from langchain.tools import tool

from app.tools.base import asyncio, get_calendar_id, get_calendar_service, proteger_agenda


def criar(descricao: str):
    @tool("desmarcar", description=descricao)
    @proteger_agenda("desmarcar")
    async def desmarcar(event_id: str) -> str:
        def _deletar():
            service = get_calendar_service()
            service.events().delete(
                calendarId=get_calendar_id(), eventId=event_id
            ).execute()

        await asyncio.to_thread(_deletar)
        return f"Agendamento {event_id} cancelado."

    return desmarcar
