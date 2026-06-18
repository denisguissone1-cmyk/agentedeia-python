"""API JSON do painel (consumida pelo SPA React em frontend/).

Reaproveita toda a lógica existente (config, presets, memória, auth). Mesma sessão por
cookie do FastAPI — o SPA chama com credenciais na mesma origem.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app import presets
from app.config import get_config, set_config
from app.memoria import resetar_todo_historico
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
