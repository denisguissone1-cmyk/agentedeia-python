"""Armazenamento de fotos de produtos no Google Cloud Storage.

As credenciais são lidas somente da infraestrutura (env/arquivo), nunca do painel:

- GCS_BUCKET: nome do bucket;
- GCS_CREDENTIALS: JSON da service account ou caminho do arquivo (opcional);
- GOOGLE_APPLICATION_CREDENTIALS / GOOGLE_CALENDAR_CREDS: fallbacks de arquivo;
- GCS_PUBLIC_BASE_URL: base pública/CDN opcional.

Sem GCS_BUCKET o catálogo mantém o comportamento legado (BYTEA no Postgres).
"""
import asyncio
import json
import os
import re
import uuid
from datetime import timedelta
from urllib.parse import quote


def configurado() -> bool:
    return bool(os.getenv("GCS_BUCKET", "").strip())


def _cliente():
    from google.cloud import storage
    from google.oauth2 import service_account

    valor = os.getenv("GCS_CREDENTIALS", "").strip()
    if valor.startswith("{"):
        creds = service_account.Credentials.from_service_account_info(json.loads(valor))
        return storage.Client(credentials=creds, project=creds.project_id)

    caminho = (
        valor
        or os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
        or os.getenv("GOOGLE_CALENDAR_CREDS", "").strip()
    )
    if caminho:
        return storage.Client.from_service_account_json(caminho)
    return storage.Client()


def _extensao(mime: str) -> str:
    return {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
        "image/avif": ".avif",
    }.get(mime.lower().split(";", 1)[0], "")


def _slug(nome: str) -> str:
    limpo = re.sub(r"[^a-zA-Z0-9_-]+", "-", nome).strip("-").lower()
    return limpo[:60] or "produto"


async def upload(pid: int, nome_produto: str, mime: str, dados: bytes) -> tuple[str, str]:
    """Envia bytes ao bucket e retorna (objeto, URL persistente de referência)."""
    bucket_nome = os.getenv("GCS_BUCKET", "").strip()
    if not bucket_nome:
        raise RuntimeError("GCS_BUCKET não configurado")
    objeto = (
        f"produtos/{pid}-{_slug(nome_produto)}/{uuid.uuid4().hex}{_extensao(mime)}"
    )

    def _enviar():
        blob = _cliente().bucket(bucket_nome).blob(objeto)
        blob.cache_control = "public, max-age=31536000, immutable"
        blob.upload_from_string(dados, content_type=mime)

    await asyncio.to_thread(_enviar)
    return objeto, url_publica(objeto)


def url_publica(objeto: str) -> str:
    base = os.getenv("GCS_PUBLIC_BASE_URL", "").strip().rstrip("/")
    if base:
        return f"{base}/{quote(objeto, safe='/')}"
    bucket = os.getenv("GCS_BUCKET", "").strip()
    return f"https://storage.googleapis.com/{quote(bucket, safe='')}/{quote(objeto, safe='/')}"


async def url_acesso(objeto: str, url_salva: str = "") -> str:
    """URL pública configurada ou URL assinada por 24 h para bucket privado."""
    if os.getenv("GCS_PUBLIC_BASE_URL", "").strip():
        return url_salva or url_publica(objeto)

    def _assinar():
        bucket = os.getenv("GCS_BUCKET", "").strip()
        return _cliente().bucket(bucket).blob(objeto).generate_signed_url(
            version="v4", expiration=timedelta(hours=24), method="GET"
        )

    return await asyncio.to_thread(_assinar)


async def remover(objeto: str) -> None:
    if not objeto or not configurado():
        return

    def _apagar():
        _cliente().bucket(os.getenv("GCS_BUCKET", "").strip()).blob(objeto).delete()

    try:
        await asyncio.to_thread(_apagar)
    except Exception:
        pass  # remoção do catálogo não deve falhar se o objeto já não existir


async def existe(objeto: str) -> bool:
    if not objeto or not configurado():
        return False

    def _existe():
        return _cliente().bucket(os.getenv("GCS_BUCKET", "").strip()).blob(objeto).exists()

    return await asyncio.to_thread(_existe)
