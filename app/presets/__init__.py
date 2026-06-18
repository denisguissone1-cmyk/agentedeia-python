"""Catálogo de bases (presets) por nicho.

Cada arquivo `app/presets/<nicho>.py` expõe um dict `PRESET` com os campos de config que
definem a identidade do agente:

    PRESET = {
        "nome_agente": "...",
        "nome_marca": "...",
        "system_prompt": "...",      # pode usar {nome_agente}, {nome_marca},
                                     # {status_contato}, {nome_contato}, {data_hora}, {numero}
        "tools_descricao": {...},    # descrição de cada tool
        "tools_ativas": {...},       # quais tools ligadas
    }

Aplicar um preset grava esses campos no Redis (via set_config) — então o mesmo motor
(código) vira aquele nicho. Para criar uma base nova, copie um arquivo existente e edite.
"""
import importlib
import pkgutil

# Campos de um preset que viram config. Qualquer outra chave do PRESET é ignorada.
_CAMPOS = ("nome_agente", "nome_marca", "system_prompt", "tools_descricao", "tools_ativas")


def listar() -> list:
    """Nomes dos presets disponíveis (nome do arquivo .py, sem extensão)."""
    nomes = [m.name for m in pkgutil.iter_modules(__path__) if not m.name.startswith("_")]
    return sorted(nomes)


def carregar(nome: str) -> dict:
    """Retorna os campos de config do preset `nome`. Levanta ValueError se não existir."""
    if nome not in listar():
        raise ValueError(f"preset desconhecido: {nome!r}")
    mod = importlib.import_module(f"app.presets.{nome}")
    preset = getattr(mod, "PRESET", {})
    return {k: preset[k] for k in _CAMPOS if k in preset}
