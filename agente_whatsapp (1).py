# =============================================================================
# AGENTE WHATSAPP — VERSÃO PRODUÇÃO
# SB Fisio | Elizabeth | n8n → Python/FastAPI
# =============================================================================
#
# COMO LER:
#   Leia de cima para baixo. Cada seção tem título e comentários leigo-friendly.
#   "C1–C5", "I1–I7", "P1–P5" = referências dos gaps corrigidos na auditoria.
#
# DEPENDÊNCIAS:
#   pip install fastapi uvicorn "redis[asyncio]" supabase openai httpx tenacity
#               python-dotenv langchain langchain-google-genai langchain-community
#               pytz psycopg2-binary google-api-python-client google-auth
#               google-generativeai
#
# VARIÁVEIS DE AMBIENTE (.env):
#   SUPABASE_URL, SUPABASE_KEY, REDIS_URL, OPENAI_API_KEY, GOOGLE_API_KEY
#   UAZAPI_TOKEN, UAZAPI_URL, POSTGRES_CONN
#   GOOGLE_CALENDAR_ID, GOOGLE_CALENDAR_CREDS=/path/service-account.json
#   WEBHOOK_TOKEN=<uuid-secreto>
# =============================================================================


# ─────────────────────────────────────────────────────────────────────────────
# SEÇÃO 1 │ IMPORTAÇÕES
# Tudo no topo — C4: import dentro de função causa re-configure() em threads.
# ─────────────────────────────────────────────────────────────────────────────

import asyncio
import base64
import hmac          # P2: comparação segura de tokens
import io
import json
import logging
import os
import threading     # C3: lock thread-safe para Calendar service
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

import google.generativeai as genai          # C4: topo, configure() no startup
import httpx
import pytz
import redis.asyncio as aioredis
from dotenv import load_dotenv
from fastapi import FastAPI, BackgroundTasks, Header, HTTPException, Request
from google.oauth2 import service_account                # topo — não recria por chamada
from googleapiclient.discovery import build as gcal_build
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.tools import tool
from langchain_community.chat_message_histories import PostgresChatMessageHistory
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_google_genai import ChatGoogleGenerativeAI
from openai import AsyncOpenAI
from supabase import create_client
from tenacity import (     # I2: retry com backoff
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# SEÇÃO 2 │ CONFIGURAÇÕES
# ─────────────────────────────────────────────────────────────────────────────

load_dotenv()

SUPABASE_URL          = os.getenv("SUPABASE_URL")
SUPABASE_KEY          = os.getenv("SUPABASE_KEY")
REDIS_URL             = os.getenv("REDIS_URL", "redis://localhost:6379")
OPENAI_API_KEY        = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY        = os.getenv("GOOGLE_API_KEY")
UAZAPI_TOKEN          = os.getenv("UAZAPI_TOKEN")
UAZAPI_URL            = os.getenv("UAZAPI_URL")
POSTGRES_CONN         = os.getenv("POSTGRES_CONN")
GOOGLE_CALENDAR_ID    = os.getenv("GOOGLE_CALENDAR_ID")
GOOGLE_CALENDAR_CREDS = os.getenv("GOOGLE_CALENDAR_CREDS")
WEBHOOK_TOKEN         = os.getenv("WEBHOOK_TOKEN", "")

# Tuning de comportamento
BUFFER_SEGUNDOS        = 6
RATE_LIMIT_MAX         = 30    # mensagens por RATE_LIMIT_JANELA segundos
RATE_LIMIT_JANELA      = 60
HISTORICO_MAX          = 40    # C1: máximo de mensagens no contexto do agente
AGENT_TIMEOUT_SEGUNDOS = 30    # C5: mata o agente se travar


# ─────────────────────────────────────────────────────────────────────────────
# SEÇÃO 3 │ CLIENTES GLOBAIS
# I1: http_client criado uma vez no lifespan, reutilizado em todas as chamadas.
# ─────────────────────────────────────────────────────────────────────────────

supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
openai_client   = AsyncOpenAI(api_key=OPENAI_API_KEY)
redis_client    = aioredis.from_url(REDIS_URL, decode_responses=False)

llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash",
    google_api_key=GOOGLE_API_KEY,
    temperature=0.3,
)

# I1: será inicializado no lifespan do FastAPI
http_client: Optional[httpx.AsyncClient] = None

# C3: lock + variável global para evitar criação duplicada em threads paralelas
_calendar_lock    = threading.Lock()
_calendar_service = None

# C4: modelo genai global (configure() chamado no lifespan, não em cada request)
_genai_model: Optional[genai.GenerativeModel] = None


def get_calendar_service():
    """
    Retorna o cliente do Google Calendar, criando uma única vez (thread-safe).
    C3: threading.Lock evita que duas threads criem o serviço simultaneamente.
    """
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
    """
    Roda no startup e shutdown do servidor.
    I1: cria o http_client global uma vez.
    C4: configura o genai uma vez (não em cada request).
    """
    global http_client, _genai_model

    # Startup
    http_client  = httpx.AsyncClient(timeout=30.0)
    genai.configure(api_key=GOOGLE_API_KEY)
    _genai_model = genai.GenerativeModel("gemini-1.5-flash")
    logger.info("Servidor iniciado — clientes HTTP e Gemini prontos")

    yield  # servidor rodando

    # Shutdown
    await http_client.aclose()
    logger.info("Servidor encerrado — clientes fechados")


# ─────────────────────────────────────────────────────────────────────────────
# SEÇÃO 4 │ HELPERS
# ─────────────────────────────────────────────────────────────────────────────

async def supabase_async(operacao):
    """Roda operação síncrona do Supabase em thread separada (não trava o loop)."""
    return await asyncio.to_thread(operacao)


def calcular_typing_ms(texto: str) -> int:
    """
    I6: simula velocidade de digitação proporcional ao texto.
    ~200 chars/s de "pensar + digitar". Mínimo 1s, máximo 5s.
    """
    ms = int((len(texto) / 200) * 1000)
    return max(1000, min(ms, 5000))


def nova_requisicao_id() -> str:
    """P5: ID curto para correlacionar logs de uma mesma mensagem."""
    return uuid.uuid4().hex[:8]


# ─────────────────────────────────────────────────────────────────────────────
# SEÇÃO 5 │ EXTRAÇÃO DE VARIÁVEIS DO WEBHOOK
# ─────────────────────────────────────────────────────────────────────────────

def extrair_variaveis(body: dict) -> dict:
    mensagem = body.get("message", {})
    chat     = body.get("chat", {})
    return {
        "number":      mensagem.get("chatid", ""),
        "nome":        chat.get("wa_name", ""),
        "txtmessage":  mensagem.get("text", ""),
        "messagetype": mensagem.get("messageType", ""),
        # C2: uazapi pode trazer mimetype; fallback = JPEG (padrão do WhatsApp)
        "mimetype":    mensagem.get("mimetype", "image/jpeg"),
        "timestamp":   mensagem.get("messageTimestamp", 0),
        "id_msg":      mensagem.get("messageid", ""),
        "human":       mensagem.get("fromMe", False),
        "is_group":    mensagem.get("isGroup", False),
    }


# ─────────────────────────────────────────────────────────────────────────────
# SEÇÃO 6 │ DEDUPLICAÇÃO E RATE LIMITING
# ─────────────────────────────────────────────────────────────────────────────

async def ja_processada(number: str, id_msg: str) -> bool:
    """
    I5: chave inclui `number` para evitar colisão entre instâncias diferentes.
    Marca a mensagem como processada por 60 segundos.
    """
    if not id_msg:
        return False
    nova = await redis_client.set(f"msg_seen:{number}:{id_msg}", "1", ex=60, nx=True)
    return nova is None  # None = chave já existia = duplicata


async def verifica_rate_limit(number: str) -> str:
    """
    I7: retorna o status do rate limit para o número.

    Retorna:
      "ok"      → dentro do limite, processa normalmente
      "aviso"   → primeiro bloqueio — avisa o usuário uma vez
      "bloqueado" → silenciosamente ignora mensagens excedentes
    """
    chave    = f"ratelimit:{number}"
    contador = await redis_client.incr(chave)
    if contador == 1:
        await redis_client.expire(chave, RATE_LIMIT_JANELA)

    if contador <= RATE_LIMIT_MAX:
        return "ok"
    elif contador == RATE_LIMIT_MAX + 1:
        return "aviso"       # avisa apenas na primeira mensagem bloqueada
    return "bloqueado"


# ─────────────────────────────────────────────────────────────────────────────
# SEÇÃO 7 │ CADASTRO
# ─────────────────────────────────────────────────────────────────────────────

async def verificar_ou_criar_cadastro(number: str) -> dict:
    """Garante que o contato existe no Supabase (upsert = cria se não existir)."""
    def _executar():
        return (
            supabase_client.table("cadastro")
            .upsert({"remoteJid": number}, on_conflict="remoteJid")
            .execute()
        )
    resultado = await supabase_async(_executar)
    return resultado.data[0] if resultado.data else {}


# ─────────────────────────────────────────────────────────────────────────────
# SEÇÃO 8 │ MEMÓRIA DA CONVERSA
#
# PostgresChatMessageHistory é síncrono — usamos to_thread.
# Para alto volume, migrar para langchain_postgres com pool asyncpg.
# ─────────────────────────────────────────────────────────────────────────────

async def inserir_na_memoria(number: str, texto: str, role: str = "human"):
    """Salva uma mensagem isolada no histórico (ex: mensagem do atendente humano)."""
    if not texto.strip():
        return

    def _inserir():
        hist = PostgresChatMessageHistory(
            connection_string=POSTGRES_CONN,
            session_id=f"{number}_chat",
        )
        msg = HumanMessage(content=texto) if role == "human" else AIMessage(content=texto)
        hist.add_message(msg)

    await asyncio.to_thread(_inserir)


async def carregar_historico(number: str) -> list:
    """
    Carrega o histórico do Postgres e fatia para HISTORICO_MAX mensagens.
    C1: sem limite → estoura context window. Com limite em pares para não
    deixar o histórico começar com mensagem da IA sem a pergunta humana.
    P3: agora retorna apenas a lista de mensagens (sem tupla desnecessária).
    """
    def _carregar():
        hist = PostgresChatMessageHistory(
            connection_string=POSTGRES_CONN,
            session_id=f"{number}_chat",
        )
        msgs = hist.messages

        if len(msgs) > HISTORICO_MAX:
            msgs = msgs[-HISTORICO_MAX:]
            # Garante que começa numa mensagem humana (mantém pares)
            if msgs and isinstance(msgs[0], AIMessage):
                msgs = msgs[1:]

        return msgs

    return await asyncio.to_thread(_carregar)


async def salvar_par_conversa(number: str, pergunta: str, resposta: str):
    """Salva o par pergunta/resposta após o agente responder."""
    def _salvar():
        hist = PostgresChatMessageHistory(
            connection_string=POSTGRES_CONN,
            session_id=f"{number}_chat",
        )
        hist.add_message(HumanMessage(content=pergunta))
        hist.add_message(AIMessage(content=resposta))

    await asyncio.to_thread(_salvar)


# ─────────────────────────────────────────────────────────────────────────────
# SEÇÃO 9 │ VERIFICAÇÃO DE BLOQUEIOS
# ─────────────────────────────────────────────────────────────────────────────

async def verificar_bloqueios_rapido(dados: dict) -> str:
    number = dados["number"]

    if dados.get("is_group"):
        return "bloquear_wpp"

    # I4: fromMe pode chegar como bool True, string "true", int 1 — bool() cobre todos
    if bool(dados["human"]) and dados["human"] not in (False, "false", "False", 0):
        await redis_client.set(f"{number}_block", "true", ex=900)  # 15 min
        return "bloquear_humano_bot"

    block_wpp = await redis_client.get("block_wpp")
    if block_wpp == b"true":
        return "bloquear_wpp"

    block_individual = await redis_client.get(f"{number}_block")
    if block_individual == b"true":
        return "bloquear_individual"

    return "processar"


# ─────────────────────────────────────────────────────────────────────────────
# SEÇÃO 10 │ DOWNLOAD E ANÁLISE DE MÍDIA
# ─────────────────────────────────────────────────────────────────────────────

async def baixar_midia(id_msg: str) -> bytes:
    """I1: usa o http_client global — sem novo handshake TCP a cada chamada."""
    resposta = await http_client.post(
        f"{UAZAPI_URL}/message/download",
        headers={"token": UAZAPI_TOKEN},
        json={"id": id_msg, "return_base64": True},
    )
    resposta.raise_for_status()
    return base64.b64decode(resposta.json()["base64Data"])


async def transcrever_audio(id_msg: str) -> str:
    audio_bytes = await baixar_midia(id_msg)
    transcricao = await openai_client.audio.transcriptions.create(
        model="whisper-1",
        file=("audio.ogg", io.BytesIO(audio_bytes), "audio/ogg"),
        language="pt",
    )
    return transcricao.text


async def analisar_imagem(id_msg: str, mimetype: str = "image/jpeg") -> str:
    """
    C2: usa o mimetype real da mensagem.
    WhatsApp sempre comprime fotos em JPEG — o padrão PNG estava errado.
    """
    imagem_bytes = await baixar_midia(id_msg)
    imagem_b64   = base64.b64encode(imagem_bytes).decode()
    resposta = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Analise a imagem. Se não estiver legível, responda: [Imagem ilegível]",
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mimetype};base64,{imagem_b64}"},
                },
            ],
        }],
    )
    return resposta.choices[0].message.content


async def analisar_documento(id_msg: str, mimetype: str = "application/pdf") -> str:
    """
    I3: usa generate_content_async — nativo async, sem to_thread.
    C4: _genai_model já configurado no lifespan, não reconfigura aqui.
    Aceita qualquer mimetype de documento que o Gemini suporte.
    """
    doc_bytes = await baixar_midia(id_msg)
    doc_b64   = base64.b64encode(doc_bytes).decode()
    resposta  = await _genai_model.generate_content_async([
        "Descreva detalhadamente o documento e todos os pontos relevantes.",
        {"mime_type": mimetype, "data": doc_b64},
    ])
    return resposta.text


async def processar_mensagem_por_tipo(dados: dict) -> str:
    """
    Roteador de tipos de mensagem.
    Try/except por tipo: falha em áudio não derruba a mensagem inteira.
    """
    tipo   = dados["messagetype"]
    id_msg = dados["id_msg"]

    _fallbacks = {
        "AudioMessage":    "[Áudio não pôde ser transcrito]",
        "ImageMessage":    "[Imagem não pôde ser analisada]",
        "DocumentMessage": "[Documento não pôde ser lido]",
    }

    try:
        if tipo == "AudioMessage":
            return await transcrever_audio(id_msg)
        elif tipo == "ImageMessage":
            return await analisar_imagem(id_msg, dados.get("mimetype", "image/jpeg"))
        elif tipo == "DocumentMessage":
            return await analisar_documento(id_msg, dados.get("mimetype", "application/pdf"))
        else:
            return dados.get("txtmessage", "")
    except Exception as exc:
        logger.warning(f"Falha ao processar mídia {tipo}/{id_msg}: {exc}")
        return _fallbacks.get(tipo, dados.get("txtmessage", ""))


# ─────────────────────────────────────────────────────────────────────────────
# SEÇÃO 11 │ BUFFER DE MENSAGENS (DEBOUNCE DESLIZANTE)
#
# Cada nova mensagem sobrescreve o token no Redis.
# Após BUFFER_SEGUNDOS, a última mensagem que chegou "ganha" e processa tudo.
# ─────────────────────────────────────────────────────────────────────────────

async def buffer_mensagens(number: str, mensagem_json: str) -> Optional[list[str]]:
    chave_lista     = f"{number}:msgs"
    chave_atividade = f"{number}:atividade"

    await redis_client.rpush(chave_lista, mensagem_json)
    # TTL: se o servidor crashar após o RPUSH, a lista expira em vez de ficar
    # suja no Redis e contaminar mensagens de uma sessão futura do mesmo número.
    await redis_client.expire(chave_lista, 120)

    # P1: time_ns() → resolução de nanosegundo, colisão praticamente impossível
    meu_token = str(time.time_ns())
    await redis_client.set(chave_atividade, meu_token, ex=120)

    await asyncio.sleep(BUFFER_SEGUNDOS)

    # Verifica se ainda somos os "donos" do turno
    valor_salvo = await redis_client.get(chave_atividade)
    if not valor_salvo or valor_salvo.decode() != meu_token:
        return None  # Outra mensagem chegou depois — essa execução descarta

    mensagens_raw = await redis_client.lrange(chave_lista, 0, -1)
    await redis_client.delete(chave_lista)
    return [m.decode() for m in mensagens_raw]


# ─────────────────────────────────────────────────────────────────────────────
# SEÇÃO 12 │ TOOLS DO AGENTE
# ─────────────────────────────────────────────────────────────────────────────

def criar_tool_cadastrar(number: str):
    """
    Cria a tool de cadastro com o `number` capturado no closure.
    Isso é necessário porque tools LangChain não recebem contexto de sessão.
    """
    @tool
    async def cadastrar(nome: str) -> str:
        """
        Salva o nome do paciente no banco de dados.
        Use SOMENTE UMA VEZ quando o usuário fornecer um nome próprio válido (1 a 3 palavras).
        NÃO use para saudações como 'Oi' ou 'Bom dia'.
        """
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


@tool
async def buscar_info(pergunta: str) -> str:
    """
    Busca informações na base de conhecimento da clínica (convênios, procedimentos, regras).
    Use como fonte de verdade absoluta — nunca invente informações.
    """
    # TODO: substituir pelo RAG real (busca vetorial no Supabase/pgvector)
    return f"[Resultado da busca: {pergunta}]"


@tool
async def consultar_agenda(after: str, before: str) -> str:
    """
    Consulta os agendamentos da clínica entre duas datas.
    SEMPRE use ANTES de pre_marcacao para evitar conflitos de horário.

    Parâmetros:
      after  — data/hora de início ISO 8601 (ex: '2026-05-06T08:00:00-03:00')
      before — data/hora de fim ISO 8601   (ex: '2026-05-08T19:00:00-03:00')
    """
    def _consultar():
        service = get_calendar_service()
        result  = service.events().list(
            calendarId   = GOOGLE_CALENDAR_ID,
            timeMin      = after,
            timeMax      = before,
            timeZone     = "America/Sao_Paulo",
            singleEvents = True,
            orderBy      = "startTime",
        ).execute()
        return result.get("items", [])

    eventos = await asyncio.to_thread(_consultar)
    return json.dumps(
        [
            {
                "id":      e.get("id"),
                "summary": e.get("summary", ""),
                "start":   e["start"].get("dateTime", e["start"].get("date")),
                "end":     e["end"].get("dateTime", e["end"].get("date")),
            }
            for e in eventos
        ],
        ensure_ascii=False,
    )


@tool
async def pre_marcacao(start: str, end: str, summary: str, description: str) -> str:
    """
    Cria uma pré-marcação na agenda da clínica.
    SEMPRE use consultar_agenda antes para evitar conflitos de horário.

    Parâmetros:
      start       — início ISO 8601
      end         — fim ISO 8601
      summary     — nome completo do paciente
      description — Procedimento, Convênio (ou Particular), Dados do paciente, Valor
    """
    def _criar():
        service = get_calendar_service()
        evento  = {
            "summary":     summary,
            "description": description,
            "start":       {"dateTime": start, "timeZone": "America/Sao_Paulo"},
            "end":         {"dateTime": end,   "timeZone": "America/Sao_Paulo"},
        }
        return service.events().insert(
            calendarId=GOOGLE_CALENDAR_ID, body=evento
        ).execute()

    resultado = await asyncio.to_thread(_criar)
    return f"Pré-marcação criada com ID {resultado.get('id')}."


@tool
async def desmarcar(event_id: str) -> str:
    """
    Cancela uma pré-marcação existente.
    Use consultar_agenda antes para obter o ID correto do evento.

    Parâmetros:
      event_id — ID retornado por consultar_agenda
    """
    def _deletar():
        service = get_calendar_service()
        service.events().delete(
            calendarId=GOOGLE_CALENDAR_ID, eventId=event_id
        ).execute()

    await asyncio.to_thread(_deletar)
    return f"Agendamento {event_id} cancelado."


# ─────────────────────────────────────────────────────────────────────────────
# SEÇÃO 13 │ AGENTE DE IA
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """# ROLE

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

# TOOLS

cadastrar:        Use SOMENTE UMA VEZ quando o lead fornecer o nome dele.
buscar_info:      Use para validar convênios, procedimentos e regras da clínica.
consultar_agenda: SEMPRE use antes de pre_marcacao para evitar conflitos.
pre_marcacao:     Use silenciosamente após confirmar os dados com o paciente.
desmarcar:        Use para cancelar uma pré-marcação existente.

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


async def chamar_agente(number: str, texto_completo: str, cadastro: dict) -> str:
    """
    Chama o agente com histórico + contexto e persiste a resposta.
    C5: asyncio.wait_for garante que o agente não trava para sempre.
    P3: carregar_historico agora retorna lista diretamente.
    """
    mensagens_historico = await carregar_historico(number)

    tool_cadastrar = criar_tool_cadastrar(number)
    tools          = [tool_cadastrar, buscar_info, consultar_agenda, pre_marcacao, desmarcar]

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="historico"),
        ("human", "{mensagem}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    agente   = create_tool_calling_agent(llm, tools, prompt)
    executor = AgentExecutor(agent=agente, tools=tools, verbose=False)

    agora = datetime.now(pytz.timezone("America/Sao_Paulo"))

    # C5: timeout de 30s — se o Gemini/Calendar travar, não fica pendurado
    resposta = await asyncio.wait_for(
        executor.ainvoke({
            "mensagem":        texto_completo,
            "historico":       mensagens_historico,
            "status_paciente": "Cliente conhecido" if cadastro.get("nomeusuario") else "Primeiro Contato",
            "nome_paciente":   cadastro.get("nomeusuario") or "Ainda não foi fornecido",
            "data_hora":       agora.strftime("%H:%M - %A - %d/%m/%Y"),
            "numero":          number.split("@")[0],
        }),
        timeout=AGENT_TIMEOUT_SEGUNDOS,
    )

    texto_resposta = resposta["output"]
    await salvar_par_conversa(number, texto_completo, texto_resposta)
    return texto_resposta


# ─────────────────────────────────────────────────────────────────────────────
# SEÇÃO 14 │ ENVIO DE MENSAGENS
# ─────────────────────────────────────────────────────────────────────────────

class ErroCliente(Exception):
    """Erro 4xx da uazapi — não deve ser retentado (problema no nosso request)."""


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception(lambda e: not isinstance(e, ErroCliente)),
    reraise=True,
)
async def _enviar_texto_raw(
    number: str, texto: str, delay_ms: int, marcar_lido: bool
) -> None:
    """
    I2: retry automático em falhas transitórias (5xx, timeout).
    Não retenta em erros 4xx (token errado, número inválido, etc).
    I1: usa http_client global — sem novo handshake TCP.
    """
    resp = await http_client.post(
        f"{UAZAPI_URL}/send/text",
        headers={"token": UAZAPI_TOKEN, "Accept": "application/json"},
        json={
            "number":       number,
            "text":         texto,
            "delay":        delay_ms,
            "readmessages": marcar_lido,
        },
    )
    if 400 <= resp.status_code < 500:
        raise ErroCliente(f"uazapi {resp.status_code}: {resp.text[:100]}")
    resp.raise_for_status()


async def enviar_aviso_rate_limit(number: str) -> None:
    """I7: avisa o usuário quando ele mandou mensagens demais."""
    aviso = "Recebi muitas mensagens ao mesmo tempo\n\nVou responder tudo em instantes"
    try:
        await _enviar_texto_raw(number, aviso, delay_ms=1000, marcar_lido=False)
    except Exception:
        pass


async def enviar_typing(number: str, duracao_ms: int) -> None:
    """Mostra 'digitando...' no WhatsApp do cliente. I6: duração proporcional."""
    try:
        await http_client.post(
            f"{UAZAPI_URL}/message/sendPresence",
            headers={"token": UAZAPI_TOKEN, "Accept": "application/json"},
            json={"number": number, "presence": "composing", "delay": duracao_ms},
        )
    except Exception:
        pass  # Typing é cosmético — não pode derrubar o envio principal


async def enviar_texto(
    number: str, texto: str, marcar_lido: bool = False
) -> None:
    """Calcula delay humanizado e chama _enviar_texto_raw."""
    velocidade = 800 / 60  # chars por segundo
    delay_ms   = int((len(texto) / velocidade) * 1000)
    delay_ms   = max(1000, min(delay_ms, 8000))
    await _enviar_texto_raw(number, texto, delay_ms, marcar_lido)


async def enviar_resposta(number: str, texto: str) -> None:
    """
    Divide em parágrafos e envia com typing proporcional.
    I1: sem criar novo AsyncClient a cada chamada.
    I6: typing ms proporcional ao tamanho do parágrafo.
    """
    paragrafos = [p.strip() for p in texto.split("\n\n") if p.strip()]
    for i, paragrafo in enumerate(paragrafos):
        await enviar_typing(number, calcular_typing_ms(paragrafo))
        await enviar_texto(number, paragrafo, marcar_lido=(i == 0))


async def enviar_fallback(number: str) -> None:
    """Mensagem de emergência quando o agente falha — cliente nunca fica no vácuo."""
    fallback = "Tive um probleminha técnico aqui\n\nPode mandar a mensagem de novo em alguns segundos?"
    try:
        await enviar_texto(number, fallback, marcar_lido=True)
    except Exception as exc:
        logger.error(f"Falha até no fallback para {number}: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# SEÇÃO 15 │ PROCESSAMENTO PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

async def processar_em_background(body: dict) -> None:
    """
    Orquestra todo o fluxo de uma mensagem recebida.
    P5: req_id permite rastrear logs de ponta a ponta.
    """
    req_id = nova_requisicao_id()
    number = "?"

    try:
        dados  = extrair_variaveis(body)
        number = dados["number"]

        if not number:
            return

        logger.info(f"[{req_id}] [{number}] Mensagem recebida tipo={dados['messagetype']}")

        # Deduplicação
        if await ja_processada(number, dados["id_msg"]):
            logger.info(f"[{req_id}] [{number}] Duplicata ignorada")
            return

        # Rate limiting
        rate = await verifica_rate_limit(number)
        if rate == "aviso":
            logger.warning(f"[{req_id}] [{number}] Rate limit — avisando usuário")
            await enviar_aviso_rate_limit(number)
            return
        elif rate == "bloqueado":
            logger.warning(f"[{req_id}] [{number}] Rate limit — ignorando silenciosamente")
            return

        # Bloqueios (grupos, atendente humano, pausa individual)
        status = await verificar_bloqueios_rapido(dados)

        if status == "bloquear_humano_bot":
            await inserir_na_memoria(number, dados["txtmessage"], role="ai")
            logger.info(f"[{req_id}] [{number}] Atendente humano assumiu — bot silenciado")
            return

        if status == "bloquear_wpp":
            return

        # Processamento de mídia (áudio/imagem/documento)
        texto_mensagem = await processar_mensagem_por_tipo(dados)

        if status == "bloquear_individual":
            await inserir_na_memoria(number, texto_mensagem, role="human")
            logger.info(f"[{req_id}] [{number}] Mensagem salva em silêncio (bloqueio individual)")
            return

        # Cadastro
        cadastro = await verificar_ou_criar_cadastro(number)

        # Buffer: agrupa mensagens rápidas em uma única chamada ao agente
        mensagem_para_buffer = json.dumps({
            "txtmessage": texto_mensagem,
            "timestamp":  dados["timestamp"],
            "id_msg":     dados["id_msg"],
        })

        mensagens = await buffer_mensagens(number, mensagem_para_buffer)
        if mensagens is None:
            return  # Outra mensagem chegou depois — ela vai processar

        textos         = [json.loads(m)["txtmessage"] for m in mensagens if m]
        texto_completo = "\n".join(t for t in textos if t.strip())

        if not texto_completo.strip():
            return

        # Agente de IA
        logger.info(f"[{req_id}] [{number}] Enviando ao agente ({len(texto_completo)} chars)")
        try:
            texto_resposta = await chamar_agente(number, texto_completo, cadastro)
        except asyncio.TimeoutError:
            logger.error(f"[{req_id}] [{number}] Timeout no agente ({AGENT_TIMEOUT_SEGUNDOS}s)")
            await enviar_fallback(number)
            return
        except Exception as exc:
            logger.error(f"[{req_id}] [{number}] Falha no agente: {exc}", exc_info=True)
            await enviar_fallback(number)
            return

        await enviar_resposta(number, texto_resposta)
        logger.info(f"[{req_id}] [{number}] ✓ Resposta enviada ({len(texto_resposta)} chars)")

    except Exception as exc:
        logger.error(f"[{req_id}] [{number}] Erro inesperado: {exc}", exc_info=True)


# ─────────────────────────────────────────────────────────────────────────────
# SEÇÃO 16 │ ROTAS DO SERVIDOR
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(lifespan=lifespan)


def validar_token_webhook(body: dict) -> None:
    """
    P2: hmac.compare_digest é resistente a timing attacks.
    Sem isso, um atacante poderia inferir o token medindo o tempo de resposta.
    """
    if not WEBHOOK_TOKEN:
        return  # Dev mode — sem token configurado
    token_recebido = body.get("token", "")
    if not hmac.compare_digest(token_recebido, WEBHOOK_TOKEN):
        raise HTTPException(status_code=401, detail="Token inválido")


@app.post("/webhook")
async def receber_mensagem(request: Request, background_tasks: BackgroundTasks):
    """
    Recebe o webhook da uazapi.
    Responde 200 imediatamente e processa em background (não trava a uazapi).
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="JSON inválido")

    validar_token_webhook(body)
    background_tasks.add_task(processar_em_background, body)
    return {"ok": True}


@app.post("/unblock/{number}")
async def desbloquear_numero(number: str, x_admin_token: str = Header(None)):
    """
    Remove o bloqueio individual de um número antes dos 15 minutos automáticos.
    Útil para o atendente "devolver" o cliente ao bot manualmente.
    """
    if not x_admin_token or not hmac.compare_digest(x_admin_token, WEBHOOK_TOKEN):
        raise HTTPException(status_code=401)

    await redis_client.delete(f"{number}_block")
    logger.info(f"Número {number} desbloqueado manualmente")
    return {"ok": True, "numero": number}


@app.get("/health")
async def health():
    """
    P4: health check real — verifica se Redis está respondendo.
    Útil para monitoramento (Uptime Robot, load balancer, etc).
    """
    try:
        await redis_client.ping()
        redis_ok = True
    except Exception:
        redis_ok = False

    return {
        "status": "ok" if redis_ok else "degraded",
        "redis":  redis_ok,
    }


# ─────────────────────────────────────────────────────────────────────────────
# SEÇÃO 17 │ INICIALIZAÇÃO
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
