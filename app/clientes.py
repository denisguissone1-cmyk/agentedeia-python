"""Clientes globais (criados uma vez) e ciclo de vida do servidor."""
import os
import threading
from contextlib import asynccontextmanager
from typing import Optional

import google.generativeai as genai
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI
from google.oauth2 import service_account
from googleapiclient.discovery import build as gcal_build
from langchain_google_genai import ChatGoogleGenerativeAI
from openai import AsyncOpenAI
from supabase import create_client

from app.config import redis_client  # fonte única do Redis

load_dotenv()

SUPABASE_URL          = os.getenv("SUPABASE_URL")
SUPABASE_KEY          = os.getenv("SUPABASE_KEY")
OPENAI_API_KEY        = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY        = os.getenv("GOOGLE_API_KEY")
UAZAPI_TOKEN          = os.getenv("UAZAPI_TOKEN")
UAZAPI_URL            = os.getenv("UAZAPI_URL")
POSTGRES_CONN         = os.getenv("POSTGRES_CONN")
GOOGLE_CALENDAR_ID    = os.getenv("GOOGLE_CALENDAR_ID")
GOOGLE_CALENDAR_CREDS = os.getenv("GOOGLE_CALENDAR_CREDS")

supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
openai_client   = AsyncOpenAI(api_key=OPENAI_API_KEY)

llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash",
    google_api_key=GOOGLE_API_KEY,
    temperature=0.3,
)

http_client: Optional[httpx.AsyncClient] = None
_genai_model: Optional[genai.GenerativeModel] = None
_calendar_lock = threading.Lock()
_calendar_service = None


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client, _genai_model
    http_client  = httpx.AsyncClient(timeout=30.0)
    genai.configure(api_key=GOOGLE_API_KEY)
    _genai_model = genai.GenerativeModel("gemini-1.5-flash")
    yield
    await http_client.aclose()
