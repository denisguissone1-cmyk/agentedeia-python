import logging

from langchain.tools import tool

from app import clientes, produtos
from app.config import get_tokens, redis_client

logger = logging.getLogger(__name__)
_FOTOS_TTL_SEGUNDOS = 30 * 60


async def _reservar_envio(number: str, pid: int, reenviar: bool) -> bool:
    """Impede chamadas repetidas da mesma foto durante uma conversa curta."""
    chave = f"fotos_enviadas:{number}:{pid}"
    try:
        if reenviar:
            await redis_client.delete(chave)
        reservado = await redis_client.set(chave, "1", ex=_FOTOS_TTL_SEGUNDOS, nx=True)
        return bool(reservado)
    except Exception as exc:
        # Falha do Redis não deve impedir um envio legítimo; a tool continua funcional.
        logger.warning("Não foi possível controlar repetição de fotos: %s", exc)
        return True


async def _liberar_envio(number: str, pid: int) -> None:
    try:
        await redis_client.delete(f"fotos_enviadas:{number}:{pid}")
    except Exception:
        pass


def criar(number: str, descricao: str):
    @tool("enviar_fotos_produto", description=descricao)
    async def enviar_fotos_produto(produto_id: int, reenviar: bool = False) -> str:
        try:
            pid = int(produto_id)
        except (TypeError, ValueError):
            return "produto_id inválido — use o número (#id) do listar_produtos."

        tokens = await get_tokens()
        if not tokens.get("uazapi_url") or not tokens.get("uazapi_token"):
            return "Não consegui enviar as fotos: UAZAPI não está configurada."
        if clientes.http_client is None:
            return "Não consegui enviar as fotos: cliente de comunicação ainda não está pronto."

        base = (tokens.get("webhook_base_url") or "").strip().rstrip("/")
        urls = await produtos.urls_fotos(pid, base)
        if not urls:
            ids = await produtos.fotos_ids(pid)
            if ids and not base:
                return "Não consegui enviar as fotos antigas: falta configurar a base URL pública do app no painel."
            return "Esse produto não tem fotos cadastradas."

        if not await _reservar_envio(number, pid, reenviar):
            return (
                "[FOTOS_JA_ENVIADAS] As fotos deste veículo já foram enviadas nesta conversa. "
                "Não chame esta ferramenta novamente; informe ao cliente que elas já foram enviadas."
            )

        enviadas = 0
        for url in urls:
            try:
                resp = await clientes.http_client.post(
                    f"{tokens['uazapi_url']}/send/media",
                    headers={"token": tokens["uazapi_token"], "Accept": "application/json"},
                    json={"number": number, "type": "image", "file": url},
                )
                if resp.status_code < 300:
                    enviadas += 1
            except Exception as exc:
                logger.warning("Falha ao enviar foto do produto %s: %s", pid, exc)

        if enviadas == 0:
            await _liberar_envio(number, pid)
            return "Tentei enviar mas não consegui (verifique a UAZAPI / o endereço público)."
        return (
            f"[FOTOS_ENVIADAS] Enviei {enviadas} foto(s) deste veículo ao cliente. "
            "Não envie as mesmas fotos novamente nem pergunte qual veículo ele queria depois disso."
        )

    return enviar_fotos_produto
