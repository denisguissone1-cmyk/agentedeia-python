from langchain.tools import tool

from app import produtos


def criar(descricao: str):
    @tool("listar_produtos", description=descricao)
    async def listar_produtos() -> str:
        itens = await produtos.resumo_ativos()
        if not itens:
            return "Nenhum produto disponível no momento."
        linhas = []
        for p in itens:
            preco = f" — R$ {p['preco']}" if p["preco"] else ""
            spec = f" — {p['descricao']}" if p["descricao"] else ""
            foto = " (tem fotos)" if p["tem_fotos"] else ""
            linhas.append(f"#{p['id']} {p['nome']}{preco}{spec}{foto}")
        return "Produtos disponíveis:\n" + "\n".join(linhas)

    return listar_produtos
