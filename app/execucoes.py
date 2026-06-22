"""Trace de execução por mensagem (estilo n8n): mostra cada passo do pipeline
e exatamente onde parou / falhou.

Cada mensagem processada vira uma "execução" com uma lista de passos. O registro
é gravado no Redis (lista curta) ao final, e o painel lê na tela Execuções.
Nunca levanta exceção — observabilidade não pode derrubar o atendimento.
"""
import json
from datetime import datetime

import pytz

from app.config import redis_client

_TZ = pytz.timezone("America/Sao_Paulo")
LISTA = "execucoes:recentes"
_MAX = 50


def _mask(numero: str) -> str:
    base = (numero or "").split("@")[0]
    return f"{base[:4]}•••{base[-2:]}" if len(base) > 6 else (base or "?")


def _hora() -> str:
    return datetime.now(_TZ).strftime("%H:%M:%S")


class Execucao:
    """Acumula os passos em memória; grava tudo de uma vez em salvar()."""

    def __init__(self, req_id: str, numero: str):
        self.req_id = req_id
        self.numero = _mask(numero)
        self.inicio = _hora()
        self.status = "andamento"   # andamento | sucesso | falha | ignorada | aguardando
        self.passos: list[dict] = []

    def passo(self, nome: str, detalhe: str = "") -> None:
        self.passos.append({"nome": nome, "status": "ok", "detalhe": detalhe, "hora": _hora()})

    def erro(self, nome: str, detalhe: str = "") -> None:
        self.passos.append({"nome": nome, "status": "erro", "detalhe": detalhe, "hora": _hora()})
        self.status = "falha"

    def encerrar(self, status: str) -> None:
        if self.status == "andamento":
            self.status = status

    async def salvar(self) -> None:
        if self.status == "andamento":
            self.status = "sucesso"
        ult = self.passos[-1] if self.passos else {"nome": "—", "detalhe": ""}
        resumo = ult["nome"] + (f" · {ult['detalhe']}" if ult.get("detalhe") else "")
        rec = {
            "req_id": self.req_id, "numero": self.numero, "hora": self.inicio,
            "status": self.status, "resumo": resumo, "passos": self.passos,
        }
        try:
            await redis_client.lpush(LISTA, json.dumps(rec, ensure_ascii=False))
            await redis_client.ltrim(LISTA, 0, _MAX - 1)
        except Exception:
            pass


async def listar(n: int = 30) -> list[dict]:
    try:
        raw = await redis_client.lrange(LISTA, 0, n - 1)
    except Exception:
        return []
    out = []
    for item in raw or []:
        try:
            out.append(json.loads(item))
        except Exception:
            continue
    return out
