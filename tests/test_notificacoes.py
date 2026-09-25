import json

import fakeredis.aioredis
import pytest

from app import config as cfg


@pytest.fixture
def fake_redis(monkeypatch):
    r = fakeredis.aioredis.FakeRedis(decode_responses=False)
    monkeypatch.setattr(cfg, "redis_client", r)
    import app.eventos as ev
    import app.notificacoes as N
    monkeypatch.setattr(ev, "redis_client", r)
    monkeypatch.setattr(N, "redis_client", r)
    return r


async def test_notificar_grava_e_listar(fake_redis):
    from app import notificacoes as N
    await N.notificar("Possível bot detectado", "Pausei a conversa com Fulano", tipo="bot_detectado", numero="551199@c.us")
    itens = await N.listar()
    assert len(itens) == 1
    assert itens[0]["titulo"] == "Possível bot detectado"
    assert itens[0]["tipo"] == "bot_detectado"
    assert itens[0]["numero"] == "551199@c.us"
    assert itens[0]["id"]
    assert itens[0]["quando"]


async def test_nao_lidas_e_marcar_lidas(fake_redis):
    from app import notificacoes as N
    assert await N.nao_lidas() == 0

    await N.notificar("Título 1", "Texto 1")
    await N.notificar("Título 2", "Texto 2")
    assert await N.nao_lidas() == 2

    await N.marcar_lidas()
    assert await N.nao_lidas() == 0

    await N.notificar("Título 3", "Texto 3")
    assert await N.nao_lidas() == 1


async def test_dedupe_ttl_suprime_repeticao(fake_redis):
    from app import notificacoes as N
    numero = "551199@c.us"
    await N.notificar("Atendente humano assumiu", "Conversa pausada", tipo="humano_assumiu",
                       numero=numero, dedupe_ttl=900)
    await N.notificar("Atendente humano assumiu", "Conversa pausada de novo", tipo="humano_assumiu",
                       numero=numero, dedupe_ttl=900)
    itens = await N.listar()
    assert len(itens) == 1


async def test_dedupe_ttl_nao_suprime_numeros_diferentes(fake_redis):
    from app import notificacoes as N
    await N.notificar("Atendente humano assumiu", "x", tipo="humano_assumiu",
                       numero="551199@c.us", dedupe_ttl=900)
    await N.notificar("Atendente humano assumiu", "x", tipo="humano_assumiu",
                       numero="552288@c.us", dedupe_ttl=900)
    itens = await N.listar()
    assert len(itens) == 2


async def test_notificar_espelha_no_feed_de_eventos(fake_redis):
    from app import notificacoes as N
    await N.notificar("Possível bot detectado", "motivo aqui", tipo="bot_detectado", numero="551199@c.us")

    raw = await fake_redis.lrange("eventos:recentes", 0, -1)
    eventos = [json.loads(x) for x in raw]
    assert len(eventos) == 1
    assert eventos[0]["filtro"] == "notificacao"
    assert eventos[0]["cor"] == "e-red"
    assert "Possível bot detectado" in eventos[0]["texto"]


async def test_notificar_nunca_levanta_excecao_com_redis_fora_do_ar(monkeypatch):
    import app.notificacoes as N

    class RedisQuebrado:
        async def set(self, *a, **k):
            raise ConnectionError("redis fora do ar")

        async def lpush(self, *a, **k):
            raise ConnectionError("redis fora do ar")

    monkeypatch.setattr(N, "redis_client", RedisQuebrado())
    await N.notificar("Título", "Texto")  # não deve levantar
