from langchain.tools import tool

from app import eventos
from app.tools.base import asyncio, get_calendar_id, get_calendar_service, proteger_agenda


def criar(number: str, descricao: str):
    @tool("pre_marcacao", description=descricao)
    @proteger_agenda("pre_marcacao")
    async def pre_marcacao(start: str, end: str, summary: str, description: str) -> str:
        def _criar():
            service = get_calendar_service()
            evento = {
                "summary": summary,
                "description": description,
                "start": {"dateTime": start, "timeZone": "America/Sao_Paulo"},
                "end": {"dateTime": end, "timeZone": "America/Sao_Paulo"},
            }
            return service.events().insert(
                calendarId=get_calendar_id(), body=evento
            ).execute()

        resultado = await asyncio.to_thread(_criar)
        await eventos.agendamento(number, urgente="URGENTE" in (summary or "").upper())
        return f"Pré-marcação criada com ID {resultado.get('id')}."

    return pre_marcacao
