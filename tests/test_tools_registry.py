import fakeredis.aioredis
import pytest

from app import config as cfg


@pytest.fixture
def fake_redis(monkeypatch):
    r = fakeredis.aioredis.FakeRedis(decode_responses=False)
    monkeypatch.setattr(cfg, "redis_client", r)
    return r


async def test_montar_tools_injeta_descricao_do_config(fake_redis):
    from app.tools import montar_tools
    await cfg.set_config({"tools_descricao": {"buscar_info": "DESC NOVA DE TESTE"}})
    tools = await montar_tools("551199@c.us")
    nomes = {t.name for t in tools}
    assert nomes == {"cadastrar", "buscar_info", "consultar_agenda",
                     "pre_marcacao", "desmarcar"}
    bi = next(t for t in tools if t.name == "buscar_info")
    assert bi.description == "DESC NOVA DE TESTE"
