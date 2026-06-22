"""Helpers puros do painel: consultas a Redis/Postgres/Gemini e formatação.

Compartilhados pela API JSON do SPA (``app/painel/api.py``). Sem dependência de
templates nem de framework de view — só dados.
"""
import asyncio
import json

from fastapi import Request

from app.clientes import get_db_conn
from app.config import get_tokens, redis_client

_CAMPOS_INT = [
    "buffer_segundos", "bloqueio_humano_min", "rate_limit_max",
    "rate_limit_janela", "historico_max", "agent_timeout_seg",
]

# Campos de texto livre da marca (editáveis em Configurações).
_CAMPOS_MARCA = ["nome_agente", "nome_marca"]

_CAMPOS_TOKENS = [
    "uazapi_url", "uazapi_token", "openai_api_key",
    "google_api_key", "supabase_url", "supabase_key",
    "gemini_model", "gemini_model_fallback",
    "google_calendar_id", "google_calendar_json",
]

# Fallback caso a API do Google não responda (a lista viva vem de /api/modelos).
_MODELOS_FALLBACK = [
    "gemini-flash-latest", "gemini-flash-lite-latest",
    "gemini-2.5-flash", "gemini-2.5-flash-lite",
    "gemini-2.0-flash", "gemini-2.0-flash-lite",
    "gemini-3-flash-preview", "gemini-3.5-flash", "gemini-2.5-pro",
]


async def _listar_modelos_gemini() -> list[str]:
    """Lista os modelos Gemini da chave salva (generateContent). Fallback se falhar."""
    import httpx
    tokens = await get_tokens()
    key = (tokens.get("google_api_key") or "").strip()
    if not key:
        return _MODELOS_FALLBACK
    try:
        async with httpx.AsyncClient(timeout=12.0) as cli:
            r = await cli.get(
                "https://generativelanguage.googleapis.com/v1beta/models",
                params={"key": key, "pageSize": 200},
            )
        r.raise_for_status()
        nomes = []
        for m in r.json().get("models", []):
            if "generateContent" not in (m.get("supportedGenerationMethods") or []):
                continue
            nome = (m.get("name") or "").replace("models/", "")
            if not nome.startswith("gemini"):
                continue
            if any(x in nome for x in ("image", "tts", "embedding", "aqa", "vision")):
                continue
            nomes.append(nome)
        return nomes or _MODELOS_FALLBACK
    except Exception:
        return _MODELOS_FALLBACK


# Ordem oficial das tools + ícone/cor (consumida pelo SPA).
_TOOLS_META = [
    ("cadastrar",         "＋",  "var(--blue-soft)"),
    ("buscar_info",       "🔍", "var(--vio-soft)"),
    ("consultar_agenda",  "📅", "var(--amber-soft)"),
    ("pre_marcacao",      "✓",  "var(--grn-soft)"),
    ("desmarcar",         "✕",  "#F0F1F4"),
    ("listar_produtos",   "📦", "var(--blue-soft)"),
    ("enviar_fotos_produto", "🖼️", "var(--vio-soft)"),
]


def _tools_view(cfg: dict) -> list[dict]:
    """Monta a lista de tools (nome, ícone, cor, descrição, estado)."""
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


def _webhook_url(request: Request, tokens: dict) -> str:
    """URL pública do webhook de entrada. Usa webhook_base_url, senão deduz do request."""
    base = (tokens.get("webhook_base_url") or "").strip().rstrip("/")
    if not base:
        base = str(request.base_url).rstrip("/")
    return f"{base}/webhook"


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


async def _status(numero: str) -> str:
    val = await redis_client.get(f"{numero}_block")
    return "pausado/bloqueado" if val == b"true" else "ativo"


def _mascara(numero: str) -> str:
    """Mascara o número (ex.: 5561999999942@c.us → 5561•••42)."""
    base = numero.split("@")[0]
    if len(base) <= 6:
        return base
    return f"{base[:4]}•••{base[-2:]}"
