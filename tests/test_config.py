import fakeredis.aioredis
import pytest

from app import config as cfg


@pytest.fixture
def fake_redis(monkeypatch):
    r = fakeredis.aioredis.FakeRedis(decode_responses=False)
    monkeypatch.setattr(cfg, "redis_client", r)
    return r


async def test_get_config_retorna_defaults_quando_vazio(fake_redis):
    c = await cfg.get_config()
    assert c["buffer_segundos"] == 6
    assert c["bloqueio_humano_min"] == 15
    assert c["system_prompt"]  # não vazio
    assert "cadastrar" in c["tools_descricao"]
    # tools_ativas vem por padrão com tudo ligado
    assert c["tools_ativas"]["cadastrar"] is True
    assert c["tools_ativas"]["desmarcar"] is True


async def test_set_config_tools_ativas_merge(fake_redis):
    await cfg.set_config({"tools_ativas": {"desmarcar": False}})
    c = await cfg.get_config()
    assert c["tools_ativas"]["desmarcar"] is False
    # demais tools continuam ligadas (merge, não substituição)
    assert c["tools_ativas"]["cadastrar"] is True


async def test_set_config_rejeita_tools_ativas_nao_bool(fake_redis):
    with pytest.raises(ValueError):
        await cfg.set_config({"tools_ativas": {"cadastrar": "sim"}})


async def test_set_config_grava_e_persiste(fake_redis):
    await cfg.set_config({"buffer_segundos": 8})
    c = await cfg.get_config()
    assert c["buffer_segundos"] == 8
    # campos não enviados continuam no padrão
    assert c["bloqueio_humano_min"] == 15


async def test_set_config_rejeita_fora_da_faixa(fake_redis):
    with pytest.raises(ValueError):
        await cfg.set_config({"buffer_segundos": 0})
    with pytest.raises(ValueError):
        await cfg.set_config({"bloqueio_humano_min": 999})


async def test_set_config_rejeita_prompt_vazio(fake_redis):
    with pytest.raises(ValueError):
        await cfg.set_config({"system_prompt": "   "})
