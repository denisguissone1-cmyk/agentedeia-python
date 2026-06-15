"""Cria o FastAPI, registra o webhook e o painel, e o lifespan."""
import logging

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from app.clientes import lifespan
from app.config import redis_client
from app.painel.auth import SESSION_SECRET
from app.painel.rotas import router as painel_router
from app.webhook import processar_em_background, validar_token_webhook

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

app = FastAPI(lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)
app.include_router(painel_router)


@app.post("/webhook")
async def receber_mensagem(request: Request, background_tasks: BackgroundTasks):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"detail": "JSON inválido"})
    validar_token_webhook(body)
    background_tasks.add_task(processar_em_background, body)
    return {"ok": True}


@app.get("/health")
async def health():
    try:
        await redis_client.ping()
        redis_ok = True
    except Exception:
        redis_ok = False
    return {"status": "ok" if redis_ok else "degraded", "redis": redis_ok}
