"""Base: concessionária de seminovos com estoque, fotos no GCS e test-drive."""


def _fotos(slug: str, quantidade: int) -> list[dict]:
    return [
        {
            "gcs_objeto": f"catalogo/concessionaria/{slug}/{ordem:02d}.webp",
            "mime": "image/webp",
        }
        for ordem in range(1, quantidade + 1)
    ]


PRESET = {
    "nome_agente": "Marina",
    "nome_marca": "Auto Prime Veículos",
    "system_prompt": """# PAPEL

Você é {nome_agente}, consultor(a) de vendas da {nome_marca}, uma concessionária de veículos seminovos. Atenda de forma consultiva, objetiva e acolhedora, sem pressionar o cliente.

# CONTEXTO

Status do contato: {status_contato}
Nome conhecido: {nome_contato}
Data/Hora: {data_hora}
Número do contato: {numero}

# FLUXO DE VENDA

1. Cumprimente em nome da {nome_marca}, descubra o nome do cliente e salve-o com cadastrar.
2. Entenda modelo/categoria, faixa de preço, câmbio desejado, forma de pagamento e se há veículo na troca.
3. Use listar_produtos antes de informar estoque, preço, FIPE, ano, quilometragem ou opcionais. O catálogo é a única fonte de verdade.
4. Apresente no máximo três opções compatíveis por vez. Diferencie preço anunciado, referência FIPE e condições de financiamento.
5. Quando pedirem imagens de um veículo identificado, use enviar_fotos_produto com o #id correto. Se pedirem apenas "fotos", pergunte primeiro de qual veículo. As fotos são da unidade anunciada.
6. Financiamento é sujeito à análise de crédito. Nunca prometa aprovação, parcela, taxa ou entrada sem simulação do consultor.
7. Para visita ou test-drive, obtenha nome, veículo, dia e período. Use consultar_agenda antes de oferecer horário. Após confirmação explícita, use pre_marcacao com duração padrão de 60 minutos, resumo “Test-drive — [veículo] — [cliente]” e descrição com telefone, veículo, troca e interesse em financiamento.
8. Para cancelar, confirme a intenção, consulte a agenda para obter o event_id e então use desmarcar.

# REGRAS

- Mensagens curtas e naturais, sem markdown. Envie cada ideia em uma bolha separada, com uma linha em branco entre bolhas.
- Faça somente uma pergunta por bolha e aguarde a resposta antes de avançar para a próxima pergunta.
- Nunca invente disponibilidade, quilometragem, cor, opcionais, documentação, garantia ou condição comercial.
- “A confirmar” significa que um consultor precisa validar na unidade; não transforme isso em “sim”.
- Valores FIPE e médias OLX são referências de julho/2026 e podem mudar. O preço vigente é o preço do catálogo.
- Não prometa avaliação do usado nem aprovação de crédito.
- Só envie fotos de veículos ativos e só agende após o cliente confirmar o horário.
- Redirecione fugas de assunto com naturalidade para compra, venda, troca, financiamento ou test-drive.""",
    "tools_descricao": {
        "cadastrar": (
            "Salva o nome do cliente. Use somente uma vez, quando ele informar o próprio "
            "nome (1 a 3 palavras); não use para saudações."
        ),
        "listar_produtos": (
            "Consulta o estoque ativo com #id, preço, FIPE, motor, câmbio, quilometragem, "
            "conforto, segurança e condição de financiamento. É a fonte de verdade."
        ),
        "enviar_fotos_produto": (
            "Envia as fotos reais cadastradas da unidade. Recebe produto_id, o #id retornado "
            "por listar_produtos. Use somente quando o cliente identificar o veículo e pedir imagens. "
            "Não use reenviar=true, salvo pedido explícito para receber as fotos novamente."
        ),
        "buscar_info": "Busca informações institucionais cadastradas sobre a concessionária.",
        "consultar_agenda": (
            "Consulta compromissos entre after e before em ISO 8601. Use antes de oferecer "
            "horário de visita ou test-drive e antes de cancelar."
        ),
        "pre_marcacao": (
            "Cria visita/test-drive após confirmação explícita. Recebe start, end, summary e "
            "description. Use duração de 60 minutos e inclua cliente, telefone e veículo."
        ),
        "desmarcar": (
            "Cancela visita/test-drive pelo event_id, somente após localizar o evento com "
            "consultar_agenda e receber confirmação explícita do cliente."
        ),
    },
    "tools_ativas": {
        "cadastrar": True,
        "listar_produtos": True,
        "enviar_fotos_produto": True,
        "buscar_info": False,
        "consultar_agenda": True,
        "pre_marcacao": True,
        "desmarcar": True,
    },
    "produtos": [
        {
            "nome": "Chevrolet Onix Plus LTZ 1.0 Turbo Manual 2023",
            "preco": "74.900",
            "descricao": "Preço de referência OLX jul/2026: R$ 74.900. FIPE jul/2026: R$ 74.455 (cód. 004503-9). Quilometragem: a confirmar. Sedã flex; motor 1.0 turbo 12V, 116 cv e 16,8 kgfm; câmbio manual de 6 marchas; direção elétrica; ar-condicionado; vidros, travas e retrovisores elétricos; multimídia/Bluetooth; volante multifuncional; sensor traseiro; ABS, 6 airbags, controles de estabilidade/tração e ISOFIX. Financiamento: sim, sujeito à análise. Troca: sob avaliação.",
            "fotos": _fotos("chevrolet-onix-plus-ltz-2023", 5),
        },
        {
            "nome": "Hyundai HB20 Platinum Plus 1.0 TGDI Automático 2023",
            "preco": "89.900",
            "descricao": "Preço médio anunciado OLX jul/2026: cerca de R$ 89.900. FIPE jul/2026: R$ 87.266 (cód. 015208-0). Quilometragem: a confirmar. Hatch flex; motor 1.0 turbo 12V, 120 cv e 17,5 kgfm; câmbio automático; direção elétrica; ar-condicionado; vidros, travas e retrovisores elétricos; multimídia/Bluetooth; volante multifuncional; sensor traseiro; ABS, 6 airbags e ISOFIX. Câmera e demais opcionais: confirmar na unidade. Financiamento: sim, sujeito à análise. Troca: sob avaliação.",
            "fotos": _fotos("hyundai-hb20-platinum-plus-2023", 5),
        },
        {
            "nome": "Volkswagen T-Cross Comfortline 200 TSI Automático 2022",
            "preco": "103.900",
            "descricao": "Preço médio anunciado OLX jul/2026: cerca de R$ 103.900. FIPE jul/2026: R$ 102.637 (cód. 005509-3). Quilometragem: a confirmar. SUV flex; motor 1.0 TSI 12V, até 128 cv e 20,4 kgfm; automático de 6 marchas; direção elétrica; ar-condicionado; vidros, travas e retrovisores elétricos; multimídia/Bluetooth; volante multifuncional; sensores dianteiro e traseiro; ABS, 6 airbags e ISOFIX. Teto/câmera: confirmar na unidade. Financiamento: sim, sujeito à análise. Troca: sob avaliação.",
            "fotos": _fotos("volkswagen-t-cross-comfortline-2022", 20),
        },
        {
            "nome": "Toyota Corolla XEi 2.0 Flex Automático 2022",
            "preco": "125.900",
            "descricao": "Preço médio anunciado OLX jul/2026: cerca de R$ 125.900. FIPE jul/2026: R$ 122.084 (cód. 002111-3). Quilometragem: a confirmar. Sedã flex; motor 2.0 16V, até 177 cv e 21,4 kgfm; câmbio CVT; direção elétrica; ar-condicionado; vidros, travas e retrovisores elétricos; multimídia/Bluetooth; volante multifuncional; ABS, airbags frontais/laterais/cortina e ISOFIX; porta-malas de 470 l. Bancos, câmera e sensores: confirmar na unidade. Financiamento: sim, sujeito à análise. Troca: sob avaliação.",
            "fotos": _fotos("toyota-corolla-xei-2022", 10),
        },
        {
            "nome": "Jeep Compass T270 80 Anos 1.3 Turbo Automático 2022",
            "preco": "115.900",
            "descricao": "Preço médio anunciado OLX jul/2026: cerca de R$ 115.900. FIPE jul/2026: R$ 117.952 (cód. 017073-9). Quilometragem: a confirmar. SUV flex; motor 1.3 turbo, até 185 cv e 27,5 kgfm; automático de 6 marchas; tração dianteira; direção elétrica; ar-condicionado; vidros, travas e retrovisores elétricos; multimídia/Bluetooth; volante multifuncional; sensor traseiro; ABS, airbags frontais/laterais/cortina e ISOFIX. Itens exclusivos 80 Anos e câmera: confirmar na unidade. Financiamento: sim, sujeito à análise. Troca: sob avaliação.",
            "fotos": _fotos("jeep-compass-80-anos-2022", 19),
        },
        {
            "nome": "Chevrolet Celta Spirit/LT 1.0 MPFI Flex Manual 2010",
            "preco": "26.900",
            "descricao": "Preço anunciado de referência OLX jul/2026: cerca de R$ 26.900. FIPE jul/2026: R$ 25.328 (cód. 004321-4). Quilometragem: a confirmar. Hatch flex 5 portas; motor 1.0 MPFI 8V, até 78 cv e 9,7 kgfm; manual de 5 marchas; direção mecânica na ficha-base; porta-malas de 260 l. Ar-condicionado, vidros/travas elétricos, direção assistida, airbags e ABS: confirmar especificamente nesta unidade. Financiamento: sim, sujeito à análise e às regras de idade do veículo. Troca: sob avaliação.",
            "fotos": _fotos("chevrolet-celta-spirit-lt-2010", 16),
        },
        {
            "nome": "Kia Cerato 1.6 16V Manual 2011",
            "preco": "41.900",
            "descricao": "Preço médio anunciado OLX jul/2026: cerca de R$ 41.900. FIPE jul/2026: R$ 41.403 (cód. 018054-8). Quilometragem: a confirmar. Sedã a gasolina; motor 1.6 16V, 126 cv e 15,9 kgfm; manual de 6 marchas; direção hidráulica; ar-condicionado; vidros, travas e retrovisores elétricos; computador de bordo e volante multifuncional; airbags frontais; porta-malas de 415 l. ABS, Bluetooth e sensores: confirmar na unidade. Financiamento: sim, sujeito à análise e às regras de idade do veículo. Troca: sob avaliação.",
            "fotos": _fotos("kia-cerato-1-6-manual-2011", 5),
        },
        {
            "nome": "Renault Kwid Intense 1.0 Flex Manual 2020",
            "preco": "41.900",
            "descricao": "Preço médio anunciado OLX jul/2026: cerca de R$ 41.900. FIPE jul/2026: R$ 40.048 (cód. 025267-0). Quilometragem: a confirmar. Hatch flex; motor 1.0 12V, até 70 cv e 9,8 kgfm; manual de 5 marchas; direção elétrica; ar-condicionado; vidros dianteiros, travas e retrovisores elétricos; multimídia/Bluetooth; ABS, airbags frontais/laterais e ISOFIX; porta-malas de 290 l. Vidros traseiros, câmera e sensores: confirmar na unidade. Financiamento: sim, sujeito à análise. Troca: sob avaliação.",
            "fotos": _fotos("renault-kwid-intense-2020", 13),
        },
    ],
}
