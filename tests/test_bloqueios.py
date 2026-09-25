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


async def test_bot_block_retorna_bloquear_bot(fake_redis):
    import app.bloqueios as b
    numero = "551199@c.us"
    assert await b.info_pausa_bot(numero) is None

    await b.pausar_por_bot(numero, "menu numérico de autoatendimento")

    info = await b.info_pausa_bot(numero)
    assert info["motivo"] == "menu numérico de autoatendimento"
    assert info["quando"]

    status = await b.verificar_bloqueios_rapido({
        "number": numero, "is_group": False, "human": False,
    })
    assert status == "bloquear_bot"


async def test_from_me_vence_bot_block(fake_redis):
    import app.bloqueios as b
    numero = "551199@c.us"
    await b.pausar_por_bot(numero, "suspeita de outro bot")

    status = await b.verificar_bloqueios_rapido({
        "number": numero, "is_group": False, "human": True,
    })
    assert status == "bloquear_humano_bot"


async def test_bot_block_nao_afeta_conversa_sem_pausa(fake_redis):
    import app.bloqueios as b
    status = await b.verificar_bloqueios_rapido({
        "number": "551199@c.us", "is_group": False, "human": False,
    })
    assert status == "processar"
