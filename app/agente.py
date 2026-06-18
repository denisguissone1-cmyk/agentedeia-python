import asyncio
import logging
from datetime import datetime

import pytz
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from app import clientes
from app.config import get_config
from app.memoria import carregar_historico, salvar_par_conversa
from app.tools import montar_tools

logger = logging.getLogger(__name__)


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

    agora = datetime.now(pytz.timezone("America/Sao_Paulo"))
    status = "Cliente conhecido" if cadastro.get("nomeusuario") else "Primeiro Contato"
    nome   = cadastro.get("nomeusuario") or "Ainda não foi fornecido"
    payload = {
        "mensagem": texto_completo,
        "historico": mensagens_historico,
        # Identidade/marca — o prompt pode usar {nome_agente} e {nome_marca} para
        # uma mesma base servir vários clientes do mesmo nicho.
        "nome_agente": cfg.get("nome_agente", "Agente"),
        "nome_marca": cfg.get("nome_marca", "Agente IA"),
        # Nomes neutros usados pelo prompt-base genérico.
        "status_contato": status,
        "nome_contato": nome,
        # Aliases legados: prompts antigos (ex.: Sofia em produção) usam estes nomes.
        # Mantidos para não quebrar agentes cujo prompt salvo ainda os referencia.
        "status_paciente": status,
        "nome_paciente": nome,
        "data_hora": agora.strftime("%H:%M - %A - %d/%m/%Y"),
        "numero": number.split("@")[0],
    }

    # Tenta o modelo principal; se falhar (modelo indisponível, erro da API), usa o fallback.
    llms = [m for m in (clientes.llm, clientes.llm_fallback) if m is not None]
    if not llms:
        raise RuntimeError("Nenhum modelo Gemini configurado (defina a Google API Key)")

    ultimo_erro: Exception | None = None
    for i, modelo in enumerate(llms):
        try:
            agente   = create_tool_calling_agent(modelo, tools, prompt)
            executor = AgentExecutor(agent=agente, tools=tools, verbose=False)
            resposta = await asyncio.wait_for(
                executor.ainvoke(payload), timeout=cfg["agent_timeout_seg"]
            )
            saida = resposta["output"]
            if isinstance(saida, list):
                texto_resposta = "".join(
                    b.get("text", "") for b in saida
                    if isinstance(b, dict) and b.get("type") == "text"
                ).strip()
            else:
                texto_resposta = saida
            await salvar_par_conversa(number, texto_completo, texto_resposta)
            return texto_resposta
        except Exception as exc:
            ultimo_erro = exc
            if i + 1 < len(llms):
                logger.warning(f"[{number}] Modelo principal falhou ({exc}); tentando fallback")
            continue

    raise ultimo_erro
