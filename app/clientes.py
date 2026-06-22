"""Clientes globais e ciclo de vida do servidor.

Os clientes de IA (OpenAI, Gemini) são inicializados no lifespan a partir dos tokens
armazenados no Redis (ou env vars como fallback). Ao salvar tokens no painel, chame
refresh_clients() para aplicar sem restart.

UAZAPI_URL e UAZAPI_TOKEN não ficam aqui — são lidos via get_tokens() em cada chamada
em webhook.py e midia.py, para que mudanças valham imediatamente.
"""
import asyncio
import json
import logging
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
logger = logging.getLogger(__name__)

# Variáveis de infraestrutura (URLs internas do compose — não vão pro painel)
POSTGRES_CONN         = os.getenv("POSTGRES_CONN")
# Google Calendar: id e credenciais agora vêm do painel (config:tokens), atualizados em
# refresh_clients(). Os env vars abaixo são só fallback inicial no boot.
GOOGLE_CALENDAR_ID    = os.getenv("GOOGLE_CALENDAR_ID", "")
GOOGLE_CALENDAR_CREDS = os.getenv("GOOGLE_CALENDAR_CREDS")  # caminho de arquivo (legado)
_calendar_info        = None  # dict do JSON da conta de serviço (colado no painel)

# Clientes de IA — None até o lifespan/refresh_clients() inicializá-los
http_client:   Optional[httpx.AsyncClient]          = None
openai_client: Optional[AsyncOpenAI]                = None
llm:           Optional[ChatGoogleGenerativeAI]     = None
llm_fallback:  Optional[ChatGoogleGenerativeAI]     = None
_genai_model:  Optional[genai.GenerativeModel]      = None

# Pool de enfileiramento (arq) usado pela API para publicar jobs — None até o lifespan
arq_pool:      Optional[object]                     = None

# Google Calendar — lazy thread-safe
_calendar_lock    = threading.Lock()
_calendar_service = None


def get_db_conn():
    """Conexão psycopg2 ao Postgres interno (síncrona — use via asyncio.to_thread)."""
    return psycopg2.connect(POSTGRES_CONN, cursor_factory=psycopg2.extras.RealDictCursor)


def garantir_schema() -> None:
    """Cria todas as tabelas necessárias no boot (idempotente).

    Sempre cria a tabela base `cadastro` (registro de contatos, usada pelo webhook
    independente de tools). Em seguida roda o DDL que cada tool declara via SCHEMA_SQL
    (veja app/tools/coletar_schemas), de modo que um agente novo já suba com as tabelas
    das suas tools criadas.

    Permite subir em qualquer Postgres gerenciado (EasyPanel, RDS, etc.) sem depender do
    init.sql. Nunca derruba o boot: cada statement é isolado, e falha de um não bloqueia
    os outros nem o arranque do servidor.
    """
    if not POSTGRES_CONN:
        return
    try:
        conn = psycopg2.connect(POSTGRES_CONN)
    except Exception:
        return  # banco ainda não respondeu — segue o boot

    try:
        try:
            from app.tools import coletar_schemas
            ddl_tools = coletar_schemas()
        except Exception:
            ddl_tools = []

        statements = [
            'CREATE TABLE IF NOT EXISTS cadastro ('
            '"remoteJid" TEXT PRIMARY KEY, nomeusuario TEXT)',
            'CREATE TABLE IF NOT EXISTS produto ('
            'id SERIAL PRIMARY KEY, nome TEXT NOT NULL, preco TEXT DEFAULT \'\', '
            'descricao TEXT DEFAULT \'\', ativo BOOLEAN NOT NULL DEFAULT TRUE, '
            'criado_em TIMESTAMPTZ NOT NULL DEFAULT now())',
            'CREATE TABLE IF NOT EXISTS produto_foto ('
            'id SERIAL PRIMARY KEY, '
            'produto_id INTEGER NOT NULL REFERENCES produto(id) ON DELETE CASCADE, '
            'mime TEXT NOT NULL DEFAULT \'image/jpeg\', dados BYTEA NOT NULL, '
            'ordem INTEGER NOT NULL DEFAULT 0)',
            'CREATE TABLE IF NOT EXISTS audio_msg ('
            'id SERIAL PRIMARY KEY, "remoteJid" TEXT, '
            'mime TEXT NOT NULL DEFAULT \'audio/ogg\', dados BYTEA NOT NULL, '
            'criado_em TIMESTAMPTZ NOT NULL DEFAULT now())',
            *ddl_tools,
        ]
        for sql in statements:
            try:
                with conn.cursor() as cur:
                    cur.execute(sql)
                conn.commit()
            except Exception:
                conn.rollback()  # DDL inválido de uma tool não derruba o resto
    finally:
        conn.close()


def get_calendar_service():
    """Cria o cliente do Google Calendar uma única vez (thread-safe).

    Levanta um erro claro se as credenciais não estiverem configuradas, em vez do
    críptico "expected str, bytes or os.PathLike object, not NoneType".
    """
    global _calendar_service
    scopes = ["https://www.googleapis.com/auth/calendar"]
    with _calendar_lock:
        if _calendar_service is None:
            if _calendar_info:  # JSON colado no painel (preferencial)
                creds = service_account.Credentials.from_service_account_info(
                    _calendar_info, scopes=scopes
                )
            elif GOOGLE_CALENDAR_CREDS and os.path.isfile(GOOGLE_CALENDAR_CREDS):
                creds = service_account.Credentials.from_service_account_file(
                    GOOGLE_CALENDAR_CREDS, scopes=scopes
                )
            else:
                raise RuntimeError(
                    "Google Calendar não configurado: cole o JSON da conta de serviço em "
                    "Configurações → Google Calendar."
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
    global openai_client, llm, llm_fallback, _genai_model
    tokens = await get_tokens()

    oai_key = tokens.get("openai_api_key")
    if oai_key:
        openai_client = AsyncOpenAI(api_key=oai_key)

    ggl_key = tokens.get("google_api_key")
    if ggl_key:
        modelo   = (tokens.get("gemini_model") or "gemini-flash-latest").strip()
        fallback = (tokens.get("gemini_model_fallback") or "").strip()
        llm = ChatGoogleGenerativeAI(
            model=modelo,
            google_api_key=ggl_key,
            temperature=0.3,
            max_retries=2,   # falha rápido p/ acionar o fallback sem travar 30s
        )
        llm_fallback = (
            ChatGoogleGenerativeAI(
                model=fallback, google_api_key=ggl_key, temperature=0.3, max_retries=2
            )
            if fallback and fallback != modelo else None
        )
        genai.configure(api_key=ggl_key)
        _genai_model = genai.GenerativeModel(modelo)

    # Google Calendar: id + JSON da conta de serviço vêm do painel (config:tokens).
    global GOOGLE_CALENDAR_ID, _calendar_info, _calendar_service
    cal_id   = (tokens.get("google_calendar_id") or "").strip()
    cal_json = (tokens.get("google_calendar_json") or "").strip()
    novo_info = None
    if cal_json:
        try:
            novo_info = json.loads(cal_json)
        except Exception:
            logger.warning("google_calendar_json inválido (não é um JSON válido) — ignorado")
    novo_id = cal_id or GOOGLE_CALENDAR_ID
    with _calendar_lock:
        if novo_info != _calendar_info or novo_id != GOOGLE_CALENDAR_ID:
            _calendar_service = None  # força recriar com as novas credenciais/id
        _calendar_info = novo_info
        GOOGLE_CALENDAR_ID = novo_id


@asynccontextmanager
async def lifespan(app: FastAPI):
    from arq import create_pool

    from app.fila import redis_settings

    global http_client, arq_pool
    http_client = httpx.AsyncClient(timeout=30.0)
    await asyncio.to_thread(garantir_schema)
    from app.config import semear_preset_se_vazio
    await semear_preset_se_vazio()
    await refresh_clients()
    arq_pool = await create_pool(redis_settings())
    yield
    await arq_pool.close()
    await http_client.aclose()
