"""Registry de tools: monta a lista injetando as descrições do config.

Para adicionar uma tool nova: crie app/tools/minha_tool.py com `def criar(descricao)`,
importe aqui, registre em _SEM_NUMERO (ou trate o closure como cadastrar), e adicione a
chave em TOOLS_DESCRICAO_DEFAULT no app/config.py.
"""


async def montar_tools(number: str) -> list:
    from app.tools import buscar_info, cadastrar, consultar_agenda, desmarcar, pre_marcacao
    from app.config import get_config

    cfg = await get_config()
    descricoes = cfg["tools_descricao"]
    ativas = cfg.get("tools_ativas", {})

    def _ligada(nome: str) -> bool:
        return ativas.get(nome) is not False  # ausente/True → ligada

    tools = []
    # Tools que precisam saber de qual número é a conversa (closure com number).
    if _ligada("cadastrar"):
        tools.append(cadastrar.criar(number, descricoes["cadastrar"]))
    if _ligada("pre_marcacao"):
        tools.append(pre_marcacao.criar(number, descricoes["pre_marcacao"]))
    _sem_numero = {
        "buscar_info": buscar_info,
        "consultar_agenda": consultar_agenda,
        "desmarcar": desmarcar,
    }
    for nome, modulo in _sem_numero.items():
        if _ligada(nome):
            tools.append(modulo.criar(descricoes[nome]))
    return tools
