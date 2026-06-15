import os

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import get_config, set_config
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
