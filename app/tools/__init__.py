"""Registry de tools: monta a lista injetando as descrições do config.

Para adicionar uma tool nova: crie app/tools/minha_tool.py com `def criar(descricao)`,
importe aqui, registre em _SEM_NUMERO (ou trate o closure como cadastrar), e adicione a
chave em TOOLS_DESCRICAO_DEFAULT no app/config.py.

Se a tool precisar de tabela própria, exponha um `SCHEMA_SQL` no topo do módulo (str ou
lista de str com CREATE TABLE IF NOT EXISTS ...). O boot roda tudo idempotente via
coletar_schemas(), então o primeiro deploy de um agente novo já cria as tabelas dele.
"""


def _modulos() -> list:
    """Todos os módulos de tool conhecidos (fonte única p/ schemas)."""
    from app.tools import buscar_info, cadastrar, consultar_agenda, desmarcar, pre_marcacao
    return [buscar_info, cadastrar, consultar_agenda, desmarcar, pre_marcacao]


def coletar_schemas() -> list:
    """DDL que cada tool declara via `SCHEMA_SQL` (str ou lista de str).

    Chamado por garantir_schema() no boot. Tools sem SCHEMA_SQL não contribuem nada.
    """
    ddl = []
    for m in _modulos():
        sql = getattr(m, "SCHEMA_SQL", None)
        if isinstance(sql, str):
            ddl.append(sql)
        elif isinstance(sql, (list, tuple)):
            ddl.extend(s for s in sql if isinstance(s, str))
    return ddl


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
