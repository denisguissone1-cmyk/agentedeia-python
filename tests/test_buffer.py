import asyncio

import fakeredis.aioredis
import pytest

from app import config as cfg


@pytest.fixture
def fake_redis(monkeypatch):
    r = fakeredis.aioredis.FakeRedis(decode_responses=False)
    monkeypatch.setattr(cfg, "redis_client", r)
    import app.buffer as buf
    monkeypatch.setattr(buf, "redis_client", r)
    return r


async def test_mensagem_nova_descarta_a_anterior(fake_redis):
    """A 1ª chamada deve retornar None (a 2ª chegou e roubou o turno)."""
    import app.buffer as buf
    await cfg.set_config({"buffer_segundos": 1})
    num = "551199@c.us"

    async def primeira():
        return await buf.buffer_mensagens(num, '{"txtmessage":"oi"}')

    async def segunda():
        await asyncio.sleep(0.3)  # chega durante a espera da primeira
        return await buf.buffer_mensagens(num, '{"txtmessage":"tudo bem?"}')

    r1, r2 = await asyncio.gather(primeira(), segunda())
    assert r1 is None                       # primeira foi descartada
    assert r2 is not None and len(r2) == 2  # segunda processou as duas mensagens
