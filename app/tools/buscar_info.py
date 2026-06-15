from langchain.tools import tool


def criar(descricao: str):
    @tool("buscar_info", description=descricao)
    async def buscar_info(pergunta: str) -> str:
        # TODO: substituir pelo RAG real (busca vetorial no Supabase/pgvector)
        return f"[Resultado da busca: {pergunta}]"

    return buscar_info
