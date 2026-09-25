"""Notificações do painel (sininho na topbar).

Cada notificação é (1) guardada numa lista curta no Redis (notificacoes:recentes)
para o SPA carregar o histórico e o contador de não-lidas, e (2) espelhada no feed
de eventos existente (app/eventos.py, filtro="notificacao") para fluir também pelo
SSE ao vivo (/api/logs/stream) sem precisar de um segundo canal pub/sub.

Roda no processo do worker (onde o webhook é processado). Nunca levanta exceção:
notificar é acessório, não pode derrubar o atendimento.
"""
import json
import time
import uuid
from datetime import datetime

import pytz

from app import eventos
from app.config import redis_client

_TZ = pytz.timezone("America/Sao_Paulo")
LISTA = "notificacoes:recentes"
LIDAS_EM = "notificacoes:lidas_em"
_MAX = 100

_COR = {"bot_detectado": "e-red", "humano_assumiu": "e-amb"}
_ICONE = {"bot_detectado": "🤖", "humano_assumiu": "🙋"}


async def notificar(
    titulo: str, texto: str, tipo: str = "info",
    numero: str | None = None, dedupe_ttl: int = 0,
) -> None:
    """Registra uma notificação. Nunca levanta exceção.

    dedupe_ttl (segundos): se >0 e houver `numero`, suprime notificações repetidas do
    mesmo tipo+número dentro da janela (ex.: takeover humano não notifica a cada
    mensagem `fromMe`, só uma vez a cada 15min).
    """
    try:
        if dedupe_ttl and numero:
            chave = f"notif:dedupe:{tipo}:{numero}"
            se_novo = await redis_client.set(chave, "1", ex=dedupe_ttl, nx=True)
            if not se_novo:
                return
        n = {
            "id": uuid.uuid4().hex[:12],
            "titulo": titulo,
            "texto": texto,
            "tipo": tipo,
            "numero": numero,
            "ts": time.time(),
            "quando": datetime.now(_TZ).strftime("%H:%M"),
        }
        await redis_client.lpush(LISTA, json.dumps(n, ensure_ascii=False))
        await redis_client.ltrim(LISTA, 0, _MAX - 1)
        await eventos.emit(
            f"{titulo} — {texto}",
            cor=_COR.get(tipo, "e-blue"), filtro="notificacao", icone=_ICONE.get(tipo, "🔔"),
        )
    except Exception:
        pass


async def listar(n: int = 50) -> list[dict]:
    """Lê notificacoes:recentes de forma tolerante. Vazio se ausente/erro."""
    try:
        raw = await redis_client.lrange(LISTA, 0, n - 1)
    except Exception:
        return []
    out = []
    for item in raw or []:
        try:
            d = json.loads(item)
            if isinstance(d, dict):
                out.append(d)
        except Exception:
            continue
    return out


async def nao_lidas() -> int:
    """Conta quantas notificações recentes são posteriores à última leitura marcada."""
    try:
        raw_lidas = await redis_client.get(LIDAS_EM)
        lidas_em = float(raw_lidas) if raw_lidas else 0.0
        itens = await listar(_MAX)
        return sum(1 for it in itens if float(it.get("ts", 0)) > lidas_em)
    except Exception:
        return 0


async def marcar_lidas() -> None:
    try:
        await redis_client.set(LIDAS_EM, str(time.time()))
    except Exception:
        pass
