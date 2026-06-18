"""Catálogo de produtos: CRUD + fotos (bytea no Postgres).

As fotos ficam na tabela produto_foto (bytes na própria base) e são servidas por uma rota
pública /media/foto/<id> (app/main.py), para o painel exibir e a UAZAPI baixar ao enviar.
As tabelas são criadas no boot por garantir_schema (app/clientes.py).
"""
import asyncio

import psycopg2

from app.clientes import get_db_conn


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
    def _q():
        conn = get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM produto WHERE id=%s", (pid,))
            conn.commit()
        finally:
            conn.close()
    await asyncio.to_thread(_q)


async def adicionar_foto(pid: int, mime: str, dados: bytes) -> int:
    def _q():
        conn = get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO produto_foto (produto_id, mime, dados, ordem) "
                    "VALUES (%s, %s, %s, COALESCE((SELECT MAX(ordem)+1 FROM produto_foto "
                    "  WHERE produto_id=%s), 0)) RETURNING id",
                    (pid, mime, psycopg2.Binary(dados), pid),
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
                cur.execute("DELETE FROM produto_foto WHERE id=%s", (fid,))
            conn.commit()
        finally:
            conn.close()
    await asyncio.to_thread(_q)


async def foto(fid: int) -> tuple[str, bytes] | None:
    """(mime, bytes) de uma foto, para servir em /media/foto/<id>."""
    def _q():
        conn = get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT mime, dados FROM produto_foto WHERE id=%s", (fid,))
                row = cur.fetchone()
                if not row:
                    return None
                return row["mime"], bytes(row["dados"])
        finally:
            conn.close()
    return await asyncio.to_thread(_q)


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


async def resumo_ativos() -> list[dict]:
    """Resumo dos produtos ativos para a tool do agente (nome, preço, specs, qtd fotos)."""
    prods = await listar(somente_ativos=True)
    return [
        {"id": p["id"], "nome": p["nome"], "preco": p["preco"],
         "descricao": p["descricao"], "tem_fotos": len(p["fotos"]) > 0}
        for p in prods
    ]
