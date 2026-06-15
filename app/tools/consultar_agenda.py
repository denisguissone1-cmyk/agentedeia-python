import json

from langchain.tools import tool

from app.tools.base import GOOGLE_CALENDAR_ID, asyncio, get_calendar_service


def criar(descricao: str):
    @tool("consultar_agenda", description=descricao)
    async def consultar_agenda(after: str, before: str) -> str:
        def _consultar():
            service = get_calendar_service()
            result = service.events().list(
                calendarId=GOOGLE_CALENDAR_ID, timeMin=after, timeMax=before,
                timeZone="America/Sao_Paulo", singleEvents=True, orderBy="startTime",
            ).execute()
            return result.get("items", [])

        eventos = await asyncio.to_thread(_consultar)
        return json.dumps(
            [
                {
                    "id": e.get("id"),
                    "summary": e.get("summary", ""),
                    "start": e["start"].get("dateTime", e["start"].get("date")),
                    "end": e["end"].get("dateTime", e["end"].get("date")),
                }
                for e in eventos
            ],
            ensure_ascii=False,
        )

    return consultar_agenda
