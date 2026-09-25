from app.agente import extrair_pausa_bot


def test_marcador_exato():
    assert extrair_pausa_bot("[[PAUSAR_BOT: menu numérico de autoatendimento]]") == \
        "menu numérico de autoatendimento"


def test_marcador_no_meio_do_texto():
    texto = "Antes disso [[PAUSAR_BOT: resposta automática]] e depois disso"
    assert extrair_pausa_bot(texto) == "resposta automática"


def test_marcador_sem_dois_pontos():
    assert extrair_pausa_bot("[[PAUSAR_BOT menu numérico]]") == "menu numérico"


def test_motivo_multilinha_colapsa_espacos():
    texto = "[[PAUSAR_BOT: menu\n  numérico\n  de autoatendimento]]"
    assert extrair_pausa_bot(texto) == "menu numérico de autoatendimento"


def test_motivo_truncado_em_120_chars():
    motivo_longo = "a" * 200
    resultado = extrair_pausa_bot(f"[[PAUSAR_BOT: {motivo_longo}]]")
    assert len(resultado) == 120


def test_motivo_vazio_usa_default():
    assert extrair_pausa_bot("[[PAUSAR_BOT:]]") == "suspeita de outro assistente virtual"
    assert extrair_pausa_bot("[[PAUSAR_BOT: ]]") == "suspeita de outro assistente virtual"


def test_marcador_malformado_sem_fechar_usa_default():
    assert extrair_pausa_bot("bla [[PAUSAR_BOT: menu numérico sem fechamento") == \
        "suspeita de outro assistente virtual"


def test_texto_normal_retorna_none():
    assert extrair_pausa_bot("Olá! Como posso ajudar você hoje?") is None
    assert extrair_pausa_bot("") is None
    assert extrair_pausa_bot(None) is None


def test_case_insensitive():
    assert extrair_pausa_bot("[[pausar_bot: menu automático]]") == "menu automático"
    assert extrair_pausa_bot("texto contendo Pausar_Bot solto") == "suspeita de outro assistente virtual"
