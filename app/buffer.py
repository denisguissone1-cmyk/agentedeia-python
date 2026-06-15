"""Buffer com debounce deslizante: agrupa mensagens rápidas em um único processamento.

A cada nova mensagem, o token de atividade é sobrescrito.
Apenas a chamada que mantiver o token por `buffer_segundos` em silêncio processa o lote.
"""
import asyncio
import time
from typing import Optional

from app.config import get_config, redis_client


async def buffer_mensagens(number: str, mensagem_json: str) -> Optional[list[str]]:
    chave_lista     = f"{number}:msgs"
    chave_atividade = f"{number}:atividade"

    await redis_client.rpush(chave_lista, mensagem_json)
    # TTL: se o servidor crashar após o RPUSH, a lista expira em vez de contaminar
    # sessões futuras do mesmo número.
    await redis_client.expire(chave_lista, 120)

    # time_ns() → resolução de nanosegundo, colisão praticamente impossível
    meu_token = str(time.time_ns())
    await redis_client.set(chave_atividade, meu_token, ex=120)

    buffer_segundos = (await get_config())["buffer_segundos"]
    await asyncio.sleep(buffer_segundos)

    # Verifica se ainda somos os "donos" do turno
    valor_salvo = await redis_client.get(chave_atividade)
    if not valor_salvo or valor_salvo.decode() != meu_token:
        return None  # outra mensagem chegou depois — descarta

    mensagens_raw = await redis_client.lrange(chave_lista, 0, -1)
    await redis_client.delete(chave_lista)
    return [m.decode() for m in mensagens_raw]
