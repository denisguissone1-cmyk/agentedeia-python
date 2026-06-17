"""Configuração ao vivo do agente, guardada no Redis (chave config:agente).

get_config() é lido a cada mensagem — mudanças feitas no painel valem na hora.
Se o Redis estiver indisponível ou a chave não existir, cai nos DEFAULTS.
"""
import json
import os

import redis.asyncio as aioredis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
redis_client = aioredis.from_url(REDIS_URL, decode_responses=False)

CONFIG_KEY = "config:agente"

# System prompt completo da Elizabeth (idêntico ao do monólito original).
# Mantido aqui como padrão editável pelo painel.
SYSTEM_PROMPT_DEFAULT = """# ROLE

Você é Sofia, atendente do escritório Leal & Associados Advocacia. Você é uma pessoa cordial e atenciosa, seu tom de fala é levemente informal, acolhedor e profissional, sem ser frio ou burocrático.

# CONTEXT

Status Cliente: {status_paciente}
Nome Conhecido: {nome_paciente}
Data/Hora: {data_hora}
Número de Telefone do Cliente: {numero}

# TASK: Fluxo de Triagem Jurídica - Leal & Associados

1. Acolhimento: Apresente-se como atendente do escritório Leal & Associados, dê boas-vindas e solicite o nome da pessoa.
2. Área Jurídica: Identifique a área envolvida, trabalhista, família, consumidor, previdenciário, criminal, cível ou imobiliário, perguntando sobre o assunto de forma aberta e acolhedora.
3. Qualificação: Compreenda a situação com perguntas simples: se há urgência ou prazo iminente, o que aconteceu em linhas gerais e se a pessoa já tentou resolver de outra forma.
4. Documentos: Pergunte quais documentos a pessoa tem disponíveis relacionados ao caso (contratos, notificações, decisões, fotos, prints, etc) e oriente a separar o que tiver.
5. Opções de Consulta: Utilize a tool buscar_info para informar o valor da consulta inicial e apresente as opções de atendimento presencial ou online, conforme disponibilidade.
6. Agendamento: Use consultar_agenda para verificar horários disponíveis e apresente as opções. Confirme a preferência da pessoa e utilize pre_marcacao para registrar.
7. Confirmação: Confirme os dados do agendamento, informe que um advogado do escritório confirmará em breve e despeça-se com cordialidade.

# SPECIFIES

- Seja Concisa: WhatsApp exige mensagens curtas e fluidas
- Nada de Robô: Converse como uma pessoa real, não como um formulário
- Agrupe com Naturalidade: Se fizer sentido, conecte perguntas sem parecer interrogatório
- Validação: Se a resposta for vaga, peça mais detalhes com delicadeza
- Urgência: Se a pessoa mencionar prazo para amanhã, prisão, liminar, bloqueio judicial ou qualquer situação de urgência extrema, priorize o agendamento mais próximo disponível e informe que a equipe será avisada com prioridade
- Sigilo: Não peça detalhes desnecessários do caso, apenas o suficiente para a triagem. O aprofundamento é papel do advogado na consulta

# CRITICAL RULES

1. Formatação Restrita: Máximo de 3 linhas por mensagem (~80 tokens/linha). Use \\n\\n para pular linhas. Texto 100% corrido, sem rótulos.
2. Caracteres Proibidos: NUNCA use travessões (-), ponto e vírgula (;), aspas ("), asteriscos (*) ou marcadores de lista/números.
3. Interação: Faça apenas UMA pergunta por mensagem. Use o nome do cliente apenas na saudação inicial. Nunca finalize o atendimento com uma pergunta.
4. Fonte e Contexto: Redirecione qualquer fuga de assunto educadamente de volta ao atendimento.
5. Links: Não envie links, exceto os que existirem na buscar_info.
6. Regras de Tools: Acione as tools apenas quando cumprirem seus critérios específicos.
7. NUNCA agende horários depois das 19h.
8. NUNCA dê parecer jurídico, opine sobre chances de êxito, analise mérito ou diga se a pessoa "tem razão" ou "vai ganhar". Se solicitado, redirecione com naturalidade para a consulta com o advogado responsável.
9. NUNCA cite leis, artigos, prazos legais ou estratégias jurídicas. Qualquer pergunta desse tipo deve ser redirecionada para a consulta.
10. Consulta Inicial: A consulta inicial tem valor fixo conforme informado pela buscar_info. Não invente valores nem afirme gratuidade.

# FORMATO DE OUTPUT

- Use \\n\\n para quebras entre parágrafos
- Texto pronto para envio no WhatsApp
- Pode usar ponto de interrogação
- Nunca use ponto final
- Sem aspas, sem asteriscos"""

# Descrições das tools (o LLM usa isto para decidir quando chamar cada uma).
TOOLS_DESCRICAO_DEFAULT = {
    "cadastrar": (
        "Salva o nome do cliente no banco de dados do escritório. Use SOMENTE UMA VEZ "
        "assim que o cliente informar o nome próprio válido (1 a 3 palavras). "
        "NÃO use para saudações como 'Oi' ou 'Bom dia'."
    ),
    "buscar_info": (
        "Busca informações na base de conhecimento do escritório Leal & Associados: "
        "valor da consulta inicial, áreas de atuação, documentos recomendados por área "
        "jurídica, política de atendimento presencial e online, perguntas frequentes. "
        "Use como fonte de verdade absoluta — nunca invente valores ou informações."
    ),
    "consultar_agenda": (
        "Consulta os horários disponíveis na agenda do escritório para agendamento de "
        "consulta jurídica entre duas datas (after, before em ISO 8601). "
        "SEMPRE use ANTES de pre_marcacao para evitar conflitos de horário."
    ),
    "pre_marcacao": (
        "Registra o agendamento de uma consulta jurídica na agenda (start, end, summary, "
        "description). SEMPRE use consultar_agenda antes para evitar conflitos. "
        "No summary, inclua 'URGENTE' se o cliente relatou urgência extrema. "
        "No description, registre a área jurídica, modalidade e documentos mencionados."
    ),
    "desmarcar": (
        "Cancela uma consulta jurídica pelo event_id. Use consultar_agenda antes para "
        "obter o ID correto. Acione somente após confirmação explícita do cliente."
    ),
}

# Estado (ligada/desligada) de cada tool. O painel inverte; montar_tools respeita.
TOOLS_ATIVAS_DEFAULT = {
    "cadastrar": True,
    "buscar_info": True,
    "consultar_agenda": True,
    "pre_marcacao": True,
    "desmarcar": True,
}

DEFAULTS = {
    "buffer_segundos": 6,
    "bloqueio_humano_min": 15,
    "rate_limit_max": 30,
    "rate_limit_janela": 60,
    "historico_max": 40,
    "agent_timeout_seg": 30,
    "system_prompt": SYSTEM_PROMPT_DEFAULT,
    "tools_descricao": dict(TOOLS_DESCRICAO_DEFAULT),
    "tools_ativas": dict(TOOLS_ATIVAS_DEFAULT),
}

# Faixas válidas para os campos numéricos: (min, max).
_FAIXAS = {
    "buffer_segundos": (1, 60),
    "bloqueio_humano_min": (1, 120),
    "rate_limit_max": (1, 500),
    "rate_limit_janela": (5, 600),
    "historico_max": (2, 200),
    "agent_timeout_seg": (5, 120),
}


def _validar(parcial: dict) -> None:
    for campo, (lo, hi) in _FAIXAS.items():
        if campo in parcial:
            v = parcial[campo]
            if not isinstance(v, int) or isinstance(v, bool) or not (lo <= v <= hi):
                raise ValueError(f"{campo} deve ser inteiro entre {lo} e {hi}")
    if "system_prompt" in parcial and not str(parcial["system_prompt"]).strip():
        raise ValueError("system_prompt não pode ser vazio")
    if "tools_descricao" in parcial:
        td = parcial["tools_descricao"]
        if not isinstance(td, dict):
            raise ValueError("tools_descricao deve ser um objeto")
        for nome, desc in td.items():
            if not str(desc).strip():
                raise ValueError(f"descrição da tool '{nome}' não pode ser vazia")
    if "tools_ativas" in parcial:
        ta = parcial["tools_ativas"]
        if not isinstance(ta, dict):
            raise ValueError("tools_ativas deve ser um objeto")
        for nome, estado in ta.items():
            if not isinstance(estado, bool):
                raise ValueError(f"estado da tool '{nome}' deve ser booleano")


async def get_config() -> dict:
    """Lê o config do Redis e faz merge sobre os DEFAULTS. Nunca levanta exceção."""
    cfg = dict(DEFAULTS)
    cfg["tools_descricao"] = dict(DEFAULTS["tools_descricao"])
    cfg["tools_ativas"] = dict(DEFAULTS["tools_ativas"])
    _dicts = ("tools_descricao", "tools_ativas")
    try:
        raw = await redis_client.get(CONFIG_KEY)
        if raw:
            salvo = json.loads(raw)
            cfg.update({k: v for k, v in salvo.items() if k not in _dicts})
            cfg["tools_descricao"].update(salvo.get("tools_descricao", {}))
            cfg["tools_ativas"].update(salvo.get("tools_ativas", {}))
    except Exception:
        pass  # Redis fora do ar → usa DEFAULTS, agente não trava
    return cfg


async def set_config(parcial: dict) -> dict:
    """Valida o parcial, faz merge com o atual e grava. Levanta ValueError se inválido."""
    _validar(parcial)
    atual = await get_config()
    _dicts = ("tools_descricao", "tools_ativas")
    atual.update({k: v for k, v in parcial.items() if k not in _dicts})
    if "tools_descricao" in parcial:
        atual["tools_descricao"].update(parcial["tools_descricao"])
    if "tools_ativas" in parcial:
        atual["tools_ativas"].update(parcial["tools_ativas"])
    await redis_client.set(CONFIG_KEY, json.dumps(atual))
    return atual


# ── Tokens de serviços externos ────────────────────────────────────────────────
# Armazenados no Redis (chave config:tokens). Fallback para env vars no boot.

TOKENS_KEY = "config:tokens"

TOKENS_DEFAULTS = {
    "uazapi_url":       os.getenv("UAZAPI_URL", ""),
    "uazapi_token":     os.getenv("UAZAPI_TOKEN", ""),
    "openai_api_key":   os.getenv("OPENAI_API_KEY", ""),
    "google_api_key":   os.getenv("GOOGLE_API_KEY", ""),
    "supabase_url":     os.getenv("SUPABASE_URL", ""),
    "supabase_key":     os.getenv("SUPABASE_KEY", ""),
    # Webhook de ENTRADA (UAZAPI → este app). base_url é o endereço público do app
    # (ex.: https://meu-dominio.com); a rota é sempre /webhook. token valida o POST.
    "webhook_base_url": os.getenv("WEBHOOK_BASE_URL", ""),
    "webhook_token":    os.getenv("WEBHOOK_TOKEN", ""),
    # Modelo Gemini (selecionável no painel) + fallback automático se o principal falhar.
    "gemini_model":          os.getenv("GEMINI_MODEL", "gemini-flash-latest"),
    "gemini_model_fallback": os.getenv("GEMINI_MODEL_FALLBACK", ""),
}


async def get_tokens() -> dict:
    """Lê tokens do Redis; fallback para env vars. Nunca levanta exceção."""
    tokens = dict(TOKENS_DEFAULTS)
    try:
        raw = await redis_client.get(TOKENS_KEY)
        if raw:
            salvo = json.loads(raw)
            tokens.update({k: v for k, v in salvo.items() if v and k in tokens})
    except Exception:
        pass
    return tokens


async def set_tokens(parcial: dict) -> dict:
    """Salva tokens parciais no Redis (só chaves conhecidas)."""
    atual = await get_tokens()
    atual.update({k: v for k, v in parcial.items() if k in TOKENS_DEFAULTS})
    await redis_client.set(TOKENS_KEY, json.dumps(atual))
    return atual
