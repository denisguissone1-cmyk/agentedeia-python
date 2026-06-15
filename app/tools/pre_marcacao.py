from langchain.tools import tool

from app.tools.base import GOOGLE_CALENDAR_ID, asyncio, get_calendar_service


def criar(descricao: str):
    @tool("pre_marcacao", description=descricao)
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
                calendarId=GOOGLE_CALENDAR_ID, body=evento
            ).execute()

        resultado = await asyncio.to_thread(_criar)
        return f"Pré-marcação criada com ID {resultado.get('id')}."

    return pre_marcacao
