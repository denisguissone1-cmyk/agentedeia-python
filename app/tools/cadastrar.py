from langchain.tools import tool

from app.clientes import get_db_conn
from app.tools.base import asyncio


def criar(number: str, descricao: str):
    @tool("cadastrar", description=descricao)
    async def cadastrar(nome: str) -> str:
        def _executar():
            conn = get_db_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        'UPDATE cadastro SET nomeusuario = %s WHERE "remoteJid" = %s',
                        (nome.strip().title(), number)
                    )
                conn.commit()
            finally:
                conn.close()
        await asyncio.to_thread(_executar)
        return f"Nome '{nome.strip().title()}' salvo com sucesso."

    return cadastrar
