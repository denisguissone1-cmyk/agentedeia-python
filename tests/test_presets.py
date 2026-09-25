import re

import pytest

from app import config as cfg
from app import presets

# Placeholders conhecidos usados pelos prompts (ver payload em app/agente.py).
_PLACEHOLDERS_CONHECIDOS = {
    "nome_agente", "nome_marca", "status_contato", "nome_contato",
    "status_paciente", "nome_paciente", "data_hora", "numero",
}


def test_listar_inclui_farmacia():
    assert "farmacia" in presets.listar()
    assert "concessionaria" in presets.listar()


def test_todos_presets_tem_campos_completos():
    chaves_esperadas = set(cfg.TOOLS_ATIVAS_DEFAULT.keys())
    for nome in presets.listar():
        c = presets.carregar(nome)
        for campo in ("nome_agente", "nome_marca", "system_prompt", "tools_descricao", "tools_ativas"):
            assert campo in c, f"preset {nome!r} não define {campo!r}"
        # Regressão anti-vazamento: cada preset declara TODAS as 7 chaves de
        # tools_ativas (senão o merge de set_config mantém o estado do preset anterior).
        assert set(c["tools_ativas"].keys()) == chaves_esperadas, (
            f"preset {nome!r} não declara todas as chaves de tools_ativas: "
            f"{chaves_esperadas - set(c['tools_ativas'].keys())} faltando"
        )


def test_prompts_so_usam_placeholders_conhecidos():
    for nome in presets.listar():
        c = presets.carregar(nome)
        prompt_completo = c["system_prompt"] + cfg.SUFIXO_DETECCAO_BOT
        # Chaves balanceadas (senão o ChatPromptTemplate do LangChain quebra em runtime).
        assert prompt_completo.count("{") == prompt_completo.count("}"), (
            f"preset {nome!r}: chaves desbalanceadas no prompt"
        )
        usados = set(re.findall(r"\{([a-zA-Z_]+)\}", prompt_completo))
        desconhecidos = usados - _PLACEHOLDERS_CONHECIDOS
        assert not desconhecidos, f"preset {nome!r} usa placeholders desconhecidos: {desconhecidos}"


def test_sufixo_deteccao_sem_chaves():
    assert "{" not in cfg.SUFIXO_DETECCAO_BOT
    assert "}" not in cfg.SUFIXO_DETECCAO_BOT
    assert "PAUSAR_BOT" in cfg.SUFIXO_DETECCAO_BOT


def test_produtos_exemplo_todos_os_presets():
    for nome in presets.listar():
        itens = presets.produtos_exemplo(nome)
        assert len(itens) >= 8, f"preset {nome!r} tem catálogo de exemplo pequeno demais"
        for item in itens:
            assert item["nome"], f"preset {nome!r} tem item de catálogo sem nome"
            assert item["preco"], f"preset {nome!r}: item {item['nome']!r} sem preço"


def test_produtos_exemplo_preset_desconhecido():
    with pytest.raises(ValueError):
        presets.produtos_exemplo("inexistente")


def test_concessionaria_preserva_referencias_de_fotos_gcs():
    itens = presets.produtos_exemplo("concessionaria")
    com_fotos = [item for item in itens if item.get("fotos")]
    assert len(com_fotos) == 8
    assert all(
        foto["gcs_objeto"].startswith("catalogo/concessionaria/")
        for item in com_fotos for foto in item["fotos"]
    )


def test_identidades_formato():
    ids = presets.identidades()
    assert len(ids) == len(presets.listar())
    for info in ids:
        assert set(info.keys()) == {"id", "nome_agente", "nome_marca"}
        assert info["id"] in presets.listar()
        assert info["nome_agente"]
        assert info["nome_marca"]


def test_concessionaria_traz_veiculos_e_fotos_remotas():
    assert "concessionaria" in presets.listar()
    itens = presets.produtos_exemplo("concessionaria")
    assert len(itens) == 8
    assert all("fotos" in item for item in itens)
    fotos = [foto for item in itens for foto in item["fotos"]]
    assert len(fotos) == 93
    assert all(isinstance(foto, dict) and foto["gcs_objeto"] for foto in fotos)
    nomes = {item["nome"] for item in itens}
    assert not any("HR-V" in nome or "Pulse" in nome or "Kwid Zen" in nome for nome in nomes)
    for item in itens:
        descricao = item["descricao"]
        for campo in ("FIPE", "Quilometragem", "motor", "Financiamento"):
            assert campo in descricao, f"{item['nome']}: descrição sem {campo}"
