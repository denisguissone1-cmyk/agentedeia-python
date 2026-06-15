from langchain.tools import tool

from app.clientes import supabase_client
from app.tools.base import asyncio


def criar(number: str, descricao: str):
    @tool("cadastrar", description=descricao)
    async def cadastrar(nome: str) -> str:
        def _executar():
            return (
                supabase_client.table("cadastro")
                .update({"nomeusuario": nome.strip().title()})
                .eq("remoteJid", number)
                .execute()
            )
        await asyncio.to_thread(_executar)
        return f"Nome '{nome.strip().title()}' salvo com sucesso."

    return cadastrar
