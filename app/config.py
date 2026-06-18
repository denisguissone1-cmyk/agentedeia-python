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

# System prompt PADRÃO genérico. Este é o template-base: um assistente neutro, sem
# domínio. Cada agente novo sobrescreve isto pelo painel (/admin/config) ou aplicando
# um preset; a config salva no Redis tem precedência sobre este default.
# Bases prontas por nicho: app/presets/ (ex.: app/presets/advogado.py).
SYSTEM_PROMPT_DEFAULT = """# PAPEL

Você é {nome_agente}, um assistente virtual de {nome_marca} que atende usuários por mensagem (WhatsApp). Seja cordial, claro e direto, com um tom natural e humano, sem ser frio ou burocrático.

# CONTEXTO

Status do contato: {status_contato}
Nome conhecido: {nome_contato}
Data/Hora: {data_hora}
Número do contato: {numero}

# TAREFA

Entenda o que o usuário precisa e responda de forma útil. Use as ferramentas disponíveis quando elas se aplicarem ao pedido do usuário.

# REGRAS

- Mensagens curtas e fluidas, adequadas a um chat. Separe parágrafos com uma linha em branco.
- Converse como uma pessoa real, não como um formulário.
- Se não tiver certeza de algo, diga com transparência e não invente informações.
- Use o nome do contato com naturalidade quando ele já for conhecido."""

# Descrições das tools (o LLM usa isto para decidir quando chamar cada uma). Genéricas
# de propósito: servem como exemplos editáveis. Versões específicas por nicho ficam nos
# presets (ex.: app/presets/advogado.py).
TOOLS_DESCRICAO_DEFAULT = {
    "cadastrar": (
        "Salva o nome do contato no banco de dados. Use SOMENTE UMA VEZ, assim que o "
        "contato informar o nome próprio dele (1 a 3 palavras). "
        "NÃO use para saudações como 'Oi' ou 'Bom dia'."
    ),
    "buscar_info": (
        "Busca informações na base de conhecimento (valores, políticas, perguntas "
        "frequentes, etc.). Use como fonte de verdade — nunca invente informações."
    ),
    "consultar_agenda": (
        "Consulta os horários disponíveis na agenda entre duas datas (after, before em "
        "ISO 8601). SEMPRE use ANTES de pre_marcacao para evitar conflitos de horário."
    ),
    "pre_marcacao": (
        "Registra um agendamento na agenda (start, end, summary, description). SEMPRE use "
        "consultar_agenda antes para evitar conflitos de horário."
    ),
    "desmarcar": (
        "Cancela um agendamento pelo event_id. Use consultar_agenda antes para obter o ID "
        "correto. Acione somente após confirmação explícita do contato."
    ),
    "listar_produtos": (
        "Consulta os produtos disponíveis (ativos) no catálogo da loja: nome, preço e "
        "especificações. Use para saber o que há disponível e responder o cliente. "
        "Cada produto tem um número (#id) usado para enviar as fotos."
    ),
    "enviar_fotos_produto": (
        "Envia as fotos de um produto para o cliente. Recebe produto_id (o #id do "
        "listar_produtos). Use quando o cliente pedir para ver as fotos de um produto."
    ),
}

# Estado (ligada/desligada) de cada tool. O painel inverte; montar_tools respeita.
# Template-base: só `cadastrar` (captura de nome, útil em qualquer agente) vem ligada.
# As demais ficam DESATIVADAS — os arquivos continuam no repo como exemplos; você liga
# o que precisar por agente, no painel.
TOOLS_ATIVAS_DEFAULT = {
    "cadastrar": True,
    "buscar_info": False,
    "consultar_agenda": False,
    "pre_marcacao": False,
    "desmarcar": False,
    "listar_produtos": False,
    "enviar_fotos_produto": False,
}

DEFAULTS = {
    # Identidade/marca exibida no painel (editável em /admin/config).
    "nome_agente": "Agente",
    "nome_marca": "Agente IA",
    # Base (preset) atualmente ativa — vazio = config personalizada (nenhum preset aplicado).
    "preset_ativo": "",
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
    for campo in ("nome_agente", "nome_marca"):
        if campo in parcial and not str(parcial[campo]).strip():
            raise ValueError(f"{campo} não pode ser vazio")
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


async def semear_preset_se_vazio() -> None:
    """No 1º boot, se não há config no Redis e AGENTE_PRESET aponta um preset válido,
    aplica esse preset. Provisionamento zero-toque: subir com AGENTE_PRESET=advogado já
    deixa o agente como advogado. Nunca derruba o boot."""
    nome = (os.getenv("AGENTE_PRESET") or "").strip()
    if not nome:
        return
    try:
        from app import presets
        if await redis_client.exists(CONFIG_KEY):
            return  # já configurado — respeita o que está no painel
        if nome not in presets.listar():
            return
        cfg = presets.carregar(nome)
        cfg["preset_ativo"] = nome
        await set_config(cfg)
    except Exception:
        pass


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
