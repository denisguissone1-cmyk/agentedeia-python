import base64

from app import midia
from app.webhook import separar_mensagens


def test_separar_mensagens_cria_bolhas_e_uma_pergunta_por_vez():
    texto = "Olá!\nComo posso ajudar? Você procura um carro?\n\nTenho algumas opções."
    assert separar_mensagens(texto) == [
        "Olá!",
        "Como posso ajudar?",
        "Você procura um carro?",
        "Tenho algumas opções.",
    ]


def test_separar_mensagens_vazia():
    assert separar_mensagens("  \n ") == []


async def test_baixar_midia_aceita_resposta_aninhada(monkeypatch):
    class Resposta:
        def raise_for_status(self):
            pass

        def json(self):
            return {"data": {"base64Data": base64.b64encode(b"audio").decode()}}

    class Http:
        async def post(self, *_args, **_kwargs):
            return Resposta()

    monkeypatch.setattr(midia, "get_tokens", lambda: _tokens())
    monkeypatch.setattr(midia.clientes, "http_client", Http())
    assert await midia.baixar_midia("msg-1") == b"audio"


async def _tokens():
    return {"uazapi_url": "https://uazapi.test", "uazapi_token": "token"}


async def test_transcrever_bytes_usa_gemini_se_whisper_falhar(monkeypatch):
    async def falhar(*_args):
        raise RuntimeError("sem OpenAI")

    async def gemini(*_args):
        return "Quero ver os carros"

    monkeypatch.setattr(midia, "_transcrever_openai", falhar)
    monkeypatch.setattr(midia, "_transcrever_gemini", gemini)
    assert await midia.transcrever_bytes(b"audio", "audio/webm") == "Quero ver os carros"
