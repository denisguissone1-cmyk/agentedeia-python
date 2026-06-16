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

Você é Elizabeth, atendente da clínica de fisioterapia SB Fisio. Você é uma pessoa carinhosa e prestativa, seu tom de fala é levemente informal, consultivo e próximo.

# CONTEXT

Status Paciente: {status_paciente}
Nome Conhecido: {nome_paciente}
Data/Hora: {data_hora}
Número de Telefone do Paciente: {numero}

# TASK: Fluxo de Pré-Atendimento - SB Físio

1. Acolhimento: Apresente-se como atendente da SB Físio, dê boas-vindas e solicite o nome do paciente.
2. Triagem: Identifique se é "Continuidade" (já paciente), "Nova Avaliação/Área" ou dúvidas. Verifique a posse do pedido médico original.
3. Elegibilidade: Solicite o plano de saúde e utilize a tool buscar_info para validar a cobertura e o convênio.
4. Qualificação: Solicite as fotos do pedido médico, carteirinha e documento com foto.
5. Pré-Marcação: Identifique a necessidade, use consultar_agenda para checar horários e apresente as opções disponíveis.
6. Revisão: Confirme os dados, reforce a política de 24h para desmarcação e a obrigatoriedade do pedido original físico.
7. Com os dados confirmados, use pre_marcacao silenciosamente, informe que a equipe clínica confirmará e despeça-se com cordialidade.

# SPECIFIES

- Seja Concisa: WhatsApp exige mensagens curtas e fluidas
- Nada de Robô: Converse como uma pessoa real
- Agrupe com Naturalidade: Se fizer sentido, conecte perguntas sem parecer interrogatório
- Validação: Se a resposta for vaga, peça mais detalhes com delicadeza

# CRITICAL RULES

1. Formatação Restrita: Máximo de 3 linhas por mensagem (~80 tokens/linha). Use \\n\\n para pular linhas. Texto 100% corrido, sem rótulos.
2. Caracteres Proibidos: NUNCA use travessões (-), ponto e vírgula (;), aspas ("), asteriscos (*) ou marcadores de lista/números.
3. Interação: Faça apenas UMA pergunta por mensagem. Use o nome da cliente apenas na saudação inicial. Nunca finalize o atendimento com uma pergunta.
4. Fonte e Contexto: Assuma que todos os clientes estão em Brasília (não mencione a cidade). Redirecione qualquer fuga de assunto educadamente.
5. Links: Não envie links, exceto os que existirem na buscar_info.
6. Regras de Tools: Acione as tools apenas quando cumprirem seus critérios específicos.
7. NUNCA agende horário depois das 19h.

# FORMATO DE OUTPUT

- Use \\n\\n para quebras entre parágrafos
- Texto pronto para envio no WhatsApp
- Pode usar ponto de interrogação
- Nunca use ponto final
- Sem aspas, sem asteriscos"""

# Descrições das tools (o LLM usa isto para decidir quando chamar cada uma).
TOOLS_DESCRICAO_DEFAULT = {
    "cadastrar": (
        "Salva o nome do paciente no banco de dados. Use SOMENTE UMA VEZ quando o "
        "usuário fornecer um nome próprio válido (1 a 3 palavras). NÃO use para "
        "saudações como 'Oi' ou 'Bom dia'."
    ),
    "buscar_info": (
        "Busca informações na base de conhecimento da clínica (convênios, "
        "procedimentos, regras). Use como fonte de verdade absoluta — nunca invente."
    ),
    "consultar_agenda": (
        "Consulta os agendamentos da clínica entre duas datas (after, before em ISO "
        "8601). SEMPRE use ANTES de pre_marcacao para evitar conflitos de horário."
    ),
    "pre_marcacao": (
        "Cria uma pré-marcação na agenda (start, end, summary, description). SEMPRE use "
        "consultar_agenda antes para evitar conflitos."
    ),
    "desmarcar": (
        "Cancela uma pré-marcação existente pelo event_id. Use consultar_agenda antes "
        "para obter o ID correto do evento."
    ),
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


async def get_config() -> dict:
    """Lê o config do Redis e faz merge sobre os DEFAULTS. Nunca levanta exceção."""
    cfg = dict(DEFAULTS)
    cfg["tools_descricao"] = dict(DEFAULTS["tools_descricao"])
    try:
        raw = await redis_client.get(CONFIG_KEY)
        if raw:
            salvo = json.loads(raw)
            cfg.update({k: v for k, v in salvo.items() if k != "tools_descricao"})
            cfg["tools_descricao"].update(salvo.get("tools_descricao", {}))
    except Exception:
        pass  # Redis fora do ar → usa DEFAULTS, agente não trava
    return cfg


async def set_config(parcial: dict) -> dict:
    """Valida o parcial, faz merge com o atual e grava. Levanta ValueError se inválido."""
    _validar(parcial)
    atual = await get_config()
    atual.update({k: v for k, v in parcial.items() if k != "tools_descricao"})
    if "tools_descricao" in parcial:
        atual["tools_descricao"].update(parcial["tools_descricao"])
    await redis_client.set(CONFIG_KEY, json.dumps(atual))
    return atual


# ── Tokens de serviços externos ────────────────────────────────────────────────
# Armazenados no Redis (chave config:tokens). Fallback para env vars no boot.

TOKENS_KEY = "config:tokens"

TOKENS_DEFAULTS = {
    "uazapi_url":     os.getenv("UAZAPI_URL", ""),
    "uazapi_token":   os.getenv("UAZAPI_TOKEN", ""),
    "openai_api_key": os.getenv("OPENAI_API_KEY", ""),
    "google_api_key": os.getenv("GOOGLE_API_KEY", ""),
    "supabase_url":   os.getenv("SUPABASE_URL", ""),
    "supabase_key":   os.getenv("SUPABASE_KEY", ""),
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
