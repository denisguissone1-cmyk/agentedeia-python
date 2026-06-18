"""Áudios recebidos no WhatsApp: bytes guardados no Postgres (tabela audio_msg).

O webhook salva o áudio original ao transcrever; o painel toca via /media/audio/<id>
e mostra um botão "ver transcrição". A tabela é criada no boot por garantir_schema
(app/clientes.py).
"""
import asyncio

import psycopg2

from app.clientes import get_db_conn


async def salvar(number: str, mime: str, dados: bytes) -> int:
    def _q():
        conn = get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    'INSERT INTO audio_msg ("remoteJid", mime, dados) '
                    "VALUES (%s, %s, %s) RETURNING id",
                    (number, mime or "audio/ogg", psycopg2.Binary(dados)),
                )
                aid = cur.fetchone()["id"]
            conn.commit()
            return aid
        finally:
            conn.close()
    return await asyncio.to_thread(_q)


async def obter(aid: int) -> tuple[str, bytes] | None:
    """(mime, bytes) de um áudio, para servir em /media/audio/<id>."""
    def _q():
        conn = get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT mime, dados FROM audio_msg WHERE id=%s", (aid,))
                row = cur.fetchone()
                if not row:
                    return None
                return row["mime"], bytes(row["dados"])
        finally:
            conn.close()
    return await asyncio.to_thread(_q)
