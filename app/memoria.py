"""Histórico de mensagens por número, armazenado no Postgres via LangChain."""
import asyncio

from langchain_community.chat_message_histories import PostgresChatMessageHistory
from langchain_core.messages import AIMessage, HumanMessage

from app.clientes import POSTGRES_CONN
from app.config import get_config


async def inserir_na_memoria(number: str, texto: str, role: str = "human"):
    """Salva uma mensagem isolada no histórico (ex: mensagem do atendente humano)."""
    if not texto.strip():
        return

    def _inserir():
        hist = PostgresChatMessageHistory(
            connection_string=POSTGRES_CONN,
            session_id=f"{number}_chat",
        )
        msg = HumanMessage(content=texto) if role == "human" else AIMessage(content=texto)
        hist.add_message(msg)

    await asyncio.to_thread(_inserir)


async def carregar_historico(number: str) -> list:
    """
    Carrega o histórico do Postgres e fatia para o limite configurado.
    Garante que começa numa mensagem humana (mantém pares).
    """
    limite = (await get_config())["historico_max"]

    def _carregar():
        hist = PostgresChatMessageHistory(
            connection_string=POSTGRES_CONN, session_id=f"{number}_chat",
        )
        msgs = hist.messages
        if len(msgs) > limite:
            msgs = msgs[-limite:]
            if msgs and isinstance(msgs[0], AIMessage):
                msgs = msgs[1:]
        return msgs

    return await asyncio.to_thread(_carregar)


async def salvar_par_conversa(number: str, pergunta: str, resposta: str):
    """Salva o par pergunta/resposta após o agente responder."""
    def _salvar():
        hist = PostgresChatMessageHistory(
            connection_string=POSTGRES_CONN, session_id=f"{number}_chat",
        )
        hist.add_message(HumanMessage(content=pergunta))
        hist.add_message(AIMessage(content=resposta))

    await asyncio.to_thread(_salvar)
