"""Catálogo de produtos: CRUD + fotos no GCS (com fallback legado no Postgres)."""
import asyncio
import logging

import psycopg2

from app import storage
from app.clientes import get_db_conn, http_client

logger = logging.getLogger(__name__)
MAX_FOTO_BYTES = 12 * 1024 * 1024


def _row_produto(cur, pid: int) -> dict | None:
    cur.execute(
        "SELECT p.id, p.nome, p.preco, p.descricao, p.ativo, "
        "COALESCE(array_agg(f.id ORDER BY f.ordem, f.id) "
        "  FILTER (WHERE f.id IS NOT NULL), '{}') AS fotos "
        "FROM produto p LEFT JOIN produto_foto f ON f.produto_id = p.id "
        "WHERE p.id = %s GROUP BY p.id",
        (pid,),
    )
    row = cur.fetchone()
    return dict(row) if row else None


async def listar(somente_ativos: bool = False) -> list[dict]:
    def _q():
        conn = get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT p.id, p.nome, p.preco, p.descricao, p.ativo, "
                    "COALESCE(array_agg(f.id ORDER BY f.ordem, f.id) "
                    "  FILTER (WHERE f.id IS NOT NULL), '{}') AS fotos "
                    "FROM produto p LEFT JOIN produto_foto f ON f.produto_id = p.id "
                    + ("WHERE p.ativo = TRUE " if somente_ativos else "")
                    + "GROUP BY p.id ORDER BY p.nome"
                )
                return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()
    return await asyncio.to_thread(_q)


async def criar(nome: str, preco: str = "", descricao: str = "", ativo: bool = True) -> dict:
    def _q():
        conn = get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO produto (nome, preco, descricao, ativo) "
                    "VALUES (%s, %s, %s, %s) RETURNING id",
                    (nome.strip(), preco.strip(), descricao.strip(), ativo),
                )
                pid = cur.fetchone()["id"]
                prod = _row_produto(cur, pid)
            conn.commit()
            return prod
        finally:
            conn.close()
    return await asyncio.to_thread(_q)


async def substituir_catalogo(itens: list[dict]) -> int:
    """Substitui TODO o catálogo pelos itens dados (seed de preset: nome/preco/descricao).

    DELETE de produto cascateia produto_foto (ON DELETE CASCADE, ver garantir_schema) —
    sem fotos órfãs. Lista vazia não faz nada (proteção contra apagar tudo sem repor).
    Retorna o número de produtos inseridos.
    """
    itens = [i for i in itens if str(i.get("nome", "")).strip()]
    if not itens:
        return 0

    def _q():
        conn = get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT gcs_objeto FROM produto_foto WHERE gcs_objeto IS NOT NULL "
                    "AND gcs_gerenciado = TRUE"
                )
                objetos_antigos = [r["gcs_objeto"] for r in cur.fetchall()]
                cur.execute("DELETE FROM produto")
                criados = []
                for i in itens:
                    cur.execute(
                        "INSERT INTO produto (nome, preco, descricao, ativo) "
                        "VALUES (%s, %s, %s, TRUE) RETURNING id",
                        (i["nome"].strip(), str(i.get("preco", "")).strip(),
                         str(i.get("descricao", "")).strip()),
                    )
                    criados.append((cur.fetchone()["id"], i))
            conn.commit()
            return objetos_antigos, criados
        finally:
            conn.close()
    objetos_antigos, criados = await asyncio.to_thread(_q)
    await asyncio.gather(*(storage.remover(o) for o in objetos_antigos))
    for pid, item in criados:
        fotos_item = item.get("fotos", []) or []
        for foto_item in fotos_item:
            try:
                if isinstance(foto_item, dict) and foto_item.get("gcs_objeto"):
                    objeto = foto_item["gcs_objeto"]
                    if await storage.existe(objeto):
                        await adicionar_referencia_gcs(
                            pid, objeto, foto_item.get("mime", "image/jpeg")
                        )
                    elif foto_item.get("url"):
                        await importar_fotos(pid, [foto_item["url"]])
                    else:
                        logger.warning("Objeto GCS ausente no preset: %s", objeto)
                elif isinstance(foto_item, str):
                    await importar_fotos(pid, [foto_item])
            except Exception as exc:
                logger.warning("Falha ao associar foto do produto %s: %s", pid, exc)
    return len(criados)


async def atualizar(pid: int, nome: str, preco: str, descricao: str, ativo: bool) -> dict | None:
    def _q():
        conn = get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE produto SET nome=%s, preco=%s, descricao=%s, ativo=%s WHERE id=%s",
                    (nome.strip(), preco.strip(), descricao.strip(), ativo, pid),
                )
                prod = _row_produto(cur, pid)
            conn.commit()
            return prod
        finally:
            conn.close()
    return await asyncio.to_thread(_q)


async def set_ativo(pid: int, ativo: bool) -> None:
    def _q():
        conn = get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE produto SET ativo=%s WHERE id=%s", (ativo, pid))
            conn.commit()
        finally:
            conn.close()
    await asyncio.to_thread(_q)


async def remover(pid: int) -> None:
    def _objetos():
        conn = get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT gcs_objeto FROM produto_foto "
                    "WHERE produto_id=%s AND gcs_objeto IS NOT NULL "
                    "AND gcs_gerenciado = TRUE", (pid,)
                )
                return [r["gcs_objeto"] for r in cur.fetchall()]
        finally:
            conn.close()

    objetos = await asyncio.to_thread(_objetos)

    def _q():
        conn = get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM produto WHERE id=%s", (pid,))
            conn.commit()
        finally:
            conn.close()
    await asyncio.to_thread(_q)
    await asyncio.gather(*(storage.remover(o) for o in objetos))


async def adicionar_foto(pid: int, mime: str, dados: bytes) -> int:
    if not dados:
        raise ValueError("foto vazia")
    if len(dados) > MAX_FOTO_BYTES:
        raise ValueError("a foto excede o limite de 12 MB")

    def _nome():
        conn = get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT nome FROM produto WHERE id=%s", (pid,))
                row = cur.fetchone()
                return row["nome"] if row else None
        finally:
            conn.close()

    nome = await asyncio.to_thread(_nome)
    if not nome:
        raise ValueError("produto não encontrado")

    objeto = url = None
    dados_db = dados
    if storage.configurado():
        objeto, url = await storage.upload(pid, nome, mime, dados)
        dados_db = None

    def _q():
        conn = get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO produto_foto (produto_id, mime, dados, gcs_objeto, url, ordem) "
                    "VALUES (%s, %s, %s, %s, %s, COALESCE((SELECT MAX(ordem)+1 FROM produto_foto "
                    "  WHERE produto_id=%s), 0)) RETURNING id",
                    (pid, mime, psycopg2.Binary(dados_db) if dados_db is not None else None,
                     objeto, url, pid),
                )
                fid = cur.fetchone()["id"]
            conn.commit()
            return fid
        finally:
            conn.close()
    try:
        return await asyncio.to_thread(_q)
    except Exception:
        if objeto:
            await storage.remover(objeto)
        raise


async def adicionar_referencia_gcs(pid: int, objeto: str, mime: str = "image/jpeg") -> int:
    """Associa ao produto um objeto preexistente, sem assumir propriedade para excluí-lo."""
    def _q():
        conn = get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO produto_foto "
                    "(produto_id, mime, dados, gcs_objeto, url, gcs_gerenciado, ordem) "
                    "VALUES (%s, %s, NULL, %s, %s, FALSE, "
                    "COALESCE((SELECT MAX(ordem)+1 FROM produto_foto WHERE produto_id=%s), 0)) "
                    "RETURNING id",
                    (pid, mime, objeto, storage.url_publica(objeto), pid),
                )
                fid = cur.fetchone()["id"]
            conn.commit()
            return fid
        finally:
            conn.close()

    return await asyncio.to_thread(_q)


async def remover_foto(fid: int) -> None:
    def _q():
        conn = get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT gcs_objeto, gcs_gerenciado FROM produto_foto WHERE id=%s", (fid,)
                )
                row = cur.fetchone()
                cur.execute("DELETE FROM produto_foto WHERE id=%s", (fid,))
            conn.commit()
            return row["gcs_objeto"] if row and row["gcs_gerenciado"] else None
        finally:
            conn.close()
    objeto = await asyncio.to_thread(_q)
    if objeto:
        await storage.remover(objeto)


async def foto(fid: int) -> tuple[str, bytes] | None:
    """(mime, bytes) de uma foto, para servir em /media/foto/<id>."""
    def _q():
        conn = get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT mime, dados FROM produto_foto WHERE id=%s", (fid,))
                row = cur.fetchone()
                if not row or row["dados"] is None:
                    return None
                return row["mime"], bytes(row["dados"])
        finally:
            conn.close()
    return await asyncio.to_thread(_q)


async def foto_url(fid: int) -> str | None:
    """Retorna URL assinada/pública da foto no GCS; None para fotos BYTEA legadas."""
    def _q():
        conn = get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT gcs_objeto, url FROM produto_foto WHERE id=%s", (fid,)
                )
                row = cur.fetchone()
                return dict(row) if row else None
        finally:
            conn.close()

    row = await asyncio.to_thread(_q)
    if not row or not row["gcs_objeto"]:
        return None
    return await storage.url_acesso(row["gcs_objeto"], row.get("url") or "")


async def importar_fotos(pid: int, urls: list[str]) -> list[int]:
    """Baixa imagens HTTP(S) e as persiste pelo fluxo normal (GCS quando configurado)."""
    ids = []
    for origem in urls:
        url = str(origem).strip()
        if not url.startswith(("https://", "http://")):
            raise ValueError(f"URL de foto inválida: {url[:80]}")
        async with http_client.stream(
            "GET", url, follow_redirects=True,
            headers={"User-Agent": "AgenteIA-Catalogo/1.0"},
        ) as resposta:
            resposta.raise_for_status()
            mime = resposta.headers.get("content-type", "").split(";", 1)[0].lower()
            if not mime.startswith("image/"):
                raise ValueError(f"a URL não retornou uma imagem: {url[:80]}")
            partes = []
            tamanho = 0
            async for parte in resposta.aiter_bytes():
                tamanho += len(parte)
                if tamanho > MAX_FOTO_BYTES:
                    raise ValueError("a foto remota excede o limite de 12 MB")
                partes.append(parte)
        ids.append(await adicionar_foto(pid, mime, b"".join(partes)))
    return ids


async def fotos_ids(pid: int) -> list[int]:
    def _q():
        conn = get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM produto_foto WHERE produto_id=%s ORDER BY ordem, id", (pid,)
                )
                return [r["id"] for r in cur.fetchall()]
        finally:
            conn.close()
    return await asyncio.to_thread(_q)


async def urls_fotos(pid: int, base_app: str = "") -> list[str]:
    """URLs prontas para envio: GCS direto ou rota do app para fotos legadas."""
    def _q():
        conn = get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, gcs_objeto, url FROM produto_foto "
                    "WHERE produto_id=%s ORDER BY ordem, id", (pid,)
                )
                return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    linhas = await asyncio.to_thread(_q)
    urls = []
    for foto_item in linhas:
        if foto_item["gcs_objeto"]:
            urls.append(await storage.url_acesso(
                foto_item["gcs_objeto"], foto_item.get("url") or ""
            ))
        elif base_app:
            urls.append(f"{base_app.rstrip('/')}/media/foto/{foto_item['id']}")
    return urls


async def resumo_ativos() -> list[dict]:
    """Resumo dos produtos ativos para a tool do agente (nome, preço, specs, qtd fotos)."""
    prods = await listar(somente_ativos=True)
    return [
        {"id": p["id"], "nome": p["nome"], "preco": p["preco"],
         "descricao": p["descricao"], "tem_fotos": len(p["fotos"]) > 0}
        for p in prods
    ]
