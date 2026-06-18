"""Cria o FastAPI, registra o webhook, a API do painel (SPA) e o lifespan."""
import logging
import os

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app import clientes
from app.clientes import lifespan
from app.config import redis_client
from app.painel.api import router as api_router
from app.painel.auth import SESSION_SECRET
from app.painel.rotas import router as painel_router
from app.webhook import validar_token_webhook

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# dist do SPA React (frontend/dist), gerado no build. Ausente em dev (usa-se o vite).
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DIST = os.path.join(_ROOT, "frontend", "dist")

app = FastAPI(lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)
app.include_router(api_router)       # /api/* (JSON, consumido pelo SPA)
app.include_router(painel_router)    # /admin/* (painel Jinja legado — mantido por ora)


@app.post("/webhook")
async def receber_mensagem(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"detail": "JSON inválido"})
    await validar_token_webhook(body)
    await clientes.arq_pool.enqueue_job("processar_mensagem", body)
    return {"ok": True}


@app.get("/health")
async def health():
    try:
        await redis_client.ping()
        redis_ok = True
    except Exception:
        redis_ok = False
    return {"status": "ok" if redis_ok else "degraded", "redis": redis_ok}


@app.get("/media/foto/{fid}", include_in_schema=False)
async def media_foto(fid: int):
    """Serve a foto de um produto (pública — o painel exibe e a UAZAPI baixa para enviar)."""
    from app import produtos
    item = await produtos.foto(fid)
    if not item:
        return Response(status_code=404)
    mime, dados = item
    return Response(content=dados, media_type=mime, headers={"Cache-Control": "public, max-age=86400"})


# ── SPA React (servido em produção; em dev usa-se `npm run dev` com proxy) ───────
if os.path.isdir(_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(_DIST, "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        """Fallback do SPA: serve arquivos do dist; senão entrega o index.html (client-side routing)."""
        candidato = os.path.normpath(os.path.join(_DIST, full_path))
        if full_path and candidato.startswith(_DIST) and os.path.isfile(candidato):
            return FileResponse(candidato)
        return FileResponse(os.path.join(_DIST, "index.html"))
