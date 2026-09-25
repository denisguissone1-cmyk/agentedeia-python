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
        "produtos": [...],           # opcional: catálogo de exemplo — lista de
                                     # {"nome": "...", "preco": "...", "descricao": "..."},
                                     # semeada na tabela produto ao ativar a base (ver
                                     # produtos_exemplo() e app.produtos.substituir_catalogo)
    }

Aplicar um preset grava os campos de _CAMPOS no Redis (via set_config) — então o mesmo
motor (código) vira aquele nicho. Para criar uma base nova, copie um arquivo existente e
edite.
"""
import importlib
import pkgutil

# Campos de um preset que viram config. Qualquer outra chave do PRESET (ex.: "produtos")
# é ignorada por carregar() — leia-a separadamente com produtos_exemplo().
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


def produtos_exemplo(nome: str) -> list[dict]:
    """Catálogo mockup do preset (chave extra "produtos" do PRESET). [] se não houver.
    Levanta ValueError se o preset não existir."""
    if nome not in listar():
        raise ValueError(f"preset desconhecido: {nome!r}")
    mod = importlib.import_module(f"app.presets.{nome}")
    itens = getattr(mod, "PRESET", {}).get("produtos", []) or []
    def _normalizar_foto(foto):
        if isinstance(foto, dict):
            return {
                "gcs_objeto": str(foto.get("gcs_objeto", "")).strip(),
                "mime": str(foto.get("mime", "image/jpeg")).strip() or "image/jpeg",
                "url": str(foto.get("url", "")).strip(),
            }
        return str(foto).strip()

    return [
        {"nome": str(i.get("nome", "")).strip(),
         "preco": str(i.get("preco", "")).strip(),
         "descricao": str(i.get("descricao", "")).strip(),
         "fotos": [_normalizar_foto(foto) for foto in (i.get("fotos", []) or [])
                   if isinstance(foto, dict) or str(foto).strip()]}
        for i in itens if str(i.get("nome", "")).strip()
    ]


def identidades() -> list[dict]:
    """[{id, nome_agente, nome_marca}] de todos os presets — usado pelo painel para
    pré-preencher o modal de ativação de base sem precisar carregar cada preset à parte."""
    out = []
    for nome in listar():
        mod = importlib.import_module(f"app.presets.{nome}")
        p = getattr(mod, "PRESET", {})
        out.append({
            "id": nome,
            "nome_agente": p.get("nome_agente", ""),
            "nome_marca": p.get("nome_marca", ""),
        })
    return out
