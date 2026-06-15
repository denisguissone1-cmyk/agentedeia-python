import fakeredis.aioredis
import pytest

from app import config as cfg


@pytest.fixture
def fake_redis(monkeypatch):
    r = fakeredis.aioredis.FakeRedis(decode_responses=False)
    monkeypatch.setattr(cfg, "redis_client", r)
    import app.bloqueios as b
    monkeypatch.setattr(b, "redis_client", r)
    return r


async def test_rate_limit_usa_max_do_config(fake_redis):
    import app.bloqueios as b
    await cfg.set_config({"rate_limit_max": 2})
    assert await b.verifica_rate_limit("551199@c.us") == "ok"      # 1
    assert await b.verifica_rate_limit("551199@c.us") == "ok"      # 2
    assert await b.verifica_rate_limit("551199@c.us") == "aviso"   # 3 (max+1)
    assert await b.verifica_rate_limit("551199@c.us") == "bloqueado"  # 4
