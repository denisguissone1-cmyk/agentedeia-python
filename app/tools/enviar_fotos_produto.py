from langchain.tools import tool

from app import clientes, produtos
from app.config import get_tokens


def criar(number: str, descricao: str):
    @tool("enviar_fotos_produto", description=descricao)
    async def enviar_fotos_produto(produto_id: int) -> str:
        try:
            ids = await produtos.fotos_ids(int(produto_id))
        except (TypeError, ValueError):
            return "produto_id inválido — use o número (#id) do listar_produtos."
        if not ids:
            return "Esse produto não tem fotos cadastradas."

        tokens = await get_tokens()
        base = (tokens.get("webhook_base_url") or "").strip().rstrip("/")
        if not base:
            return "Não consegui enviar: falta configurar o endereço público do app (base URL) no painel."

        enviadas = 0
        for fid in ids:
            url = f"{base}/media/foto/{fid}"
            try:
                resp = await clientes.http_client.post(
                    f"{tokens['uazapi_url']}/send/media",
                    headers={"token": tokens["uazapi_token"], "Accept": "application/json"},
                    json={"number": number, "type": "image", "file": url},
                )
                if resp.status_code < 300:
                    enviadas += 1
            except Exception:
                pass

        if enviadas == 0:
            return "Tentei enviar mas não consegui (verifique a UAZAPI / o endereço público)."
        return f"{enviadas} foto(s) do produto enviada(s) ao cliente."

    return enviar_fotos_produto
