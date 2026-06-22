# Painel Admin + Modularização do Agente WhatsApp — Implementation Plan

> **⚠️ Documento histórico (substituído).** Este plano descreve a construção original de um
> painel Jinja em `/admin`. Esse painel foi entregue e, depois, **substituído por um SPA
> React** (`frontend/`) servido na raiz `/` e consumindo a API JSON em `/api/*`. Os templates
> Jinja e as rotas `/admin/*` (incluindo os blocos de código abaixo) **não existem mais** —
> este arquivo permanece só como registro de implementação. Para a arquitetura atual, veja
> `AGENTS.md`.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transformar o monólito `agente_whatsapp (1).py` num pacote `app/` modular com um painel web `/admin` (login usuário+senha) que configura o agente ao vivo via Redis e mostra cada conversa separada, empacotado em Docker para deploy numa VPS.

**Architecture:** Um único serviço FastAPI roda o agente (`/webhook`) e o painel (`/admin`). Configurações ficam num JSON no Redis (`config:agente`), lido a cada mensagem — mudanças valem na hora, sem restart. O código vira módulos de responsabilidade única; cada tool é um arquivo em `app/tools/` com uma factory que recebe a descrição vinda do config.

**Tech Stack:** Python 3.12, FastAPI, Uvicorn, LangChain 0.3.x + Gemini, Redis, Postgres (Supabase), Jinja2, Starlette SessionMiddleware, pytest + fakeredis, Docker Compose.

**Premissa-chave:** O debounce deslizante do buffer **já existe** (`buffer_mensagens`). Este plano só troca a constante fixa pelo valor do config — não reescreve a lógica.

**Convenção de migração:** "mover (linhas A–B)" refere-se ao arquivo original `agente_whatsapp (1).py`. Mover = recortar a função **sem alterar a lógica**, ajustando apenas os imports. Onde houver mudança de comportamento, o passo mostra o código completo.

---

## Fase 0 — Scaffolding

### Task 1: Inicializar repositório e estrutura

**Files:**
- Create: `.gitignore`, `requirements.txt`, `requirements-dev.txt`, `pytest.ini`
- Create: `app/__init__.py`, `app/tools/__init__.py`, `app/painel/__init__.py`, `app/painel/templates/.gitkeep`
- Create: `tests/__init__.py`

- [ ] **Step 1: Inicializar git**

Run:
```bash
git init
git add -A && git commit -m "chore: estado inicial (monólito) antes da modularização" || true
```

- [ ] **Step 2: Criar `.gitignore`**

```gitignore
.venv/
__pycache__/
*.pyc
.env
*.log
.pytest_cache/
```

- [ ] **Step 3: Criar `requirements.txt`** (versões que funcionam em Python 3.12)

```text
fastapi==0.115.*
uvicorn[standard]==0.49.*
redis==5.*
supabase==2.*
openai==1.*
httpx==0.27.*
tenacity==9.*
python-dotenv==1.*
pytz==2024.*
google-api-python-client==2.*
google-auth==2.*
google-generativeai==0.8.*
langchain==0.3.27
langchain-community==0.3.27
langchain-google-genai==2.0.10
pydantic>=2.10
jinja2==3.*
itsdangerous==2.*
psycopg2-binary==2.9.*
```

- [ ] **Step 4: Criar `requirements-dev.txt`**

```text
-r requirements.txt
pytest==8.*
pytest-asyncio==0.24.*
fakeredis==2.*
```

- [ ] **Step 5: Criar `pytest.ini`**

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
```

- [ ] **Step 6: Criar pacotes vazios**

Crie arquivos vazios: `app/__init__.py`, `app/tools/__init__.py`, `app/painel/__init__.py`, `tests/__init__.py` e `app/painel/templates/.gitkeep` (conteúdo vazio).

- [ ] **Step 7: Instalar dev deps no venv 3.12**

Run:
```bash
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
```
Expected: instala sem erro (o `.venv` já é Python 3.12).

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "chore: scaffolding do pacote app/ e dependências"
```

---

## Fase 1 — Camada de configuração ao vivo

### Task 2: `app/config.py` (TDD)

**Files:**
- Create: `app/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Escrever o teste que falha**

`tests/test_config.py`:
```python
import fakeredis.aioredis
import pytest

from app import config as cfg


@pytest.fixture
def fake_redis(monkeypatch):
    r = fakeredis.aioredis.FakeRedis(decode_responses=False)
    monkeypatch.setattr(cfg, "redis_client", r)
    return r


async def test_get_config_retorna_defaults_quando_vazio(fake_redis):
    c = await cfg.get_config()
    assert c["buffer_segundos"] == 6
    assert c["bloqueio_humano_min"] == 15
    assert c["system_prompt"]  # não vazio
    assert "cadastrar" in c["tools_descricao"]


async def test_set_config_grava_e_persiste(fake_redis):
    await cfg.set_config({"buffer_segundos": 8})
    c = await cfg.get_config()
    assert c["buffer_segundos"] == 8
    # campos não enviados continuam no padrão
    assert c["bloqueio_humano_min"] == 15


async def test_set_config_rejeita_fora_da_faixa(fake_redis):
    with pytest.raises(ValueError):
        await cfg.set_config({"buffer_segundos": 0})
    with pytest.raises(ValueError):
        await cfg.set_config({"bloqueio_humano_min": 999})


async def test_set_config_rejeita_prompt_vazio(fake_redis):
    with pytest.raises(ValueError):
        await cfg.set_config({"system_prompt": "   "})
```

- [ ] **Step 2: Rodar o teste e ver falhar**

Run: `.venv/Scripts/python.exe -m pytest tests/test_config.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.config'`.

- [ ] **Step 3: Implementar `app/config.py`**

```python
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
```

- [ ] **Step 4: Rodar os testes e ver passar**

Run: `.venv/Scripts/python.exe -m pytest tests/test_config.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add app/config.py tests/test_config.py
git commit -m "feat: camada de config ao vivo no Redis com validação"
```

---

## Fase 2 — Modularização (preserva comportamento)

> Em cada task desta fase, mover a função do original **sem mudar a lógica**, exceto onde o passo mostrar código novo (integração com config). Ao final da fase, o smoke test confirma que tudo monta.

### Task 3: `app/clientes.py` — clientes globais e lifespan

**Files:**
- Create: `app/clientes.py`

- [ ] **Step 1: Criar `app/clientes.py`**

Mover do original: o bloco de `os.getenv` (linhas 80–97), a criação de `supabase_client`, `openai_client`, `redis_client`, `llm` (105–116), o lock/serviço do Calendar (119–123), `get_calendar_service` (126–141) e `lifespan` (144–163).

Mudanças obrigatórias:
- Importar `redis_client` de `app.config` (fonte única do Redis): `from app.config import redis_client`. Remover a recriação local do Redis.
- Trocar as constantes de tuning fixas — elas saem daqui (vão para o config). Manter apenas variáveis de ambiente de credenciais.
- Manter `http_client`, `_genai_model`, `_calendar_service`, `_calendar_lock` como globais do módulo.

```python
"""Clientes globais (criados uma vez) e ciclo de vida do servidor."""
import os
import threading
from contextlib import asynccontextmanager
from typing import Optional

import google.generativeai as genai
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI
from google.oauth2 import service_account
from googleapiclient.discovery import build as gcal_build
from langchain_google_genai import ChatGoogleGenerativeAI
from openai import AsyncOpenAI
from supabase import create_client

from app.config import redis_client  # fonte única do Redis

load_dotenv()

SUPABASE_URL          = os.getenv("SUPABASE_URL")
SUPABASE_KEY          = os.getenv("SUPABASE_KEY")
OPENAI_API_KEY        = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY        = os.getenv("GOOGLE_API_KEY")
UAZAPI_TOKEN          = os.getenv("UAZAPI_TOKEN")
UAZAPI_URL            = os.getenv("UAZAPI_URL")
POSTGRES_CONN         = os.getenv("POSTGRES_CONN")
GOOGLE_CALENDAR_ID    = os.getenv("GOOGLE_CALENDAR_ID")
GOOGLE_CALENDAR_CREDS = os.getenv("GOOGLE_CALENDAR_CREDS")

supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
openai_client   = AsyncOpenAI(api_key=OPENAI_API_KEY)

llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash",
    google_api_key=GOOGLE_API_KEY,
    temperature=0.3,
)

http_client: Optional[httpx.AsyncClient] = None
_genai_model: Optional[genai.GenerativeModel] = None
_calendar_lock = threading.Lock()
_calendar_service = None


def get_calendar_service():
    """Cria o cliente do Google Calendar uma única vez (thread-safe)."""
    global _calendar_service
    with _calendar_lock:
        if _calendar_service is None:
            creds = service_account.Credentials.from_service_account_file(
                GOOGLE_CALENDAR_CREDS,
                scopes=["https://www.googleapis.com/auth/calendar"],
            )
            _calendar_service = gcal_build(
                "calendar", "v3", credentials=creds, cache_discovery=False
            )
    return _calendar_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client, _genai_model
    http_client  = httpx.AsyncClient(timeout=30.0)
    genai.configure(api_key=GOOGLE_API_KEY)
    _genai_model = genai.GenerativeModel("gemini-1.5-flash")
    yield
    await http_client.aclose()
```

- [ ] **Step 2: Commit**

```bash
git add app/clientes.py
git commit -m "refactor: extrair clientes globais e lifespan para app/clientes.py"
```

### Task 4: `app/memoria.py` — histórico Postgres

**Files:**
- Create: `app/memoria.py`

- [ ] **Step 1: Criar `app/memoria.py`**

Mover do original: `inserir_na_memoria` (269–282), `carregar_historico` (285–307), `salvar_par_conversa` (310–320). Adicionar no topo:
```python
import asyncio

from langchain_community.chat_message_histories import PostgresChatMessageHistory
from langchain_core.messages import AIMessage, HumanMessage

from app.clientes import POSTGRES_CONN
from app.config import get_config
```
Mudança em `carregar_historico`: o limite vem do config. Substituir o uso de `HISTORICO_MAX` por leitura do config **fora** da thread:
```python
async def carregar_historico(number: str) -> list:
    limite = (await get_config())["historico_max"]

    def _carregar():
        hist = PostgresChatMessageHistory(
            connection_string=POSTGRES_CONN, session_id=f"{number}_chat",
        )
        msgs = hist.messages
        if len(msgs) > limite:
            msgs = msgs[-limite:]
            if msgs and isinstance(msgs[0], AIMessage):
                msgs = msgs[1:]
        return msgs

    return await asyncio.to_thread(_carregar)
```
As outras duas funções vão sem alteração de lógica (só os imports acima).

- [ ] **Step 2: Commit**

```bash
git add app/memoria.py
git commit -m "refactor: extrair memória Postgres para app/memoria.py (histórico_max via config)"
```

### Task 5: `app/midia.py` — áudio/imagem/documento

**Files:**
- Create: `app/midia.py`

- [ ] **Step 1: Criar `app/midia.py`**

Mover do original: `baixar_midia` (353–361), `transcrever_audio` (364–371), `analisar_imagem` (374–397), `analisar_documento` (400–412), `processar_mensagem_por_tipo` (415–440), **sem mudança de lógica**. Imports no topo:
```python
import base64
import io
import logging

from app import clientes
from app.clientes import UAZAPI_TOKEN, UAZAPI_URL, openai_client

logger = logging.getLogger(__name__)
```
Onde o original usa `http_client` e `_genai_model` (globais que mudam no lifespan), referenciar via módulo para pegar o valor atual: `clientes.http_client` e `clientes._genai_model` (não importar o valor direto, senão pega `None`).

- [ ] **Step 2: Commit**

```bash
git add app/midia.py
git commit -m "refactor: extrair processamento de mídia para app/midia.py"
```

### Task 6: `app/bloqueios.py` — grupos, humano, rate limit (config)

**Files:**
- Create: `app/bloqueios.py`
- Test: `tests/test_bloqueios.py`

- [ ] **Step 1: Escrever teste do rate limit lendo do config**

`tests/test_bloqueios.py`:
```python
import fakeredis.aioredis
import pytest

from app import config as cfg


@pytest.fixture
def fake_redis(monkeypatch):
    r = fakeredis.aioredis.FakeRedis(decode_responses=False)
    monkeypatch.setattr(cfg, "redis_client", r)
    import app.bloqueios as b
    monkeypatch.setattr(b, "redis_client", r)
    return r


async def test_rate_limit_usa_max_do_config(fake_redis):
    import app.bloqueios as b
    await cfg.set_config({"rate_limit_max": 2})
    assert await b.verifica_rate_limit("551199@c.us") == "ok"   # 1
    assert await b.verifica_rate_limit("551199@c.us") == "ok"   # 2
    assert await b.verifica_rate_limit("551199@c.us") == "aviso"  # 3 (max+1)
    assert await b.verifica_rate_limit("551199@c.us") == "bloqueado"  # 4
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/Scripts/python.exe -m pytest tests/test_bloqueios.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.bloqueios'`.

- [ ] **Step 3: Criar `app/bloqueios.py`**

Mover `ja_processada` (214–222), `verifica_rate_limit` (225–243), `verificar_bloqueios_rapido` (327–346). Imports:
```python
from app.config import get_config, redis_client
```
Mudança em `verifica_rate_limit` — ler `rate_limit_max`/`rate_limit_janela` do config:
```python
async def verifica_rate_limit(number: str) -> str:
    cfg = await get_config()
    rate_max, janela = cfg["rate_limit_max"], cfg["rate_limit_janela"]
    chave = f"ratelimit:{number}"
    contador = await redis_client.incr(chave)
    if contador == 1:
        await redis_client.expire(chave, janela)
    if contador <= rate_max:
        return "ok"
    elif contador == rate_max + 1:
        return "aviso"
    return "bloqueado"
```
Mudança em `verificar_bloqueios_rapido` — o TTL do bloqueio humano vem do config (minutos → segundos):
```python
    if bool(dados["human"]) and dados["human"] not in (False, "false", "False", 0):
        minutos = (await get_config())["bloqueio_humano_min"]
        await redis_client.set(f"{number}_block", "true", ex=minutos * 60)
        return "bloquear_humano_bot"
```
O resto da função (grupos, `block_wpp`, `{number}_block`) vai sem alteração.

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/Scripts/python.exe -m pytest tests/test_bloqueios.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add app/bloqueios.py tests/test_bloqueios.py
git commit -m "feat: bloqueios com rate limit e tempo de bloqueio humano via config"
```

### Task 7: `app/buffer.py` — debounce deslizante (config)

**Files:**
- Create: `app/buffer.py`
- Test: `tests/test_buffer.py`

- [ ] **Step 1: Escrever teste do reset deslizante**

`tests/test_buffer.py`:
```python
import asyncio

import fakeredis.aioredis
import pytest

from app import config as cfg


@pytest.fixture
def fake_redis(monkeypatch):
    r = fakeredis.aioredis.FakeRedis(decode_responses=False)
    monkeypatch.setattr(cfg, "redis_client", r)
    import app.buffer as buf
    monkeypatch.setattr(buf, "redis_client", r)
    return r


async def test_mensagem_nova_descarta_a_anterior(fake_redis):
    """A 1ª chamada deve retornar None (a 2ª chegou e roubou o turno)."""
    import app.buffer as buf
    await cfg.set_config({"buffer_segundos": 1})
    num = "551199@c.us"

    async def primeira():
        return await buf.buffer_mensagens(num, '{"txtmessage":"oi"}')

    async def segunda():
        await asyncio.sleep(0.3)  # chega durante a espera da primeira
        return await buf.buffer_mensagens(num, '{"txtmessage":"tudo bem?"}')

    r1, r2 = await asyncio.gather(primeira(), segunda())
    assert r1 is None                      # primeira foi descartada
    assert r2 is not None and len(r2) == 2 # segunda processou as duas mensagens
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/Scripts/python.exe -m pytest tests/test_buffer.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.buffer'`.

- [ ] **Step 3: Criar `app/buffer.py`**

Mover `buffer_mensagens` (450–472). Trocar `BUFFER_SEGUNDOS` pelo config e usar `redis_client` do config:
```python
import asyncio
import time
from typing import Optional

from app.config import get_config, redis_client


async def buffer_mensagens(number: str, mensagem_json: str) -> Optional[list[str]]:
    chave_lista     = f"{number}:msgs"
    chave_atividade = f"{number}:atividade"

    await redis_client.rpush(chave_lista, mensagem_json)
    await redis_client.expire(chave_lista, 120)

    meu_token = str(time.time_ns())
    await redis_client.set(chave_atividade, meu_token, ex=120)

    buffer_segundos = (await get_config())["buffer_segundos"]
    await asyncio.sleep(buffer_segundos)

    valor_salvo = await redis_client.get(chave_atividade)
    if not valor_salvo or valor_salvo.decode() != meu_token:
        return None  # outra mensagem chegou depois — descarta

    mensagens_raw = await redis_client.lrange(chave_lista, 0, -1)
    await redis_client.delete(chave_lista)
    return [m.decode() for m in mensagens_raw]
```

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/Scripts/python.exe -m pytest tests/test_buffer.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add app/buffer.py tests/test_buffer.py
git commit -m "feat: buffer lê o tempo do debounce do config (reset deslizante preservado)"
```

### Task 8: `app/tools/` — uma tool por arquivo + registry com descrição do config

**Files:**
- Create: `app/tools/base.py`, `app/tools/cadastrar.py`, `app/tools/buscar_info.py`, `app/tools/consultar_agenda.py`, `app/tools/pre_marcacao.py`, `app/tools/desmarcar.py`
- Modify: `app/tools/__init__.py`
- Test: `tests/test_tools_registry.py`

> Padrão: cada arquivo expõe `def criar(descricao: str) -> Tool` (a `cadastrar` recebe também o `number`). A descrição vem do config e é injetada via o argumento `description` da decoração `@tool`.

- [ ] **Step 1: Criar `app/tools/base.py`**

```python
"""Helpers compartilhados pelas tools."""
import asyncio

from app.clientes import GOOGLE_CALENDAR_ID, get_calendar_service

__all__ = ["asyncio", "GOOGLE_CALENDAR_ID", "get_calendar_service"]
```

- [ ] **Step 2: Criar `app/tools/cadastrar.py`**

```python
from langchain.tools import tool

from app.clientes import supabase_client
from app.tools.base import asyncio


def criar(number: str, descricao: str):
    @tool("cadastrar", description=descricao)
    async def cadastrar(nome: str) -> str:
        def _executar():
            return (
                supabase_client.table("cadastro")
                .update({"nomeusuario": nome.strip().title()})
                .eq("remoteJid", number)
                .execute()
            )
        await asyncio.to_thread(_executar)
        return f"Nome '{nome.strip().title()}' salvo com sucesso."

    return cadastrar
```

- [ ] **Step 3: Criar `app/tools/buscar_info.py`**

```python
from langchain.tools import tool


def criar(descricao: str):
    @tool("buscar_info", description=descricao)
    async def buscar_info(pergunta: str) -> str:
        # TODO: substituir pelo RAG real (busca vetorial no Supabase/pgvector)
        return f"[Resultado da busca: {pergunta}]"

    return buscar_info
```

- [ ] **Step 4: Criar `app/tools/consultar_agenda.py`**

Mover o corpo de `consultar_agenda` (514–548) para dentro da factory:
```python
import json

from langchain.tools import tool

from app.tools.base import GOOGLE_CALENDAR_ID, asyncio, get_calendar_service


def criar(descricao: str):
    @tool("consultar_agenda", description=descricao)
    async def consultar_agenda(after: str, before: str) -> str:
        def _consultar():
            service = get_calendar_service()
            result = service.events().list(
                calendarId=GOOGLE_CALENDAR_ID, timeMin=after, timeMax=before,
                timeZone="America/Sao_Paulo", singleEvents=True, orderBy="startTime",
            ).execute()
            return result.get("items", [])

        eventos = await asyncio.to_thread(_consultar)
        return json.dumps(
            [
                {
                    "id": e.get("id"),
                    "summary": e.get("summary", ""),
                    "start": e["start"].get("dateTime", e["start"].get("date")),
                    "end": e["end"].get("dateTime", e["end"].get("date")),
                }
                for e in eventos
            ],
            ensure_ascii=False,
        )

    return consultar_agenda
```

- [ ] **Step 5: Criar `app/tools/pre_marcacao.py`**

Mover o corpo de `pre_marcacao` (551–576):
```python
from langchain.tools import tool

from app.tools.base import GOOGLE_CALENDAR_ID, asyncio, get_calendar_service


def criar(descricao: str):
    @tool("pre_marcacao", description=descricao)
    async def pre_marcacao(start: str, end: str, summary: str, description: str) -> str:
        def _criar():
            service = get_calendar_service()
            evento = {
                "summary": summary,
                "description": description,
                "start": {"dateTime": start, "timeZone": "America/Sao_Paulo"},
                "end": {"dateTime": end, "timeZone": "America/Sao_Paulo"},
            }
            return service.events().insert(
                calendarId=GOOGLE_CALENDAR_ID, body=evento
            ).execute()

        resultado = await asyncio.to_thread(_criar)
        return f"Pré-marcação criada com ID {resultado.get('id')}."

    return pre_marcacao
```

- [ ] **Step 6: Criar `app/tools/desmarcar.py`**

Mover o corpo de `desmarcar` (579–595):
```python
from langchain.tools import tool

from app.tools.base import GOOGLE_CALENDAR_ID, asyncio, get_calendar_service


def criar(descricao: str):
    @tool("desmarcar", description=descricao)
    async def desmarcar(event_id: str) -> str:
        def _deletar():
            service = get_calendar_service()
            service.events().delete(
                calendarId=GOOGLE_CALENDAR_ID, eventId=event_id
            ).execute()

        await asyncio.to_thread(_deletar)
        return f"Agendamento {event_id} cancelado."

    return desmarcar
```

- [ ] **Step 7: Escrever o teste do registry**

`tests/test_tools_registry.py`:
```python
import fakeredis.aioredis
import pytest

from app import config as cfg


@pytest.fixture
def fake_redis(monkeypatch):
    r = fakeredis.aioredis.FakeRedis(decode_responses=False)
    monkeypatch.setattr(cfg, "redis_client", r)
    return r


async def test_montar_tools_injeta_descricao_do_config(fake_redis):
    from app.tools import montar_tools
    await cfg.set_config({"tools_descricao": {"buscar_info": "DESC NOVA DE TESTE"}})
    tools = await montar_tools("551199@c.us")
    nomes = {t.name for t in tools}
    assert nomes == {"cadastrar", "buscar_info", "consultar_agenda",
                     "pre_marcacao", "desmarcar"}
    bi = next(t for t in tools if t.name == "buscar_info")
    assert bi.description == "DESC NOVA DE TESTE"
```

- [ ] **Step 8: Implementar `app/tools/__init__.py` (registry)**

```python
"""Registry de tools: monta a lista injetando as descrições do config.

Para adicionar uma tool nova: crie app/tools/minha_tool.py com `def criar(descricao)`,
importe aqui, registre em _SEM_NUMERO (ou trate o closure como cadastrar), e adicione a
chave em TOOLS_DESCRICAO_DEFAULT no app/config.py.
"""
from app.config import get_config
from app.tools import (
    buscar_info,
    cadastrar,
    consultar_agenda,
    desmarcar,
    pre_marcacao,
)

# Tools cuja factory recebe só a descrição.
_SEM_NUMERO = {
    "buscar_info": buscar_info,
    "consultar_agenda": consultar_agenda,
    "pre_marcacao": pre_marcacao,
    "desmarcar": desmarcar,
}


async def montar_tools(number: str) -> list:
    descricoes = (await get_config())["tools_descricao"]
    tools = [cadastrar.criar(number, descricoes["cadastrar"])]
    for nome, modulo in _SEM_NUMERO.items():
        tools.append(modulo.criar(descricoes[nome]))
    return tools
```

- [ ] **Step 9: Rodar e ver passar**

Run: `.venv/Scripts/python.exe -m pytest tests/test_tools_registry.py -v`
Expected: 1 passed.

- [ ] **Step 10: Commit**

```bash
git add app/tools tests/test_tools_registry.py
git commit -m "feat: tools em arquivos separados com descrição dinâmica via config"
```

### Task 9: `app/agente.py` — monta o agente com prompt e timeout do config

**Files:**
- Create: `app/agente.py`

- [ ] **Step 1: Criar `app/agente.py`**

Baseado em `chamar_agente` (657–695). Mudanças: `SYSTEM_PROMPT` e `AGENT_TIMEOUT_SEGUNDOS` vêm do config; tools vêm de `montar_tools`.
```python
import asyncio
from datetime import datetime

import pytz
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from app.clientes import llm
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

    agente   = create_tool_calling_agent(llm, tools, prompt)
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
```

- [ ] **Step 2: Commit**

```bash
git add app/agente.py
git commit -m "feat: agente monta prompt, tools e timeout a partir do config"
```

### Task 10: `app/webhook.py` — envio + orquestração + cadastro

**Files:**
- Create: `app/webhook.py`

- [ ] **Step 1: Criar `app/webhook.py`**

Mover, sem mudança de lógica (só imports): helpers `calcular_typing_ms` (175–181), `nova_requisicao_id` (184–186), `supabase_async` (170–172), `extrair_variaveis` (193–207); cadastro `verificar_ou_criar_cadastro` (250–259); envio `ErroCliente` + `_enviar_texto_raw` (702–732), `enviar_aviso_rate_limit` (735–741), `enviar_typing` (744–753), `enviar_texto` (756–763), `enviar_resposta` (766–775), `enviar_fallback` (778–784); a validação `validar_token_webhook` (889–898); e a orquestração `processar_em_background` (791–879).

Imports no topo:
```python
import asyncio
import hmac
import json
import logging
import os
import uuid

from fastapi import HTTPException
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from app import clientes
from app.agente import chamar_agente
from app.bloqueios import ja_processada, verifica_rate_limit, verificar_bloqueios_rapido
from app.buffer import buffer_mensagens
from app.clientes import UAZAPI_TOKEN, UAZAPI_URL, supabase_client
from app.memoria import inserir_na_memoria
from app.midia import processar_mensagem_por_tipo

logger = logging.getLogger(__name__)
WEBHOOK_TOKEN = os.getenv("WEBHOOK_TOKEN", "")
```
Onde usar o `http_client` global, referenciar `clientes.http_client` (pega o valor criado no lifespan). A lógica interna de `processar_em_background` é **idêntica** ao original. Inclua `validar_token_webhook` (usa `WEBHOOK_TOKEN` e `hmac.compare_digest`, igual ao original):
```python
def validar_token_webhook(body: dict) -> None:
    if not WEBHOOK_TOKEN:
        return  # dev mode — sem token configurado
    if not hmac.compare_digest(body.get("token", ""), WEBHOOK_TOKEN):
        raise HTTPException(status_code=401, detail="Token inválido")
```

- [ ] **Step 2: Commit**

```bash
git add app/webhook.py
git commit -m "refactor: orquestração, envio e cadastro em app/webhook.py"
```

### Task 11: `app/main.py` + smoke test do pacote

**Files:**
- Create: `app/main.py`
- Test: `tests/test_smoke_app.py`

- [ ] **Step 1: Criar `app/main.py`**

```python
"""Cria o FastAPI, registra o webhook e o painel, e o lifespan."""
import logging

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from starlette.middleware.sessions import SessionMiddleware

from app.clientes import lifespan
from app.config import redis_client
from app.painel.auth import SESSION_SECRET
from app.painel.rotas import router as painel_router
from app.webhook import processar_em_background, validar_token_webhook

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

app = FastAPI(lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)
app.include_router(painel_router)


@app.post("/webhook")
async def receber_mensagem(request: Request, background_tasks: BackgroundTasks):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="JSON inválido")
    validar_token_webhook(body)
    background_tasks.add_task(processar_em_background, body)
    return {"ok": True}


@app.get("/health")
async def health():
    try:
        await redis_client.ping()
        redis_ok = True
    except Exception:
        redis_ok = False
    return {"status": "ok" if redis_ok else "degraded", "redis": redis_ok}
```
> Nota: `validar_token_webhook` vive em `app/webhook.py` (Task 10) e é chamada acima antes de agendar a task. O `/unblock` original foi substituído pelas rotas `/admin/sessoes/{numero}/pausar` e `/despausar` do painel (Task 14), que já exigem login.

- [ ] **Step 2: Escrever smoke test do pacote**

`tests/test_smoke_app.py`:
```python
import os

os.environ.setdefault("SUPABASE_URL", "https://exemplo.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "x")
os.environ.setdefault("OPENAI_API_KEY", "x")
os.environ.setdefault("GOOGLE_API_KEY", "x")
os.environ.setdefault("UAZAPI_URL", "https://x")
os.environ.setdefault("UAZAPI_TOKEN", "x")
os.environ.setdefault("POSTGRES_CONN", "postgresql://u:p@localhost/db")
os.environ.setdefault("GOOGLE_CALENDAR_ID", "x")
os.environ.setdefault("PAINEL_USER", "admin")
os.environ.setdefault("PAINEL_PASS_HASH", "x")
os.environ.setdefault("SESSION_SECRET", "dev-secret")


def test_app_monta_e_expoe_rotas():
    from app.main import app
    paths = {r.path for r in app.routes if hasattr(r, "path")}
    assert "/webhook" in paths
    assert "/health" in paths
    assert "/admin/login" in paths
```

- [ ] **Step 3: Rodar o smoke test**

Run: `.venv/Scripts/python.exe -m pytest tests/test_smoke_app.py -v`
Expected: PASS (depois que Task 12–13 existirem; se rodar antes, falha no import do painel — ordem natural é fazer 12–14 e então este passo).

- [ ] **Step 4: Commit**

```bash
git add app/main.py tests/test_smoke_app.py
git commit -m "feat: app/main.py monta agente + painel num único FastAPI"
```

---

## Fase 3 — Painel

### Task 12: `app/painel/auth.py` — login usuário+senha (TDD)

**Files:**
- Create: `app/painel/auth.py`
- Test: `tests/test_auth.py`

- [ ] **Step 1: Escrever o teste**

`tests/test_auth.py`:
```python
import hashlib

from app.painel import auth


def test_senha_correta_confere():
    h = hashlib.sha256("segredo123".encode()).hexdigest()
    assert auth.conferir("admin", "segredo123", usuario="admin", senha_hash=h) is True


def test_usuario_ou_senha_errado_falha():
    h = hashlib.sha256("segredo123".encode()).hexdigest()
    assert auth.conferir("admin", "errada", usuario="admin", senha_hash=h) is False
    assert auth.conferir("outro", "segredo123", usuario="admin", senha_hash=h) is False
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/Scripts/python.exe -m pytest tests/test_auth.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.painel.auth'`.

- [ ] **Step 3: Implementar `app/painel/auth.py`**

```python
"""Autenticação simples do painel: um usuário admin (credenciais no .env).

Gerar o hash da senha:
  python -c "import hashlib,sys;print(hashlib.sha256(sys.argv[1].encode()).hexdigest())" MINHA_SENHA
"""
import hashlib
import hmac
import os

from fastapi import Request
from fastapi.responses import RedirectResponse

PAINEL_USER      = os.getenv("PAINEL_USER", "admin")
PAINEL_PASS_HASH = os.getenv("PAINEL_PASS_HASH", "")
SESSION_SECRET   = os.getenv("SESSION_SECRET", "troque-esse-segredo")


def conferir(usuario_in: str, senha_in: str, *, usuario=None, senha_hash=None) -> bool:
    usuario = usuario if usuario is not None else PAINEL_USER
    senha_hash = senha_hash if senha_hash is not None else PAINEL_PASS_HASH
    hash_in = hashlib.sha256(senha_in.encode()).hexdigest()
    ok_user = hmac.compare_digest(usuario_in, usuario)
    ok_pass = hmac.compare_digest(hash_in, senha_hash or "")
    return ok_user and ok_pass


def logado(request: Request) -> bool:
    return bool(request.session.get("user"))


def exigir_login(request: Request):
    """Use como dependência; retorna RedirectResponse se não logado, senão None."""
    if not logado(request):
        return RedirectResponse("/admin/login", status_code=302)
    return None
```

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/Scripts/python.exe -m pytest tests/test_auth.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add app/painel/auth.py tests/test_auth.py
git commit -m "feat: auth do painel (usuário+senha com hash)"
```

### Task 13: `app/painel/rotas.py` — login + tela de configurações

**Files:**
- Create: `app/painel/rotas.py`
- Create: `app/painel/templates/base.html`, `login.html`, `config.html`

- [ ] **Step 1: Criar `app/painel/templates/base.html`**

```html
<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Painel Elizabeth</title>
  <style>
    body{font-family:system-ui,sans-serif;max-width:760px;margin:2rem auto;padding:0 1rem;color:#222}
    nav a{margin-right:1rem} label{display:block;margin:.8rem 0 .2rem;font-weight:600}
    input,textarea{width:100%;padding:.5rem;font:inherit;border:1px solid #ccc;border-radius:6px}
    textarea{min-height:6rem} button{margin-top:1rem;padding:.6rem 1.2rem;cursor:pointer}
    .ok{background:#e6ffed;border:1px solid #34d058;padding:.6rem;border-radius:6px}
    .err{background:#ffeef0;border:1px solid #d73a49;padding:.6rem;border-radius:6px}
    table{width:100%;border-collapse:collapse} td,th{border-bottom:1px solid #eee;padding:.5rem;text-align:left}
  </style>
</head>
<body>
  {% if request.session.get('user') %}
  <nav><a href="/admin/config">Configurações</a><a href="/admin/sessoes">Sessões</a>
    <a href="/admin/logout">Sair</a></nav><hr>
  {% endif %}
  {% block conteudo %}{% endblock %}
</body>
</html>
```

- [ ] **Step 2: Criar `app/painel/templates/login.html`**

```html
{% extends "base.html" %}
{% block conteudo %}
<h1>Entrar</h1>
{% if erro %}<p class="err">{{ erro }}</p>{% endif %}
<form method="post" action="/admin/login">
  <label>Usuário</label><input name="usuario" autofocus>
  <label>Senha</label><input name="senha" type="password">
  <button type="submit">Entrar</button>
</form>
{% endblock %}
```

- [ ] **Step 3: Criar `app/painel/templates/config.html`**

```html
{% extends "base.html" %}
{% block conteudo %}
<h1>Configurações</h1>
{% if salvo %}<p class="ok">Salvo ✓</p>{% endif %}
{% if erro %}<p class="err">{{ erro }}</p>{% endif %}
<form method="post" action="/admin/config">
  <label>Tempo do buffer (segundos)</label>
  <input name="buffer_segundos" type="number" value="{{ c.buffer_segundos }}">
  <label>Bloqueio humano (minutos)</label>
  <input name="bloqueio_humano_min" type="number" value="{{ c.bloqueio_humano_min }}">
  <label>Rate limit — máx mensagens</label>
  <input name="rate_limit_max" type="number" value="{{ c.rate_limit_max }}">
  <label>Rate limit — janela (segundos)</label>
  <input name="rate_limit_janela" type="number" value="{{ c.rate_limit_janela }}">
  <label>Máx mensagens no histórico</label>
  <input name="historico_max" type="number" value="{{ c.historico_max }}">
  <label>Timeout do agente (segundos)</label>
  <input name="agent_timeout_seg" type="number" value="{{ c.agent_timeout_seg }}">
  <label>System prompt (personalidade da Elizabeth)</label>
  <textarea name="system_prompt">{{ c.system_prompt }}</textarea>
  <h3>Descrição das tools</h3>
  {% for nome, desc in c.tools_descricao.items() %}
  <label>{{ nome }}</label>
  <textarea name="tool__{{ nome }}">{{ desc }}</textarea>
  {% endfor %}
  <button type="submit">Salvar</button>
</form>
{% endblock %}
```

- [ ] **Step 4: Criar `app/painel/rotas.py` (login + config)**

```python
import os

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import get_config, set_config
from app.painel.auth import PAINEL_PASS_HASH, PAINEL_USER, conferir, logado

router = APIRouter(prefix="/admin")
_DIR = os.path.dirname(__file__)
templates = Jinja2Templates(directory=os.path.join(_DIR, "templates"))

_CAMPOS_INT = [
    "buffer_segundos", "bloqueio_humano_min", "rate_limit_max",
    "rate_limit_janela", "historico_max", "agent_timeout_seg",
]


@router.get("/login", response_class=HTMLResponse)
async def login_form(request: Request, erro: str = ""):
    return templates.TemplateResponse("login.html", {"request": request, "erro": erro})


@router.post("/login")
async def login_post(request: Request, usuario: str = Form(...), senha: str = Form(...)):
    if conferir(usuario, senha, usuario=PAINEL_USER, senha_hash=PAINEL_PASS_HASH):
        request.session["user"] = usuario
        return RedirectResponse("/admin/config", status_code=302)
    return templates.TemplateResponse(
        "login.html", {"request": request, "erro": "Usuário ou senha inválidos"},
        status_code=401,
    )


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/admin/login", status_code=302)


@router.get("/config", response_class=HTMLResponse)
async def config_form(request: Request, salvo: str = ""):
    if not logado(request):
        return RedirectResponse("/admin/login", status_code=302)
    c = await get_config()
    return templates.TemplateResponse(
        "config.html", {"request": request, "c": c, "salvo": bool(salvo), "erro": ""}
    )


@router.post("/config", response_class=HTMLResponse)
async def config_post(request: Request):
    if not logado(request):
        return RedirectResponse("/admin/login", status_code=302)
    form = await request.form()
    parcial = {}
    try:
        for campo in _CAMPOS_INT:
            if form.get(campo) not in (None, ""):
                parcial[campo] = int(form[campo])
        if form.get("system_prompt") is not None:
            parcial["system_prompt"] = form["system_prompt"]
        td = {k[len("tool__"):]: v for k, v in form.items() if k.startswith("tool__")}
        if td:
            parcial["tools_descricao"] = td
        await set_config(parcial)
    except ValueError as exc:
        c = await get_config()
        return templates.TemplateResponse(
            "config.html",
            {"request": request, "c": c, "salvo": False, "erro": str(exc)},
            status_code=400,
        )
    return RedirectResponse("/admin/config?salvo=1", status_code=302)
```

- [ ] **Step 5: Rodar o smoke test do app (já cobre /admin/login)**

Run: `.venv/Scripts/python.exe -m pytest tests/test_smoke_app.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/painel/rotas.py app/painel/templates
git commit -m "feat: painel /admin com login e tela de configurações"
```

### Task 14: Tela de sessões + pausar/despausar

**Files:**
- Modify: `app/painel/rotas.py`
- Create: `app/painel/templates/sessoes.html`, `conversa.html`

- [ ] **Step 1: Criar `app/painel/templates/sessoes.html`**

```html
{% extends "base.html" %}
{% block conteudo %}
<h1>Sessões</h1>
<table>
  <tr><th>Número</th><th>Nome</th><th>Status</th><th></th></tr>
  {% for s in sessoes %}
  <tr>
    <td>{{ s.numero.split('@')[0] }}</td>
    <td>{{ s.nome or '—' }}</td>
    <td>{{ s.status }}</td>
    <td><a href="/admin/sessoes/{{ s.numero }}">abrir</a></td>
  </tr>
  {% endfor %}
</table>
{% endblock %}
```

- [ ] **Step 2: Criar `app/painel/templates/conversa.html`**

```html
{% extends "base.html" %}
{% block conteudo %}
<h1>Conversa {{ numero.split('@')[0] }}</h1>
<form method="post" action="/admin/sessoes/{{ numero }}/pausar" style="display:inline">
  <button>Pausar bot</button></form>
<form method="post" action="/admin/sessoes/{{ numero }}/despausar" style="display:inline">
  <button>Despausar</button></form>
<hr>
{% for m in mensagens %}
<p><strong>{{ m.role }}:</strong> {{ m.texto }}</p>
{% endfor %}
{% endblock %}
```

- [ ] **Step 3: Adicionar rotas de sessões em `app/painel/rotas.py`**

Acrescentar imports e rotas:
```python
import asyncio

from langchain_community.chat_message_histories import PostgresChatMessageHistory
from langchain_core.messages import AIMessage

from app.clientes import POSTGRES_CONN, supabase_client
from app.config import redis_client


async def _status(numero: str) -> str:
    val = await redis_client.get(f"{numero}_block")
    return "pausado/bloqueado" if val == b"true" else "ativo"


@router.get("/sessoes", response_class=HTMLResponse)
async def sessoes(request: Request):
    if not logado(request):
        return RedirectResponse("/admin/login", status_code=302)

    def _listar():
        return supabase_client.table("cadastro").select("remoteJid,nomeusuario").execute()

    res = await asyncio.to_thread(_listar)
    linhas = res.data or []
    sessoes = []
    for row in linhas:
        numero = row["remoteJid"]
        sessoes.append({
            "numero": numero, "nome": row.get("nomeusuario"),
            "status": await _status(numero),
        })
    return templates.TemplateResponse(
        "sessoes.html", {"request": request, "sessoes": sessoes}
    )


@router.get("/sessoes/{numero}", response_class=HTMLResponse)
async def conversa(request: Request, numero: str):
    if not logado(request):
        return RedirectResponse("/admin/login", status_code=302)

    def _hist():
        h = PostgresChatMessageHistory(
            connection_string=POSTGRES_CONN, session_id=f"{numero}_chat"
        )
        return h.messages

    msgs = await asyncio.to_thread(_hist)
    mensagens = [
        {"role": "Elizabeth" if isinstance(m, AIMessage) else "Paciente",
         "texto": m.content}
        for m in msgs
    ]
    return templates.TemplateResponse(
        "conversa.html", {"request": request, "numero": numero, "mensagens": mensagens}
    )


@router.post("/sessoes/{numero}/pausar")
async def pausar(request: Request, numero: str):
    if not logado(request):
        return RedirectResponse("/admin/login", status_code=302)
    await redis_client.set(f"{numero}_block", "true")  # sem TTL: até despausar
    return RedirectResponse(f"/admin/sessoes/{numero}", status_code=302)


@router.post("/sessoes/{numero}/despausar")
async def despausar(request: Request, numero: str):
    if not logado(request):
        return RedirectResponse("/admin/login", status_code=302)
    await redis_client.delete(f"{numero}_block")
    return RedirectResponse(f"/admin/sessoes/{numero}", status_code=302)
```

- [ ] **Step 4: Verificar que o app ainda monta**

Run: `.venv/Scripts/python.exe -m pytest tests/test_smoke_app.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/painel/rotas.py app/painel/templates/sessoes.html app/painel/templates/conversa.html
git commit -m "feat: painel lista sessões e permite pausar/despausar o bot por número"
```

---

## Fase 4 — Deploy

### Task 15: Docker, Compose, .env.example, README

**Files:**
- Create: `Dockerfile`, `docker-compose.yml`, `.env.example`, `README.md`, `.dockerignore`

- [ ] **Step 1: Criar `Dockerfile`**

```dockerfile
FROM python:3.12-slim
WORKDIR /code
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Criar `.dockerignore`**

```text
.venv
__pycache__
*.pyc
.git
tests
docs
.env
```

- [ ] **Step 3: Criar `docker-compose.yml`**

```yaml
services:
  app:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    environment:
      REDIS_URL: redis://redis:6379
    depends_on:
      - redis
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    volumes:
      - redis-data:/data
    restart: unless-stopped

  # HTTPS opcional (descomente e ajuste o domínio):
  # caddy:
  #   image: caddy:2
  #   ports: ["80:80", "443:443"]
  #   command: caddy reverse-proxy --from seu-dominio.com --to app:8000
  #   depends_on: [app]
  #   restart: unless-stopped

volumes:
  redis-data:
```

- [ ] **Step 4: Criar `.env.example`**

```text
# --- Serviços do agente ---
SUPABASE_URL=
SUPABASE_KEY=
OPENAI_API_KEY=
GOOGLE_API_KEY=
UAZAPI_URL=
UAZAPI_TOKEN=
POSTGRES_CONN=postgresql://usuario:senha@host:5432/db
GOOGLE_CALENDAR_ID=
GOOGLE_CALENDAR_CREDS=/code/service-account.json

# --- Painel admin ---
PAINEL_USER=admin
# Gere com: python -c "import hashlib;print(hashlib.sha256(b'SUA_SENHA').hexdigest())"
PAINEL_PASS_HASH=
SESSION_SECRET=troque-por-um-valor-aleatorio-longo
```

- [ ] **Step 5: Criar `README.md`**

```markdown
# Agente WhatsApp Elizabeth + Painel

## Deploy na VPS
1. `git clone <repo> && cd <repo>`
2. `cp .env.example .env` e preencha as variáveis.
3. Gere o hash da senha do painel:
   `python -c "import hashlib;print(hashlib.sha256(b'SUA_SENHA').hexdigest())"`
4. `docker compose up -d --build`
5. Agente: `http://SEU_IP:8000/webhook` · Painel: `http://SEU_IP:8000/admin`

> Use HTTPS em produção (serviço `caddy` comentado no compose). Login sem HTTPS
> expõe a senha.

## Desenvolvimento local (Python 3.12)
`.venv/Scripts/python.exe -m pytest` roda os testes.
```

- [ ] **Step 6: Validar o build da imagem**

Run: `docker build -t elizabeth-agente .`
Expected: build conclui sem erro (requer Docker instalado na máquina).

- [ ] **Step 7: Commit**

```bash
git add Dockerfile .dockerignore docker-compose.yml .env.example README.md
git commit -m "feat: empacotamento Docker + compose (app+redis) e README de deploy"
```

---

## Fase 5 — Documentação para extensão

### Task 16: `AGENTS.md` + `CLAUDE.md`

**Files:**
- Create: `AGENTS.md`, `CLAUDE.md`

- [ ] **Step 1: Criar `AGENTS.md`**

```markdown
# AGENTS.md — Guia de manutenção do Agente Elizabeth

## Arquitetura
FastAPI único serve o agente (`/webhook`) e o painel (`/admin`). Estado e config no
Redis; memória das conversas no Postgres; agenda no Google Calendar.

| Módulo | Responsabilidade |
|--------|------------------|
| `app/config.py` | Config ao vivo (Redis) + DEFAULTS + validação |
| `app/clientes.py` | Clientes globais (Supabase, OpenAI, Gemini, Calendar) + lifespan |
| `app/buffer.py` | Debounce deslizante (agrupa mensagens rápidas) |
| `app/bloqueios.py` | Grupos, atendente humano, rate limit |
| `app/memoria.py` | Histórico Postgres |
| `app/midia.py` | Áudio/imagem/documento |
| `app/tools/` | Uma tool por arquivo + registry |
| `app/agente.py` | Monta o agente LangChain |
| `app/webhook.py` | Orquestração + envio de mensagens |
| `app/painel/` | Login, configurações, sessões |

## Config ao vivo
Tudo que o painel ajusta vive numa chave Redis (`config:agente`). O agente chama
`get_config()` a cada mensagem, então mudanças valem na hora, sem restart. Padrões e
faixas de validação estão em `app/config.py`.

## Como criar uma TOOL nova
1. Crie `app/tools/minha_tool.py`:
   ```python
   from langchain.tools import tool

   def criar(descricao: str):
       @tool("minha_tool", description=descricao)
       async def minha_tool(param: str) -> str:
           return "resultado"
       return minha_tool
   ```
2. Em `app/config.py`, adicione a chave em `TOOLS_DESCRICAO_DEFAULT["minha_tool"] = "..."`.
3. Em `app/tools/__init__.py`, importe o módulo e registre em `_SEM_NUMERO`
   (ou trate o closure se precisar do número, como `cadastrar`).
4. Pronto: a descrição já aparece editável no painel e o agente já enxerga a tool.

## Como adicionar um CONFIG novo
1. Em `app/config.py`: adicione a chave em `DEFAULTS` e, se numérico, a faixa em `_FAIXAS`.
2. Use onde precisar via `(await get_config())["minha_chave"]`.
3. Em `app/painel/templates/config.html`: adicione o campo; se for `int`, inclua o nome
   em `_CAMPOS_INT` dentro de `app/painel/rotas.py`.

## Rodar testes
`.venv/Scripts/python.exe -m pytest`
```

- [ ] **Step 2: Criar `CLAUDE.md`**

```markdown
# CLAUDE.md
Veja **AGENTS.md** para a arquitetura e os guias de extensão (criar tools, configs).
Stack roda em Python 3.12. Testes: `.venv/Scripts/python.exe -m pytest`.
```

- [ ] **Step 3: Rodar a suíte completa**

Run: `.venv/Scripts/python.exe -m pytest -v`
Expected: todos os testes passam.

- [ ] **Step 4: Commit**

```bash
git add AGENTS.md CLAUDE.md
git commit -m "docs: AGENTS.md com guia de extensão (tools/configs) + CLAUDE.md"
```

---

## Encerramento

- [ ] **Remover o monólito antigo e o smoke test temporário**

```bash
git rm "agente_whatsapp (1).py" smoke_test.py
git commit -m "chore: remover monólito e smoke test temporário (substituídos por app/)"
```

> O comportamento do agente em produção é idêntico ao original; o que mudou é a
> organização (módulos), a origem dos ajustes (config ao vivo) e o painel `/admin`.
