import asyncio
from datetime import datetime

import pytz
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from app import clientes
from app.config import get_config
from app.memoria import carregar_historico, salvar_par_conversa
from app.tools import montar_tools


async def chamar_agente(number: str, texto_completo: str, cadastro: dict) -> str:
    cfg = await get_config()
    mensagens_historico = await carregar_historico(number)
    tools = await montar_tools(number)

    prompt = ChatPromptTemplate.from_messages([
        ("system", cfg["system_prompt"]),
        MessagesPlaceholder(variable_name="historico"),
        ("human", "{mensagem}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    agente   = create_tool_calling_agent(clientes.llm, tools, prompt)
    executor = AgentExecutor(agent=agente, tools=tools, verbose=False)

    agora = datetime.now(pytz.timezone("America/Sao_Paulo"))
    resposta = await asyncio.wait_for(
        executor.ainvoke({
            "mensagem": texto_completo,
            "historico": mensagens_historico,
            "status_paciente": "Cliente conhecido" if cadastro.get("nomeusuario") else "Primeiro Contato",
            "nome_paciente": cadastro.get("nomeusuario") or "Ainda não foi fornecido",
            "data_hora": agora.strftime("%H:%M - %A - %d/%m/%Y"),
            "numero": number.split("@")[0],
        }),
        timeout=cfg["agent_timeout_seg"],
    )

    texto_resposta = resposta["output"]
    await salvar_par_conversa(number, texto_completo, texto_resposta)
    return texto_resposta
