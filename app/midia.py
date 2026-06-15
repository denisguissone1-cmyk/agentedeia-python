"""Download e análise de mídias recebidas no WhatsApp (áudio, imagem, documento)."""
import base64
import io
import logging

from app import clientes
from app.clientes import UAZAPI_TOKEN, UAZAPI_URL, openai_client

logger = logging.getLogger(__name__)


async def baixar_midia(id_msg: str) -> bytes:
    """Usa o http_client global — sem novo handshake TCP a cada chamada."""
    resposta = await clientes.http_client.post(
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
    Usa o mimetype real da mensagem.
    WhatsApp sempre comprime fotos em JPEG — o padrão PNG do original estava errado.
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
    Usa generate_content_async — nativo async, sem to_thread.
    _genai_model já configurado no lifespan, não reconfigura aqui.
    """
    doc_bytes = await baixar_midia(id_msg)
    doc_b64   = base64.b64encode(doc_bytes).decode()
    resposta  = await clientes._genai_model.generate_content_async([
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
