from langchain.tools import tool

from app.tools.base import GOOGLE_CALENDAR_ID, asyncio, get_calendar_service


def criar(descricao: str):
    @tool("desmarcar", description=descricao)
    async def desmarcar(event_id: str) -> str:
        def _deletar():
            service = get_calendar_service()
            service.events().delete(
                calendarId=GOOGLE_CALENDAR_ID, eventId=event_id
            ).execute()

        await asyncio.to_thread(_deletar)
        return f"Agendamento {event_id} cancelado."

    return desmarcar
