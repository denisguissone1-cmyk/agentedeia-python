import asyncio
import hmac
import json
import logging
import uuid

from fastapi import HTTPException
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from app import clientes, eventos
from app.agente import chamar_agente
from app.execucoes import Execucao
from app.bloqueios import ja_processada, verifica_rate_limit, verificar_bloqueios_rapido
from app.buffer import buffer_mensagens
from app.clientes import get_db_conn
from app.config import get_tokens
from app.memoria import inserir_na_memoria
from app.midia import processar_conteudo

logger = logging.getLogger(__name__)


def calcular_typing_ms(texto: str) -> int:
    ms = int((len(texto) / 200) * 1000)
    return max(1000, min(ms, 5000))


def nova_requisicao_id() -> str:
    return uuid.uuid4().hex[:8]


def extrair_variaveis(body: dict) -> dict:
    mensagem = body.get("message", {})
    chat     = body.get("chat", {})
    return {
        "number":      mensagem.get("chatid", ""),
        "nome":        chat.get("wa_name", ""),
        "txtmessage":  mensagem.get("text", ""),
        "messagetype": mensagem.get("messageType", ""),
        "mimetype":    mensagem.get("mimetype", "image/jpeg"),
        "timestamp":   mensagem.get("messageTimestamp", 0),
        "id_msg":      mensagem.get("messageid", ""),
        "human":       mensagem.get("fromMe", False),
        "is_group":    mensagem.get("isGroup", False),
    }


async def verificar_ou_criar_cadastro(number: str) -> dict:
    """Garante que o contato existe no Postgres interno (upsert)."""
    def _executar():
        conn = get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    'INSERT INTO cadastro ("remoteJid") VALUES (%s) '
                    'ON CONFLICT ("remoteJid") DO NOTHING',
                    (number,)
                )
                cur.execute(
                    'SELECT "remoteJid", nomeusuario FROM cadastro WHERE "remoteJid" = %s',
                    (number,)
                )
                row = cur.fetchone()
            conn.commit()
            return dict(row) if row else {}
        finally:
            conn.close()
    return await asyncio.to_thread(_executar)


class ErroCliente(Exception):
    """Erro 4xx da uazapi — não deve ser retentado."""


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception(lambda e: not isinstance(e, ErroCliente)),
    reraise=True,
)
async def _enviar_texto_raw(
    number: str, texto: str, delay_ms: int, marcar_lido: bool
) -> None:
    tokens = await get_tokens()
    resp = await clientes.http_client.post(
        f"{tokens['uazapi_url']}/send/text",
        headers={"token": tokens["uazapi_token"], "Accept": "application/json"},
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
    aviso = "Recebi muitas mensagens ao mesmo tempo\n\nVou responder tudo em instantes"
    try:
        await _enviar_texto_raw(number, aviso, delay_ms=1000, marcar_lido=False)
    except Exception:
        pass


async def enviar_typing(number: str, duracao_ms: int) -> None:
    try:
        tokens = await get_tokens()
        await clientes.http_client.post(
            f"{tokens['uazapi_url']}/message/sendPresence",
            headers={"token": tokens["uazapi_token"], "Accept": "application/json"},
            json={"number": number, "presence": "composing", "delay": duracao_ms},
        )
    except Exception:
        pass


async def enviar_texto(
    number: str, texto: str, marcar_lido: bool = False
) -> None:
    velocidade = 800 / 60
    delay_ms   = int((len(texto) / velocidade) * 1000)
    delay_ms   = max(1000, min(delay_ms, 8000))
    await _enviar_texto_raw(number, texto, delay_ms, marcar_lido)


async def enviar_resposta(number: str, texto: str) -> None:
    paragrafos = [p.strip() for p in texto.split("\n\n") if p.strip()]
    for i, paragrafo in enumerate(paragrafos):
        await enviar_typing(number, calcular_typing_ms(paragrafo))
        await enviar_texto(number, paragrafo, marcar_lido=(i == 0))


async def enviar_fallback(number: str) -> None:
    fallback = "Tive um probleminha técnico aqui\n\nPode mandar a mensagem de novo em alguns segundos?"
    try:
        await enviar_texto(number, fallback, marcar_lido=True)
    except Exception as exc:
        logger.error(f"Falha até no fallback para {number}: {exc}")


async def validar_token_webhook(body: dict) -> None:
    """Valida o token do webhook lendo o valor atual (Redis/painel). Vazio = sem validação."""
    tokens = await get_tokens()
    esperado = tokens.get("webhook_token", "")
    if not esperado:
        return
    recebido = body.get("token", "")
    if not hmac.compare_digest(recebido, esperado):
        raise HTTPException(status_code=401, detail="Token inválido")


async def processar_em_background(body: dict) -> None:
    req_id = nova_requisicao_id()
    number = "?"
    exe = None

    try:
        dados  = extrair_variaveis(body)
        number = dados["number"]

        if not number:
            return

        exe = Execucao(req_id, number)
        exe.passo("Mensagem recebida", f"tipo={dados['messagetype']}")
        logger.info(f"[{req_id}] [{number}] Mensagem recebida tipo={dados['messagetype']}")

        if await ja_processada(number, dados["id_msg"]):
            exe.passo("Duplicata ignorada", "mesma mensagem já processada")
            exe.encerrar("ignorada")
            logger.info(f"[{req_id}] [{number}] Duplicata ignorada")
            return

        rate = await verifica_rate_limit(number)
        if rate == "aviso":
            exe.passo("Rate limit", "muitas mensagens — avisando o usuário")
            exe.encerrar("ignorada")
            logger.warning(f"[{req_id}] [{number}] Rate limit — avisando usuário")
            await enviar_aviso_rate_limit(number)
            await eventos.aviso_rate(dados["nome"], number)
            return
        elif rate == "bloqueado":
            exe.passo("Rate limit", "excedido — ignorando silenciosamente")
            exe.encerrar("ignorada")
            logger.warning(f"[{req_id}] [{number}] Rate limit — ignorando silenciosamente")
            return

        status = await verificar_bloqueios_rapido(dados)

        if status == "bloquear_humano_bot":
            exe.passo("Atendente humano assumiu", "bot pausado nesta conversa")
            exe.encerrar("ignorada")
            await inserir_na_memoria(number, dados["txtmessage"], role="ai")
            logger.info(f"[{req_id}] [{number}] Atendente humano assumiu — bot silenciado")
            await eventos.humano_assumiu(dados["nome"], number)
            return

        if status == "bloquear_wpp":
            exe.passo("Mensagem ignorada", "grupo ou enviada pelo próprio número")
            exe.encerrar("ignorada")
            return

        conteudo       = await processar_conteudo(dados)
        texto_mensagem = conteudo["texto"]
        exe.passo("Conteúdo processado", f"{len(texto_mensagem)} chars ({dados['messagetype']})")
        await eventos.recebida(dados["nome"], number, dados["messagetype"])

        if status == "bloquear_individual":
            exe.passo("Salvo em silêncio", "bloqueio individual ativo")
            exe.encerrar("ignorada")
            await inserir_na_memoria(number, texto_mensagem, role="human")
            logger.info(f"[{req_id}] [{number}] Mensagem salva em silêncio (bloqueio individual)")
            return

        cadastro = await verificar_ou_criar_cadastro(number)
        exe.passo("Cadastro verificado", cadastro.get("nomeusuario") or "novo contato")

        mensagem_para_buffer = json.dumps({
            "txtmessage": texto_mensagem,
            "tipo":       conteudo["tipo"],
            "audio_id":   conteudo["audio_id"],
            "timestamp":  dados["timestamp"],
            "id_msg":     dados["id_msg"],
        })

        mensagens = await buffer_mensagens(number, mensagem_para_buffer)
        if mensagens is None:
            exe.passo("Aguardando agrupar (buffer)", "esperando se chegam mais mensagens")
            exe.encerrar("aguardando")
            return

        agrupadas      = [json.loads(m) for m in mensagens if m]
        textos         = [d.get("txtmessage", "") for d in agrupadas]
        texto_completo = "\n".join(t for t in textos if t.strip())
        # Metadados por mensagem para o painel renderizar áudio + transcrição (não vão ao LLM).
        itens = [
            {"tipo": d.get("tipo", "texto"), "texto": d.get("txtmessage", ""),
             "audio_id": d.get("audio_id")}
            for d in agrupadas if d.get("txtmessage", "").strip() or d.get("audio_id")
        ]

        if not texto_completo.strip():
            exe.passo("Sem texto para enviar", "nada a processar após o buffer")
            exe.encerrar("ignorada")
            return

        exe.passo("Enviando ao agente", f"{len(texto_completo)} chars")
        logger.info(f"[{req_id}] [{number}] Enviando ao agente ({len(texto_completo)} chars)")
        try:
            texto_resposta = await chamar_agente(number, texto_completo, cadastro, itens)
        except asyncio.TimeoutError:
            exe.erro("Agente", "timeout — excedeu o tempo limite")
            logger.error(f"[{req_id}] [{number}] Timeout no agente")
            await enviar_fallback(number)
            return
        except Exception as exc:
            exe.erro("Agente", f"{type(exc).__name__}: {exc}")
            logger.error(f"[{req_id}] [{number}] Falha no agente: {exc}", exc_info=True)
            await enviar_fallback(number)
            return

        exe.passo("Resposta do agente", f"{len(texto_resposta)} chars")
        await enviar_resposta(number, texto_resposta)
        exe.passo("Resposta enviada ao WhatsApp")
        exe.encerrar("sucesso")
        logger.info(f"[{req_id}] [{number}] ✓ Resposta enviada ({len(texto_resposta)} chars)")
        await eventos.respondida(dados["nome"], number)

    except Exception as exc:
        if exe is not None:
            exe.erro("Erro inesperado", f"{type(exc).__name__}: {exc}")
        logger.error(f"[{req_id}] [{number}] Erro inesperado: {exc}", exc_info=True)
    finally:
        if exe is not None:
            await exe.salvar()
