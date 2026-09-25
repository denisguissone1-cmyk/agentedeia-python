import fakeredis.aioredis

from app import produtos
from app.tools import enviar_fotos_produto


class _Resposta:
    status_code = 200


class _Http:
    def __init__(self):
        self.chamadas = []

    async def post(self, *args, **kwargs):
        self.chamadas.append((args, kwargs))
        return _Resposta()


async def test_fotos_nao_reenvia_mesmo_veiculo_na_conversa(monkeypatch):
    redis = fakeredis.aioredis.FakeRedis(decode_responses=False)
    http = _Http()
    monkeypatch.setattr(enviar_fotos_produto, "redis_client", redis)
    monkeypatch.setattr(enviar_fotos_produto, "get_tokens", lambda: _tokens())
    monkeypatch.setattr(enviar_fotos_produto.clientes, "http_client", http)
    monkeypatch.setattr(produtos, "urls_fotos", lambda *_args: _urls())

    tool = enviar_fotos_produto.criar("5511999999999", "fotos")
    primeira = await tool.ainvoke({"produto_id": 42})
    segunda = await tool.ainvoke({"produto_id": 42})

    assert "FOTOS_ENVIADAS" in primeira
    assert "FOTOS_JA_ENVIADAS" in segunda
    assert len(http.chamadas) == 2


async def test_fotos_so_reenvia_com_pedido_explicito(monkeypatch):
    redis = fakeredis.aioredis.FakeRedis(decode_responses=False)
    http = _Http()
    monkeypatch.setattr(enviar_fotos_produto, "redis_client", redis)
    monkeypatch.setattr(enviar_fotos_produto, "get_tokens", lambda: _tokens())
    monkeypatch.setattr(enviar_fotos_produto.clientes, "http_client", http)
    monkeypatch.setattr(produtos, "urls_fotos", lambda *_args: _urls())

    tool = enviar_fotos_produto.criar("5511888888888", "fotos")
    await tool.ainvoke({"produto_id": 7})
    reenviada = await tool.ainvoke({"produto_id": 7, "reenviar": True})

    assert "FOTOS_ENVIADAS" in reenviada
    assert len(http.chamadas) == 4


async def _tokens():
    return {"uazapi_url": "https://uazapi.test", "uazapi_token": "token"}


async def _urls(*_args):
    return ["https://storage.test/01.webp", "https://storage.test/02.webp"]
