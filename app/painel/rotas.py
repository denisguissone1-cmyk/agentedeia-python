import asyncio
import os

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from langchain_community.chat_message_histories import PostgresChatMessageHistory
from langchain_core.messages import AIMessage

from app.clientes import POSTGRES_CONN, get_db_conn, refresh_clients
from app.config import get_config, get_tokens, redis_client, set_config, set_tokens
from app.painel.auth import PAINEL_PASS_HASH, PAINEL_USER, conferir, logado

router = APIRouter(prefix="/admin")
_DIR = os.path.dirname(__file__)
templates = Jinja2Templates(directory=os.path.join(_DIR, "templates"))

_CAMPOS_INT = [
    "buffer_segundos", "bloqueio_humano_min", "rate_limit_max",
    "rate_limit_janela", "historico_max", "agent_timeout_seg",
]


@router.get("/login", response_class=HTMLResponse)
async def login_form(request: Request, erro: str = ""):
    return templates.TemplateResponse("login.html", {"request": request, "erro": erro})


@router.post("/login")
async def login_post(request: Request, usuario: str = Form(...), senha: str = Form(...)):
    if conferir(usuario, senha, usuario=PAINEL_USER, senha_hash=PAINEL_PASS_HASH):
        request.session["user"] = usuario
        return RedirectResponse("/admin/config", status_code=302)
    return templates.TemplateResponse(
        "login.html", {"request": request, "erro": "Usuário ou senha inválidos"},
        status_code=401,
    )


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/admin/login", status_code=302)


@router.get("/config", response_class=HTMLResponse)
async def config_form(request: Request, salvo: str = ""):
    if not logado(request):
        return RedirectResponse("/admin/login", status_code=302)
    c = await get_config()
    return templates.TemplateResponse(
        "config.html", {"request": request, "c": c, "salvo": bool(salvo), "erro": ""}
    )


@router.post("/config", response_class=HTMLResponse)
async def config_post(request: Request):
    if not logado(request):
        return RedirectResponse("/admin/login", status_code=302)
    form = await request.form()
    parcial = {}
    try:
        for campo in _CAMPOS_INT:
            if form.get(campo) not in (None, ""):
                parcial[campo] = int(form[campo])
        if form.get("system_prompt") is not None:
            parcial["system_prompt"] = form["system_prompt"]
        td = {k[len("tool__"):]: v for k, v in form.items() if k.startswith("tool__")}
        if td:
            parcial["tools_descricao"] = td
        await set_config(parcial)
    except ValueError as exc:
        c = await get_config()
        return templates.TemplateResponse(
            "config.html",
            {"request": request, "c": c, "salvo": False, "erro": str(exc)},
            status_code=400,
        )
    return RedirectResponse("/admin/config?salvo=1", status_code=302)


async def _status(numero: str) -> str:
    val = await redis_client.get(f"{numero}_block")
    return "pausado/bloqueado" if val == b"true" else "ativo"


@router.get("/sessoes", response_class=HTMLResponse)
async def sessoes(request: Request):
    if not logado(request):
        return RedirectResponse("/admin/login", status_code=302)

    def _listar():
        conn = get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute('SELECT "remoteJid", nomeusuario FROM cadastro ORDER BY "remoteJid"')
                return cur.fetchall()
        finally:
            conn.close()

    linhas = await asyncio.to_thread(_listar) or []
    sessoes_lista = []
    for row in linhas:
        numero = row["remoteJid"]
        sessoes_lista.append({
            "numero": numero, "nome": row.get("nomeusuario"),
            "status": await _status(numero),
        })
    return templates.TemplateResponse(
        "sessoes.html", {"request": request, "sessoes": sessoes_lista}
    )


@router.get("/sessoes/{numero}", response_class=HTMLResponse)
async def conversa(request: Request, numero: str):
    if not logado(request):
        return RedirectResponse("/admin/login", status_code=302)

    def _hist():
        h = PostgresChatMessageHistory(
            connection_string=POSTGRES_CONN, session_id=f"{numero}_chat"
        )
        return h.messages

    msgs = await asyncio.to_thread(_hist)
    mensagens = [
        {"role": "Elizabeth" if isinstance(m, AIMessage) else "Paciente",
         "texto": m.content}
        for m in msgs
    ]
    return templates.TemplateResponse(
        "conversa.html", {"request": request, "numero": numero, "mensagens": mensagens}
    )


@router.post("/sessoes/{numero}/pausar")
async def pausar(request: Request, numero: str):
    if not logado(request):
        return RedirectResponse("/admin/login", status_code=302)
    await redis_client.set(f"{numero}_block", "true")  # sem TTL: até despausar
    return RedirectResponse(f"/admin/sessoes/{numero}", status_code=302)


@router.post("/sessoes/{numero}/despausar")
async def despausar(request: Request, numero: str):
    if not logado(request):
        return RedirectResponse("/admin/login", status_code=302)
    await redis_client.delete(f"{numero}_block")
    return RedirectResponse(f"/admin/sessoes/{numero}", status_code=302)


_CAMPOS_TOKENS = [
    "uazapi_url", "uazapi_token", "openai_api_key",
    "google_api_key", "supabase_url", "supabase_key",
]


@router.get("/tokens", response_class=HTMLResponse)
async def tokens_form(request: Request, salvo: str = ""):
    if not logado(request):
        return RedirectResponse("/admin/login", status_code=302)
    t = await get_tokens()
    return templates.TemplateResponse(
        "tokens.html", {"request": request, "t": t, "salvo": bool(salvo), "erro": ""}
    )


@router.post("/tokens", response_class=HTMLResponse)
async def tokens_post(request: Request):
    if not logado(request):
        return RedirectResponse("/admin/login", status_code=302)
    form = await request.form()
    parcial = {k: form.get(k, "") for k in _CAMPOS_TOKENS}
    await set_tokens(parcial)
    await refresh_clients()
    return RedirectResponse("/admin/tokens?salvo=1", status_code=302)
