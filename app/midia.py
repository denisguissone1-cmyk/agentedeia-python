"""Download e análise de mídias recebidas no WhatsApp (áudio, imagem, documento)."""
import asyncio
import base64
import io
import logging
import re

from app import clientes
from app.config import get_tokens

logger = logging.getLogger(__name__)


async def converter_para_mp3(audio_bytes: bytes) -> bytes | None:
    """Converte o áudio recebido (ogg/opus do WhatsApp) para MP3 via ffmpeg.

    MP3 toca no iPhone/Safari (o ogg/opus não). Retorna None se o ffmpeg não estiver
    disponível ou falhar — aí o chamador guarda o áudio original.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-i", "pipe:0", "-vn", "-f", "mp3", "-b:a", "64k", "pipe:1",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await proc.communicate(input=audio_bytes)
        if proc.returncode == 0 and out:
            return out
        logger.warning(f"ffmpeg falhou (rc={proc.returncode}): {err[:200].decode(errors='ignore')}")
    except FileNotFoundError:
        logger.warning("ffmpeg não encontrado — guardando áudio no formato original")
    except Exception as exc:
        logger.warning(f"Falha ao converter áudio para MP3: {exc}")
    return None


async def baixar_midia(id_msg: str) -> bytes:
    tokens = await get_tokens()
    if not tokens.get("uazapi_url") or not tokens.get("uazapi_token"):
        raise RuntimeError("UAZAPI_URL/UAZAPI_TOKEN não configurados")
    if clientes.http_client is None:
        raise RuntimeError("cliente HTTP ainda não foi inicializado")
    resposta = await clientes.http_client.post(
        f"{tokens['uazapi_url']}/message/download",
        headers={"token": tokens["uazapi_token"]},
        json={"id": id_msg, "return_base64": True},
    )
    resposta.raise_for_status()
    payload = resposta.json()
    dados = payload.get("base64Data") or payload.get("base64")
    if not dados and isinstance(payload.get("data"), dict):
        dados = payload["data"].get("base64Data") or payload["data"].get("base64")
    if not dados:
        raise RuntimeError("UAZAPI não retornou base64Data ao baixar a mídia")
    if isinstance(dados, str) and dados.startswith("data:") and "," in dados:
        dados = dados.split(",", 1)[1]
    try:
        return base64.b64decode(re.sub(r"\s+", "", dados), validate=True)
    except Exception as exc:
        raise RuntimeError("base64 da mídia retornado pela UAZAPI é inválido") from exc


def _mime_audio(mimetype: str | None) -> str:
    mime = (mimetype or "audio/ogg").split(";", 1)[0].strip().lower()
    return mime if mime.startswith("audio/") else "audio/ogg"


def _nome_audio(mime: str) -> str:
    extensao = {
        "audio/ogg": ".ogg", "audio/opus": ".opus", "audio/webm": ".webm",
        "audio/mp4": ".mp4", "audio/mpeg": ".mp3", "audio/wav": ".wav",
        "audio/x-wav": ".wav",
    }.get(mime, ".ogg")
    return f"audio{extensao}"


async def _transcrever_openai(audio_bytes: bytes, mime: str) -> str:
    if clientes.openai_client is None:
        raise RuntimeError("OPENAI_API_KEY não configurada")
    transcricao = await clientes.openai_client.audio.transcriptions.create(
        model="whisper-1",
        file=(_nome_audio(mime), io.BytesIO(audio_bytes), mime),
        language="pt",
    )
    texto = (getattr(transcricao, "text", "") or "").strip()
    if not texto:
        raise RuntimeError("Whisper retornou uma transcrição vazia")
    return texto


async def _transcrever_gemini(audio_bytes: bytes, mime: str) -> str:
    if clientes._genai_model is None:
        raise RuntimeError("modelo Gemini não configurado para transcrição")
    resposta = await clientes._genai_model.generate_content_async([
        "Transcreva este áudio em português do Brasil. Retorne somente o que foi falado, "
        "sem comentários, rótulos ou explicações.",
        {"mime_type": mime, "data": audio_bytes},
    ])
    texto = (getattr(resposta, "text", "") or "").strip()
    if not texto:
        raise RuntimeError("Gemini retornou uma transcrição vazia")
    return texto


async def transcrever_bytes(audio_bytes: bytes, mimetype: str = "audio/ogg") -> str:
    """Transcreve com Whisper e usa o Gemini como fallback configurado no agente."""
    mime = _mime_audio(mimetype)
    erros = []
    for transcritor in (_transcrever_openai, _transcrever_gemini):
        try:
            return await transcritor(audio_bytes, mime)
        except Exception as exc:
            erros.append(f"{type(exc).__name__}: {exc}")
            logger.warning("Falha na transcrição com %s: %s", transcritor.__name__, exc)
    raise RuntimeError("Não foi possível transcrever o áudio (" + "; ".join(erros) + ")")


async def transcrever_audio(id_msg: str) -> str:
    return await transcrever_bytes(await baixar_midia(id_msg))


async def analisar_imagem(id_msg: str, mimetype: str = "image/jpeg") -> str:
    imagem_bytes = await baixar_midia(id_msg)
    imagem_b64   = base64.b64encode(imagem_bytes).decode()
    resposta = await clientes.openai_client.chat.completions.create(
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
    doc_bytes = await baixar_midia(id_msg)
    doc_b64   = base64.b64encode(doc_bytes).decode()
    resposta  = await clientes._genai_model.generate_content_async([
        "Descreva detalhadamente o documento e todos os pontos relevantes.",
        {"mime_type": mimetype, "data": doc_b64},
    ])
    return resposta.text


async def processar_conteudo(dados: dict) -> dict:
    """Processa a mensagem por tipo e devolve {texto, tipo, audio_id}.

    Para áudio: baixa uma vez, guarda os bytes no Postgres (para o painel tocar) e
    transcreve. `audio_id` aponta para a rota /media/audio/<id>; é None para os demais.
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
            from app import audios
            audio_bytes = await baixar_midia(id_msg)
            audio_id = None
            try:
                mp3 = await converter_para_mp3(audio_bytes)
                if mp3:
                    audio_id = await audios.salvar(dados.get("number", ""), "audio/mpeg", mp3)
                else:
                    audio_id = await audios.salvar(
                        dados.get("number", ""), dados.get("mimetype", "audio/ogg"), audio_bytes
                    )
            except Exception as exc:
                logger.warning(f"Falha ao guardar áudio {id_msg}: {exc}")
            return {"texto": await transcrever_bytes(audio_bytes, dados.get("mimetype", "audio/ogg")),
                    "tipo": "AudioMessage", "audio_id": audio_id}
        elif tipo == "ImageMessage":
            texto = await analisar_imagem(id_msg, dados.get("mimetype", "image/jpeg"))
            return {"texto": texto, "tipo": "ImageMessage", "audio_id": None}
        elif tipo == "DocumentMessage":
            texto = await analisar_documento(id_msg, dados.get("mimetype", "application/pdf"))
            return {"texto": texto, "tipo": "DocumentMessage", "audio_id": None}
        else:
            return {"texto": dados.get("txtmessage", ""), "tipo": "texto", "audio_id": None}
    except Exception as exc:
        logger.warning(f"Falha ao processar mídia {tipo}/{id_msg}: {exc}")
        return {"texto": _fallbacks.get(tipo, dados.get("txtmessage", "")),
                "tipo": tipo or "texto", "audio_id": None}


async def processar_mensagem_por_tipo(dados: dict) -> str:
    """Compat: devolve só o texto (usado onde o tipo não importa)."""
    return (await processar_conteudo(dados))["texto"]
