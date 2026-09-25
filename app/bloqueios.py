"""Lógica de bloqueio: grupos, atendente humano assumindo, rate limit, detecção de bot."""
import json
import logging
from datetime import datetime

import pytz

from app.config import get_config, redis_client

logger = logging.getLogger(__name__)
_TZ = pytz.timezone("America/Sao_Paulo")


async def ja_processada(number: str, id_msg: str) -> bool:
    """
    Chave inclui `number` para evitar colisão entre instâncias diferentes.
    Marca a mensagem como processada por 60 segundos.
    """
    if not id_msg:
        return False
    nova = await redis_client.set(f"msg_seen:{number}:{id_msg}", "1", ex=60, nx=True)
    return nova is None  # None = chave já existia = duplicata


async def verifica_rate_limit(number: str) -> str:
    """
    Retorna o status do rate limit para o número.

    Retorna:
      "ok"        → dentro do limite, processa normalmente
      "aviso"     → primeiro bloqueio — avisa o usuário uma vez
      "bloqueado" → silenciosamente ignora mensagens excedentes
    """
    cfg = await get_config()
    rate_max, janela = cfg["rate_limit_max"], cfg["rate_limit_janela"]
    chave = f"ratelimit:{number}"
    contador = await redis_client.incr(chave)
    if contador == 1:
        await redis_client.expire(chave, janela)
    if contador <= rate_max:
        return "ok"
    elif contador == rate_max + 1:
        return "aviso"
    return "bloqueado"


async def pausar_por_bot(number: str, motivo: str) -> None:
    """Pausa permanente (sem TTL) por suspeita de outro bot. Só um humano despausa
    (app/painel/api.py despausar apaga esta chave e {number}_block)."""
    quando = datetime.now(_TZ).strftime("%d/%m/%Y %H:%M")
    await redis_client.set(
        f"{number}_bot_block",
        json.dumps({"motivo": motivo, "quando": quando}, ensure_ascii=False),
    )


async def info_pausa_bot(number: str) -> dict | None:
    """None se a conversa não está pausada por bot; senão {"motivo", "quando"}."""
    raw = await redis_client.get(f"{number}_bot_block")
    if not raw:
        return None
    try:
        d = json.loads(raw)
        return d if isinstance(d, dict) else {"motivo": "", "quando": ""}
    except Exception:
        return {"motivo": "", "quando": ""}


async def verificar_bloqueios_rapido(dados: dict) -> str:
    number = dados["number"]

    if dados.get("is_group"):
        return "bloquear_wpp"

    # fromMe pode chegar como bool True, string "true", int 1 — bool() cobre todos
    if bool(dados["human"]) and dados["human"] not in (False, "false", "False", 0):
        minutos = (await get_config())["bloqueio_humano_min"]
        await redis_client.set(f"{number}_block", "true", ex=minutos * 60)
        return "bloquear_humano_bot"

    block_wpp = await redis_client.get("block_wpp")
    if block_wpp == b"true":
        return "bloquear_wpp"

    if await redis_client.get(f"{number}_bot_block"):
        return "bloquear_bot"

    block_individual = await redis_client.get(f"{number}_block")
    if block_individual == b"true":
        return "bloquear_individual"

    return "processar"
