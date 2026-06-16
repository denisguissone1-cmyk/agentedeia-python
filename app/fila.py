"""Fila durável no Redis (arq). O webhook enfileira; os workers consomem."""
import os
from arq.connections import RedisSettings

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

def redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(REDIS_URL)

NOME_JOB = "processar_mensagem"
