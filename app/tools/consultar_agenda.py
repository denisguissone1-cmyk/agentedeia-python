import json

from langchain.tools import tool

from app.tools.base import asyncio, get_calendar_id, get_calendar_service, proteger_agenda


def criar(descricao: str):
    @tool("consultar_agenda", description=descricao)
    @proteger_agenda("consultar_agenda")
    async def consultar_agenda(after: str, before: str) -> str:
        def _consultar():
            service = get_calendar_service()
            result = service.events().list(
                calendarId=get_calendar_id(), timeMin=after, timeMax=before,
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
