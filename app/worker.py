"""Worker arq: inicializa os clientes uma vez e consome a fila."""
import asyncio

import httpx

from app import clientes
from app.fila import redis_settings
from app.webhook import processar_em_background


async def processar_mensagem(ctx, body: dict) -> None:
    await processar_em_background(body)


async def startup(ctx) -> None:
    clientes.http_client = httpx.AsyncClient(timeout=30.0)
    await asyncio.to_thread(clientes.garantir_schema)
    await clientes.refresh_clients()


async def shutdown(ctx) -> None:
    if clientes.http_client:
        await clientes.http_client.aclose()


class WorkerSettings:
    functions = [processar_mensagem]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = redis_settings()
    max_jobs = 10
