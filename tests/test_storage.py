import pytest

from app import storage


def test_gcs_configurado_depende_do_bucket(monkeypatch):
    monkeypatch.delenv("GCS_BUCKET", raising=False)
    assert storage.configurado() is False
    monkeypatch.setenv("GCS_BUCKET", "catalogo-teste")
    assert storage.configurado() is True


def test_url_publica_codifica_bucket_e_objeto(monkeypatch):
    monkeypatch.setenv("GCS_BUCKET", "catalogo teste")
    monkeypatch.delenv("GCS_PUBLIC_BASE_URL", raising=False)
    assert storage.url_publica("produtos/carro azul/foto 1.jpg") == (
        "https://storage.googleapis.com/catalogo%20teste/"
        "produtos/carro%20azul/foto%201.jpg"
    )


@pytest.mark.asyncio
async def test_url_acesso_usa_base_publica_sem_cliente_gcs(monkeypatch):
    monkeypatch.setenv("GCS_PUBLIC_BASE_URL", "https://cdn.exemplo.com/catalogo/")
    assert await storage.url_acesso("produtos/1/foto.jpg") == (
        "https://cdn.exemplo.com/catalogo/produtos/1/foto.jpg"
    )
