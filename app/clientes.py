"""Clientes globais e ciclo de vida do servidor.

Os clientes de IA (OpenAI, Gemini) são inicializados no lifespan a partir dos tokens
armazenados no Redis (ou env vars como fallback). Ao salvar tokens no painel, chame
refresh_clients() para aplicar sem restart.

UAZAPI_URL e UAZAPI_TOKEN não ficam aqui — são lidos via get_tokens() em cada chamada
em webhook.py e midia.py, para que mudanças valham imediatamente.
"""
import os
import threading
from contextlib import asynccontextmanager
from typing import Optional

import google.generativeai as genai
import httpx
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from fastapi import FastAPI
from google.oauth2 import service_account
from googleapiclient.discovery import build as gcal_build
from langchain_google_genai import ChatGoogleGenerativeAI
from openai import AsyncOpenAI

from app.config import get_tokens, redis_client  # fonte única do Redis

load_dotenv()

# Variáveis de infraestrutura (URLs internas do compose ou arquivos — não vão pro painel)
POSTGRES_CONN         = os.getenv("POSTGRES_CONN")
GOOGLE_CALENDAR_ID    = os.getenv("GOOGLE_CALENDAR_ID")
GOOGLE_CALENDAR_CREDS = os.getenv("GOOGLE_CALENDAR_CREDS")

# Clientes de IA — None até o lifespan/refresh_clients() inicializá-los
http_client:   Optional[httpx.AsyncClient]          = None
openai_client: Optional[AsyncOpenAI]                = None
llm:           Optional[ChatGoogleGenerativeAI]     = None
_genai_model:  Optional[genai.GenerativeModel]      = None

# Pool de enfileiramento (arq) usado pela API para publicar jobs — None até o lifespan
arq_pool:      Optional[object]                     = None

# Google Calendar — lazy thread-safe
_calendar_lock    = threading.Lock()
_calendar_service = None


def get_db_conn():
    """Conexão psycopg2 ao Postgres interno (síncrona — use via asyncio.to_thread)."""
    return psycopg2.connect(POSTGRES_CONN, cursor_factory=psycopg2.extras.RealDictCursor)


def get_calendar_service():
    """Cria o cliente do Google Calendar uma única vez (thread-safe)."""
    global _calendar_service
    with _calendar_lock:
        if _calendar_service is None:
            creds = service_account.Credentials.from_service_account_file(
                GOOGLE_CALENDAR_CREDS,
                scopes=["https://www.googleapis.com/auth/calendar"],
            )
            _calendar_service = gcal_build(
                "calendar", "v3", credentials=creds, cache_discovery=False
            )
    return _calendar_service


async def refresh_clients() -> None:
    """Re-cria os clientes de IA com os tokens atuais (Redis ou env vars).

    Chamado automaticamente no lifespan e pelo painel ao salvar tokens.
    UAZAPI não precisa de refresh — é lido por chamada via get_tokens().
    """
    global openai_client, llm, _genai_model
    tokens = await get_tokens()

    oai_key = tokens.get("openai_api_key")
    if oai_key:
        openai_client = AsyncOpenAI(api_key=oai_key)

    ggl_key = tokens.get("google_api_key")
    if ggl_key:
        llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            google_api_key=ggl_key,
            temperature=0.3,
        )
        genai.configure(api_key=ggl_key)
        _genai_model = genai.GenerativeModel("gemini-1.5-flash")


@asynccontextmanager
async def lifespan(app: FastAPI):
    from arq import create_pool

    from app.fila import redis_settings

    global http_client, arq_pool
    http_client = httpx.AsyncClient(timeout=30.0)
    await refresh_clients()
    arq_pool = await create_pool(redis_settings())
    yield
    await arq_pool.close()
    await http_client.aclose()
