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

_CAMPOS_TOKENS = [
    "uazapi_url", "uazapi_token", "openai_api_key",
    "google_api_key", "supabase_url", "supabase_key",
]

# Ordem oficial das tools + ícone/cor (espelha o mock).
_TOOLS_META = [
    ("cadastrar",         "＋",  "var(--blue-soft)"),
    ("buscar_info",       "🔍", "var(--vio-soft)"),
    ("consultar_agenda",  "📅", "var(--amber-soft)"),
    ("pre_marcacao",      "✓",  "var(--grn-soft)"),
    ("desmarcar",         "✕",  "#F0F1F4"),
]


def _tools_view(cfg: dict) -> list[dict]:
    """Monta a lista de tools (nome, ícone, cor, descrição, estado) para os templates."""
    descr = cfg.get("tools_descricao", {})
    ativas = cfg.get("tools_ativas", {})
    out = []
    for nome, icone, bg in _TOOLS_META:
        out.append({
            "nome": nome,
            "icone": icone,
            "bg": bg,
            "descricao": descr.get(nome, ""),
            "ativa": ativas.get(nome) is not False,
        })
    return out


async def _eventos_recentes(n: int = 6) -> list[dict]:
    """Lê eventos:recentes (lista Redis) de forma tolerante. Vazio se ausente/erro."""
    import json
    try:
        raw = await redis_client.lrange("eventos:recentes", 0, n - 1)
    except Exception:
        return []
    eventos = []
    for item in raw or []:
        try:
            ev = json.loads(item)
            if isinstance(ev, dict):
                eventos.append(ev)
        except Exception:
            continue
    return eventos


# ── Raiz / auth ────────────────────────────────────────────────────────────────


@router.get("", include_in_schema=False)
@router.get("/", include_in_schema=False)
async def raiz_admin(request: Request):
    if logado(request):
        return RedirectResponse("/admin/dashboard", status_code=302)
    return RedirectResponse("/admin/login", status_code=302)


@router.get("/login", response_class=HTMLResponse)
async def login_form(request: Request, erro: str = ""):
    return templates.TemplateResponse("login.html", {"request": request, "erro": erro})


@router.post("/login")
async def login_post(request: Request, usuario: str = Form(...), senha: str = Form(...)):
    if conferir(usuario, senha, usuario=PAINEL_USER, senha_hash=PAINEL_PASS_HASH):
        request.session["user"] = usuario
        return RedirectResponse("/admin/dashboard", status_code=302)
    return templates.TemplateResponse(
        "login.html", {"request": request, "erro": "Usuário ou senha inválidos"},
        status_code=401,
    )


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/admin/login", status_code=302)


# ── Dashboard ───────────────────────────────────────────────────────────────────


async def _contar_conversas() -> int:
    def _q():
        conn = get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) AS n FROM cadastro")
                row = cur.fetchone()
                return int(row["n"]) if row else 0
        finally:
            conn.close()
    try:
        return await asyncio.to_thread(_q)
    except Exception:
        return 0


async def _redis_int(chave: str) -> int:
    try:
        val = await redis_client.get(chave)
        return int(val) if val is not None else 0
    except Exception:
        return 0


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    if not logado(request):
        return RedirectResponse("/admin/login", status_code=302)

    cfg = await get_config()

    conversas = await _contar_conversas()
    msgs_hoje = await _redis_int("stats:msgs_hoje")
    agendamentos = await _redis_int("stats:agendamentos_hoje")
    try:
        fila = await redis_client.llen("arq:queue:default")
    except Exception:
        fila = 0

    stats = {
        "conversas_ativas": conversas,
        "msgs_hoje": msgs_hoje,
        "fila_pendente": fila or 0,
        "agendamentos": agendamentos,
    }

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request, "ativo": "dashboard", "titulo": "Dashboard",
            "stats": stats, "eventos": await _eventos_recentes(6),
            "tools": _tools_view(cfg),
        },
    )


# ── Tools ─────────────────────────────────────────────────────────────────────


@router.get("/tools", response_class=HTMLResponse)
async def tools_view(request: Request, salvo: str = ""):
    if not logado(request):
        return RedirectResponse("/admin/login", status_code=302)
    cfg = await get_config()
    return templates.TemplateResponse(
        "tools.html",
        {"request": request, "ativo": "tools", "titulo": "Tools",
         "tools": _tools_view(cfg), "salvo": bool(salvo)},
    )


@router.post("/tools/{nome}/toggle")
async def tools_toggle(request: Request, nome: str):
    if not logado(request):
        return RedirectResponse("/admin/login", status_code=302)
    cfg = await get_config()
    atual = cfg.get("tools_ativas", {}).get(nome) is not False
    if any(n == nome for n, _, _ in _TOOLS_META):
        await set_config({"tools_ativas": {nome: (not atual)}})
    return RedirectResponse("/admin/tools?salvo=1", status_code=302)


# ── Prompt ────────────────────────────────────────────────────────────────────


@router.get("/prompt", response_class=HTMLResponse)
async def prompt_form(request: Request, salvo: str = "", erro: str = ""):
    if not logado(request):
        return RedirectResponse("/admin/login", status_code=302)
    c = await get_config()
    return templates.TemplateResponse(
        "prompt.html",
        {"request": request, "ativo": "prompt", "titulo": "Prompt",
         "c": c, "salvo": bool(salvo), "erro": erro},
    )


@router.post("/prompt", response_class=HTMLResponse)
async def prompt_post(request: Request):
    if not logado(request):
        return RedirectResponse("/admin/login", status_code=302)
    form = await request.form()
    parcial = {}
    if form.get("system_prompt") is not None:
        parcial["system_prompt"] = form["system_prompt"]
    td = {k[len("tool__"):]: v for k, v in form.items() if k.startswith("tool__")}
    if td:
        parcial["tools_descricao"] = td
    try:
        await set_config(parcial)
    except ValueError as exc:
        c = await get_config()
        return templates.TemplateResponse(
            "prompt.html",
            {"request": request, "ativo": "prompt", "titulo": "Prompt",
             "c": c, "salvo": False, "erro": str(exc)},
            status_code=400,
        )
    return RedirectResponse("/admin/prompt?salvo=1", status_code=302)


# ── Configurações (numéricos + tokens) ────────────────────────────────────────


def _webhook_url(request: Request, tokens: dict) -> str:
    """URL pública do webhook de entrada. Usa webhook_base_url, senão deduz do request."""
    base = (tokens.get("webhook_base_url") or "").strip().rstrip("/")
    if not base:
        base = str(request.base_url).rstrip("/")
    return f"{base}/webhook"


@router.get("/config", response_class=HTMLResponse)
async def config_form(request: Request, salvo: str = "", erro: str = "", wmsg: str = "", werro: str = ""):
    if not logado(request):
        return RedirectResponse("/admin/login", status_code=302)
    c = await get_config()
    t = await get_tokens()
    return templates.TemplateResponse(
        "config.html",
        {"request": request, "ativo": "config", "titulo": "Configurações",
         "c": c, "t": t, "salvo": bool(salvo), "erro": erro,
         "webhook_url": _webhook_url(request, t), "wmsg": wmsg, "werro": werro},
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
        await set_config(parcial)
    except ValueError as exc:
        c = await get_config()
        t = await get_tokens()
        return templates.TemplateResponse(
            "config.html",
            {"request": request, "ativo": "config", "titulo": "Configurações",
             "c": c, "t": t, "salvo": False, "erro": str(exc)},
            status_code=400,
        )
    return RedirectResponse("/admin/config?salvo=1", status_code=302)


@router.post("/tokens", response_class=HTMLResponse)
async def tokens_post(request: Request):
    if not logado(request):
        return RedirectResponse("/admin/login", status_code=302)
    form = await request.form()
    parcial = {k: form.get(k, "") for k in _CAMPOS_TOKENS}
    await set_tokens(parcial)
    await refresh_clients()
    return RedirectResponse("/admin/config?salvo=1", status_code=302)


# ── Webhook de entrada ─────────────────────────────────────────────────────────


async def _registrar_webhook_uazapi(url: str, tokens: dict) -> tuple[bool, str]:
    """Registra a URL do webhook na instância UAZAPI (POST {instancia}/webhook)."""
    instancia = (tokens.get("uazapi_url") or "").strip().rstrip("/")
    token = (tokens.get("uazapi_token") or "").strip()
    if not instancia or not token:
        return False, "Configure a URL e o token da UAZAPI primeiro (em Tokens)."
    import httpx
    try:
        async with httpx.AsyncClient(timeout=20.0) as cli:
            resp = await cli.post(
                f"{instancia}/webhook",
                headers={"token": token},
                json={
                    "url": url,
                    "enabled": True,
                    "events": ["messages"],
                    "excludeMessages": ["wasSentByApi"],
                },
            )
    except Exception as exc:
        return False, f"Não consegui falar com a UAZAPI: {exc}"
    if resp.status_code < 300:
        return True, f"Webhook registrado na UAZAPI: {url}"
    return False, f"A UAZAPI respondeu {resp.status_code}: {resp.text[:160]}"


@router.post("/webhook")
async def webhook_config(request: Request):
    if not logado(request):
        return RedirectResponse("/admin/login", status_code=302)
    from urllib.parse import quote
    form = await request.form()
    await set_tokens({
        "webhook_base_url": form.get("webhook_base_url", "").strip(),
        "webhook_token":    form.get("webhook_token", "").strip(),
    })
    if form.get("acao") == "registrar":
        t = await get_tokens()
        ok, msg = await _registrar_webhook_uazapi(_webhook_url(request, t), t)
        chave = "wmsg" if ok else "werro"
        return RedirectResponse(f"/admin/config?{chave}={quote(msg)}", status_code=302)
    return RedirectResponse("/admin/config?salvo=1", status_code=302)


# ── Logs ──────────────────────────────────────────────────────────────────────


@router.get("/logs", response_class=HTMLResponse)
async def logs_view(request: Request):
    if not logado(request):
        return RedirectResponse("/admin/login", status_code=302)
    return templates.TemplateResponse(
        "logs.html",
        {"request": request, "ativo": "logs", "titulo": "Logs ao vivo",
         "eventos": await _eventos_recentes(20)},
    )


# ── Sessões / conversa ────────────────────────────────────────────────────────


async def _status(numero: str) -> str:
    val = await redis_client.get(f"{numero}_block")
    return "pausado/bloqueado" if val == b"true" else "ativo"


def _mascara(numero: str) -> str:
    """Mascara o número (ex.: 5561999999942@c.us → 5561•••42)."""
    base = numero.split("@")[0]
    if len(base) <= 6:
        return base
    return f"{base[:4]}•••{base[-2:]}"


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
            "mascara": _mascara(numero), "status": await _status(numero),
        })
    return templates.TemplateResponse(
        "sessoes.html",
        {"request": request, "ativo": "sessoes", "titulo": "Sessões",
         "sessoes": sessoes_lista},
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
        "conversa.html",
        {"request": request, "ativo": "sessoes", "titulo": "Conversa",
         "numero": numero, "mensagens": mensagens},
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
