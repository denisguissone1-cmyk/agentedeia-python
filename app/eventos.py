"""Eventos de atividade da Sofia, em português leigo-friendly.

Cada evento é (1) guardado numa lista curta no Redis (eventos:recentes) para
a tela carregar o histórico e (2) publicado num canal pub/sub (eventos:stream)
que o endpoint SSE do painel transmite ao vivo.

Roda no processo do worker (onde o webhook é processado). Nunca levanta exceção:
log é acessório, não pode derrubar o atendimento.
"""
import json
from datetime import datetime

import pytz

from app.config import redis_client

_TZ = pytz.timezone("America/Sao_Paulo")
LISTA = "eventos:recentes"
CANAL = "eventos:stream"
_MAX = 50


async def emit(texto: str, *, cor: str = "e-blue", filtro: str = "msg", icone: str = "💬") -> None:
    """Grava o evento na lista recente e publica no canal ao vivo."""
    ev = {
        "texto": texto, "cor": cor, "filtro": filtro, "icone": icone,
        "quando": datetime.now(_TZ).strftime("%H:%M"),
    }
    payload = json.dumps(ev, ensure_ascii=False)
    try:
        await redis_client.lpush(LISTA, payload)
        await redis_client.ltrim(LISTA, 0, _MAX - 1)
        await redis_client.publish(CANAL, payload)
    except Exception:
        pass


async def _bump(chave: str) -> None:
    """Incrementa um contador diário (expira em 24h)."""
    try:
        if await redis_client.incr(chave) == 1:
            await redis_client.expire(chave, 86400)
    except Exception:
        pass


async def _hist(metric: str) -> None:
    """Conta diária por métrica (stats:hist:<metric>:YYYY-MM-DD) para o gráfico do dashboard.
    Retida ~120 dias. Nunca levanta exceção."""
    try:
        chave = f"stats:hist:{metric}:{datetime.now(_TZ).strftime('%Y-%m-%d')}"
        if await redis_client.incr(chave) == 1:
            await redis_client.expire(chave, 120 * 86400)
    except Exception:
        pass


def _quem(nome: str, numero: str) -> str:
    n = (nome or "").strip()
    if n:
        return n
    base = (numero or "").split("@")[0]
    return f"{base[:4]}•••{base[-2:]}" if len(base) > 6 else (base or "alguém")


# ── Helpers de alto nível (chamados no webhook / tools) ─────────────────────────

async def recebida(nome: str, numero: str, tipo: str) -> None:
    rotulos = {
        "AudioMessage":    ("mandou um áudio — transcrevi para texto", "🎤"),
        "ImageMessage":    ("enviou uma imagem", "📎"),
        "DocumentMessage": ("enviou um documento", "📎"),
    }
    acao, icone = rotulos.get(tipo, ("enviou uma mensagem", "💬"))
    await emit(f"{_quem(nome, numero)} {acao}", cor="e-blue", filtro="msg", icone=icone)
    await _bump("stats:msgs_hoje")
    await _hist("mensagens")


async def respondida(nome: str, numero: str) -> None:
    await emit(f"Sofia respondeu {_quem(nome, numero)}", cor="e-grn", filtro="msg", icone="✅")


async def aviso_rate(nome: str, numero: str) -> None:
    await emit(
        f"{_quem(nome, numero)} mandou muitas mensagens de uma vez — avisei que respondo em instantes",
        cor="e-amb", filtro="aviso", icone="⏳",
    )


async def humano_assumiu(nome: str, numero: str) -> None:
    await emit(
        f"Um atendente humano assumiu a conversa de {_quem(nome, numero)} — Sofia pausada",
        cor="e-amb", filtro="aviso", icone="🙋",
    )


async def agendamento(numero: str, urgente: bool = False) -> None:
    if urgente:
        await emit(
            f"Caso URGENTE de {_quem('', numero)} — consulta priorizada e equipe avisada",
            cor="e-red", filtro="agenda", icone="🚨",
        )
    else:
        await emit(f"Consulta agendada para {_quem('', numero)}", cor="e-vio", filtro="agenda", icone="📅")
    await _bump("stats:agendamentos_hoje")
    await _hist("agendamentos")
