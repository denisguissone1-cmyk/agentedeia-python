"""API JSON do painel (consumida pelo SPA React em frontend/).

Reaproveita toda a lógica existente (config, presets, memória, auth). Mesma sessão por
cookie do FastAPI — o SPA chama com credenciais na mesma origem.
"""
import asyncio

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from app import presets, produtos
from app.config import get_config, get_tokens, redis_client, set_config, set_tokens
from app.memoria import resetar_todo_historico
from app.painel import rotas as R  # reutiliza helpers do painel Jinja
from app.painel.auth import PAINEL_PASS_HASH, PAINEL_USER, conferir, logado

router = APIRouter(prefix="/api")


def require_login(request: Request) -> str:
    """Dependência: 401 JSON se não logado; senão devolve o usuário."""
    if not logado(request):
        raise HTTPException(status_code=401, detail="Não autenticado")
    return request.session["user"]


# ── Auth ────────────────────────────────────────────────────────────────────────

class LoginIn(BaseModel):
    usuario: str
    senha: str


@router.post("/login")
async def login(request: Request, dados: LoginIn):
    if not conferir(dados.usuario, dados.senha, usuario=PAINEL_USER, senha_hash=PAINEL_PASS_HASH):
        raise HTTPException(status_code=401, detail="Usuário ou senha inválidos")
    request.session["user"] = dados.usuario
    return {"user": dados.usuario}


@router.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@router.get("/me")
async def me(user: str = Depends(require_login)):
    return {"user": user}


# ── Marca (usada no shell do SPA) ───────────────────────────────────────────────

async def _marca() -> dict:
    c = await get_config()
    nome_agente = (c.get("nome_agente") or "Agente").strip()
    nome_marca = (c.get("nome_marca") or "Agente IA").strip()
    return {"nome_agente": nome_agente, "nome_marca": nome_marca}


@router.get("/marca")
async def marca(_: str = Depends(require_login)):
    return await _marca()


# ── Painel Geral ─────────────────────────────────────────────────────────────────

@router.get("/geral")
async def geral(_: str = Depends(require_login)):
    c = await get_config()
    m = await _marca()
    return {
        "presets": presets.listar(),
        "preset_ativo": c.get("preset_ativo", ""),
        **m,
    }


class PresetIn(BaseModel):
    preset: str


@router.post("/preset")
async def aplicar_preset(dados: PresetIn, _: str = Depends(require_login)):
    nome = (dados.preset or "").strip()
    try:
        cfg = presets.carregar(nome)
        cfg["preset_ativo"] = nome
        await set_config(cfg)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Não foi possível ativar '{nome}': {exc}")
    return {"ok": True, "preset_ativo": nome}


@router.post("/reset")
async def resetar(_: str = Depends(require_login)):
    apagadas = await resetar_todo_historico()
    return {"ok": True, "apagadas": apagadas}


# ── Dashboard ────────────────────────────────────────────────────────────────────

@router.get("/dashboard")
async def dashboard(_: str = Depends(require_login)):
    cfg = await get_config()
    try:
        fila = await redis_client.llen("arq:queue:default")
    except Exception:
        fila = 0
    stats = {
        "conversas_ativas": await R._contar_conversas(),
        "msgs_hoje": await R._redis_int("stats:msgs_hoje"),
        "fila_pendente": fila or 0,
        "agendamentos": await R._redis_int("stats:agendamentos_hoje"),
    }
    return {"stats": stats, "eventos": await R._eventos_recentes(6), "tools": R._tools_view(cfg)}


# ── Tools ─────────────────────────────────────────────────────────────────────

@router.get("/tools")
async def tools(_: str = Depends(require_login)):
    cfg = await get_config()
    return {"tools": R._tools_view(cfg)}


@router.post("/tools/{nome}/toggle")
async def tool_toggle(nome: str, _: str = Depends(require_login)):
    cfg = await get_config()
    atual = cfg.get("tools_ativas", {}).get(nome) is not False
    if not any(n == nome for n, _ic, _bg in R._TOOLS_META):
        raise HTTPException(status_code=404, detail="tool desconhecida")
    await set_config({"tools_ativas": {nome: (not atual)}})
    return {"nome": nome, "ativa": (not atual)}


# ── Prompt ────────────────────────────────────────────────────────────────────

@router.get("/prompt")
async def prompt_get(_: str = Depends(require_login)):
    c = await get_config()
    return {"system_prompt": c["system_prompt"], "tools_descricao": c["tools_descricao"]}


class PromptIn(BaseModel):
    system_prompt: str | None = None
    tools_descricao: dict | None = None


@router.post("/prompt")
async def prompt_post(dados: PromptIn, _: str = Depends(require_login)):
    parcial: dict = {}
    if dados.system_prompt is not None:
        parcial["system_prompt"] = dados.system_prompt
    if dados.tools_descricao:
        parcial["tools_descricao"] = dados.tools_descricao
    try:
        await set_config(parcial)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True}


# ── Configurações / tokens / webhook ────────────────────────────────────────────

@router.get("/config")
async def config_get(request: Request, _: str = Depends(require_login)):
    c = await get_config()
    t = await get_tokens()
    return {"c": c, "t": t, "webhook_url": R._webhook_url(request, t)}


@router.post("/config")
async def config_post(request: Request, _: str = Depends(require_login)):
    body = await request.json()
    parcial: dict = {}
    for campo in R._CAMPOS_INT:
        if body.get(campo) not in (None, ""):
            try:
                parcial[campo] = int(body[campo])
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail=f"{campo} deve ser um número inteiro")
    for campo in R._CAMPOS_MARCA:
        if body.get(campo) not in (None, ""):
            parcial[campo] = str(body[campo]).strip()
    try:
        await set_config(parcial)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True}


@router.post("/tokens")
async def tokens_post(request: Request, _: str = Depends(require_login)):
    from app.clientes import refresh_clients
    body = await request.json()
    await set_tokens({k: body.get(k, "") for k in R._CAMPOS_TOKENS})
    await refresh_clients()
    return {"ok": True}


@router.get("/modelos")
async def modelos(_: str = Depends(require_login)):
    return await R._listar_modelos_gemini()


class WebhookIn(BaseModel):
    webhook_base_url: str = ""
    webhook_token: str = ""
    registrar: bool = False


@router.post("/webhook")
async def webhook_post(request: Request, dados: WebhookIn, _: str = Depends(require_login)):
    await set_tokens({
        "webhook_base_url": dados.webhook_base_url.strip(),
        "webhook_token": dados.webhook_token.strip(),
    })
    if dados.registrar:
        t = await get_tokens()
        ok, msg = await R._registrar_webhook_uazapi(R._webhook_url(request, t), t)
        return {"ok": ok, "msg": msg}
    return {"ok": True, "msg": "Webhook salvo."}


# ── Sessões / conversa ───────────────────────────────────────────────────────────

@router.get("/sessoes")
async def sessoes(_: str = Depends(require_login)):
    from app.clientes import get_db_conn

    def _listar():
        conn = get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    'CREATE TABLE IF NOT EXISTS cadastro ('
                    '"remoteJid" TEXT PRIMARY KEY, nomeusuario TEXT)'
                )
                cur.execute('SELECT "remoteJid", nomeusuario FROM cadastro ORDER BY "remoteJid"')
                rows = cur.fetchall()
            conn.commit()
            return rows
        finally:
            conn.close()

    erro = ""
    try:
        linhas = await asyncio.to_thread(_listar) or []
    except Exception as exc:
        linhas, erro = [], f"Não foi possível acessar o banco de dados ({type(exc).__name__})."
    out = []
    for row in linhas:
        numero = row["remoteJid"]
        out.append({
            "numero": numero, "nome": row.get("nomeusuario"),
            "mascara": R._mascara(numero), "status": await R._status(numero),
        })
    return {"sessoes": out, "erro": erro}


@router.get("/sessoes/{numero}")
async def conversa(numero: str, _: str = Depends(require_login)):
    from langchain_community.chat_message_histories import PostgresChatMessageHistory
    from langchain_core.messages import AIMessage

    from app.clientes import POSTGRES_CONN

    def _hist():
        h = PostgresChatMessageHistory(connection_string=POSTGRES_CONN, session_id=f"{numero}_chat")
        return h.messages

    msgs = await asyncio.to_thread(_hist)
    m = await _marca()
    mensagens = [
        {"role": m["nome_agente"] if isinstance(x, AIMessage) else "Contato",
         "ag": isinstance(x, AIMessage), "texto": x.content}
        for x in msgs
    ]
    return {"numero": numero, "mensagens": mensagens}


@router.post("/sessoes/{numero}/pausar")
async def pausar(numero: str, _: str = Depends(require_login)):
    await redis_client.set(f"{numero}_block", "true")
    return {"ok": True}


@router.post("/sessoes/{numero}/despausar")
async def despausar(numero: str, _: str = Depends(require_login)):
    await redis_client.delete(f"{numero}_block")
    return {"ok": True}


# ── Logs (feed + SSE ao vivo) ───────────────────────────────────────────────────

@router.get("/logs")
async def logs(_: str = Depends(require_login)):
    return {"eventos": await R._eventos_recentes(20)}


@router.get("/logs/stream")
async def logs_stream(request: Request):
    if not logado(request):
        return Response(status_code=401)

    async def gen():
        pubsub = redis_client.pubsub()
        await pubsub.subscribe("eventos:stream")
        try:
            yield ": conectado\n\n"
            async for msg in pubsub.listen():
                if msg.get("type") == "message":
                    data = msg["data"]
                    if isinstance(data, (bytes, bytearray)):
                        data = data.decode("utf-8", "ignore")
                    yield f"data: {data}\n\n"
        finally:
            try:
                await pubsub.unsubscribe("eventos:stream")
                await pubsub.aclose()
            except Exception:
                pass

    return StreamingResponse(
        gen(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Execuções ────────────────────────────────────────────────────────────────────

@router.get("/execucoes")
async def execucoes(_: str = Depends(require_login)):
    from app.execucoes import listar
    return {"execucoes": await listar(40)}


# ── Produtos (catálogo) ──────────────────────────────────────────────────────────

class ProdutoIn(BaseModel):
    nome: str
    preco: str = ""
    descricao: str = ""
    ativo: bool = True


@router.get("/produtos")
async def produtos_list(_: str = Depends(require_login)):
    return {"produtos": await produtos.listar()}


@router.post("/produtos")
async def produtos_create(dados: ProdutoIn, _: str = Depends(require_login)):
    if not dados.nome.strip():
        raise HTTPException(status_code=400, detail="O nome do produto é obrigatório")
    return await produtos.criar(dados.nome, dados.preco, dados.descricao, dados.ativo)


@router.put("/produtos/{pid}")
async def produtos_update(pid: int, dados: ProdutoIn, _: str = Depends(require_login)):
    if not dados.nome.strip():
        raise HTTPException(status_code=400, detail="O nome do produto é obrigatório")
    prod = await produtos.atualizar(pid, dados.nome, dados.preco, dados.descricao, dados.ativo)
    if not prod:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    return prod


@router.post("/produtos/{pid}/toggle")
async def produtos_toggle(pid: int, _: str = Depends(require_login)):
    prods = {p["id"]: p for p in await produtos.listar()}
    if pid not in prods:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    novo = not prods[pid]["ativo"]
    await produtos.set_ativo(pid, novo)
    return {"id": pid, "ativo": novo}


@router.delete("/produtos/{pid}")
async def produtos_delete(pid: int, _: str = Depends(require_login)):
    await produtos.remover(pid)
    return {"ok": True}


@router.post("/produtos/{pid}/fotos")
async def produtos_upload(pid: int, fotos: list[UploadFile] = File(...), _: str = Depends(require_login)):
    ids = []
    for f in fotos:
        dados = await f.read()
        if not dados:
            continue
        mime = f.content_type or "image/jpeg"
        if not mime.startswith("image/"):
            raise HTTPException(status_code=400, detail=f"'{f.filename}' não é uma imagem")
        ids.append(await produtos.adicionar_foto(pid, mime, dados))
    return {"ok": True, "fotos": ids}


@router.delete("/produtos/fotos/{fid}")
async def produtos_foto_delete(fid: int, _: str = Depends(require_login)):
    await produtos.remover_foto(fid)
    return {"ok": True}
