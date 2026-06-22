"""Helpers compartilhados pelas tools."""
import asyncio
import functools
import logging

from app import clientes
from app.clientes import get_calendar_service

logger = logging.getLogger(__name__)


def get_calendar_id() -> str:
    """ID da agenda configurado no painel (atualizado em refresh_clients). Lido a cada
    chamada para refletir mudanças sem restart. 'primary' como último recurso."""
    return clientes.GOOGLE_CALENDAR_ID or "primary"

# Mensagem que a tool devolve ao agente quando a agenda falha. O agente lê isso como
# resultado da ferramenta e responde com naturalidade, sem vazar erro técnico pro cliente.
ERRO_AGENDA = (
    "[ferramenta de agenda indisponível no momento] Não foi possível acessar a agenda. "
    "Não invente horários: peça desculpas pela instabilidade e diga que um atendente "
    "confirma o agendamento em seguida."
)


def proteger_agenda(nome: str):
    """Decorator: captura qualquer erro da tool de agenda e devolve ERRO_AGENDA ao agente,
    em vez de propagar a exceção (que abortaria o turno inteiro do agente)."""
    def wrap(fn):
        @functools.wraps(fn)
        async def inner(*args, **kwargs):
            try:
                return await fn(*args, **kwargs)
            except Exception as exc:
                logger.warning(f"Tool '{nome}' falhou: {type(exc).__name__}: {exc}")
                return ERRO_AGENDA
        return inner
    return wrap


__all__ = ["asyncio", "get_calendar_id", "get_calendar_service", "ERRO_AGENDA", "proteger_agenda"]
