"""Download e análise de mídias recebidas no WhatsApp (áudio, imagem, documento)."""
import base64
import io
import logging

from app import clientes
from app.config import get_tokens

logger = logging.getLogger(__name__)


async def baixar_midia(id_msg: str) -> bytes:
    tokens = await get_tokens()
    resposta = await clientes.http_client.post(
        f"{tokens['uazapi_url']}/message/download",
        headers={"token": tokens["uazapi_token"]},
        json={"id": id_msg, "return_base64": True},
    )
    resposta.raise_for_status()
    return base64.b64decode(resposta.json()["base64Data"])


async def transcrever_bytes(audio_bytes: bytes) -> str:
    transcricao = await clientes.openai_client.audio.transcriptions.create(
        model="whisper-1",
        file=("audio.ogg", io.BytesIO(audio_bytes), "audio/ogg"),
        language="pt",
    )
    return transcricao.text


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
                audio_id = await audios.salvar(
                    dados.get("number", ""), dados.get("mimetype", "audio/ogg"), audio_bytes
                )
            except Exception as exc:
                logger.warning(f"Falha ao guardar áudio {id_msg}: {exc}")
            return {"texto": await transcrever_bytes(audio_bytes),
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
