# AGENTS.md — Guia do agente base (template genérico)

Este repo é um **template de agente de IA por WhatsApp**: toda a infra (webhook, buffer,
memória, mídia, painel, fila, LLM com fallback) já está resolvida e é agnóstica de
domínio. Para criar um agente novo você só escreve o prompt e liga/cria as tools — veja
[Usar como template](#usar-como-template-criar-um-agente-novo).

## Arquitetura

FastAPI único serve o agente (`/webhook`) e o painel (`/admin`). Estado e config no
Redis; memória das conversas no Postgres; agenda no Google Calendar.

| Módulo | Responsabilidade |
|--------|------------------|
| `app/config.py` | Config ao vivo (Redis) + DEFAULTS + validação |
| `app/clientes.py` | Clientes globais (Supabase, OpenAI, Gemini, Calendar) + lifespan |
| `app/buffer.py` | Debounce deslizante (agrupa mensagens rápidas) |
| `app/bloqueios.py` | Grupos, atendente humano, rate limit |
| `app/memoria.py` | Histórico Postgres |
| `app/midia.py` | Áudio/imagem/documento |
| `app/tools/` | Uma tool por arquivo + registry |
| `app/agente.py` | Monta o agente LangChain |
| `app/webhook.py` | Orquestração + envio de mensagens |
| `app/painel/` | Login, configurações, sessões |

## Config ao vivo

Tudo que o painel ajusta vive numa chave Redis (`config:agente`). O agente chama
`get_config()` a cada mensagem, então mudanças valem na hora, sem restart. Padrões e
faixas de validação estão em `app/config.py`. A config salva no Redis **tem precedência**
sobre os defaults — então editar os defaults só afeta deploys novos (Redis vazio).

## Usar como template (criar um agente novo)

O default já vem **genérico e sem tools** (só `cadastrar` ligada — captura de nome,
útil em qualquer agente). Para um agente novo:

1. **Prompt**: edite o System Prompt em `/admin/config` (ou ajuste `SYSTEM_PROMPT_DEFAULT`
   em `app/config.py` para um deploy novo). Variáveis disponíveis: `{status_contato}`,
   `{nome_contato}`, `{data_hora}`, `{numero}`.
2. **Tools**: ligue as que precisar no painel, ou crie novas (abaixo). As tools de exemplo
   (`buscar_info`, `consultar_agenda`, `pre_marcacao`, `desmarcar`) vêm **desativadas** —
   os arquivos ficam no repo como modelo, é só ligar.
3. **Tabelas**: cada tool declara as suas (veja abaixo) e o boot cria sozinho.

Mais rápido ainda: comece de uma **base pronta** (preset) — veja abaixo.

## Bases por nicho (presets)

Um preset é a identidade de um agente (prompt + tools + marca) empacotada como **dado**,
não código. O motor é o mesmo para todos os nichos — conserto entra uma vez no `main` e
todos herdam no próximo build. Sem branch por nicho, sem divergência.

- **Catálogo**: `app/presets/`, um arquivo por nicho (ex.: `advogado.py`). Cada um expõe um
  dict `PRESET` com `nome_agente`, `nome_marca`, `system_prompt`, `tools_descricao`,
  `tools_ativas`. O prompt pode usar `{nome_agente}` e `{nome_marca}` para a mesma base
  servir vários clientes do nicho.
- **Aplicar pelo painel**: `/admin/config` → card *Base do agente (preset)* → escolher e
  *Aplicar base*. Sobrescreve prompt, tools e marca na config (Redis).
- **Aplicar no deploy (zero-toque)**: suba com a env `AGENTE_PRESET=advogado`. No 1º boot,
  se o Redis ainda não tem config, o preset é semeado automaticamente (`semear_preset_se_vazio`).
- **Criar uma base nova**: copie `app/presets/advogado.py`, renomeie (`fisioterapia.py`,
  `odontologia.py`…) e edite o `PRESET`. Aparece sozinho no dropdown e na env.

A **versão do motor** (código) é rastreada à parte por tag de imagem (SHA/semver). Assim
um cliente fica, por exemplo, *fisioterapia rodando motor v1.2*.

## Painel Geral

Tela `/admin/geral` (item no menu) é a central de controle da instância:

- **Base ativa**: rádio com todos os presets — só **uma** ativa por vez. Ativar uma chama
  `set_config(preset)` e grava `preset_ativo`; as outras ficam desmarcadas. A base ativa
  fica destacada com o selo *ativa*. `preset_ativo` vazio = config personalizada (nenhum
  preset aplicado, ex.: um agente ajustado só pelo painel).
- **Reset de conversas**: apaga TODO o histórico de mensagens (`message_store`) via
  `memoria.resetar_todo_historico()` — cada conversa recomeça do zero. **Mantém** os
  contatos (`cadastro`). Ação destrutiva, com confirmação no navegador.

## Como criar uma TOOL nova

1. Crie `app/tools/minha_tool.py`:
   ```python
   from langchain.tools import tool

   # Opcional: se a tool precisar de tabela, declare o DDL idempotente aqui.
   # O boot (garantir_schema) cria tudo sozinho no primeiro deploy.
   SCHEMA_SQL = (
       "CREATE TABLE IF NOT EXISTS minha_tabela ("
       "id TEXT PRIMARY KEY, valor TEXT)"
   )  # pode ser uma str única ou uma lista de strings

   def criar(descricao: str):
       @tool("minha_tool", description=descricao)
       async def minha_tool(param: str) -> str:
           return "resultado"
       return minha_tool
   ```
2. Em `app/config.py`, adicione a chave em `TOOLS_DESCRICAO_DEFAULT` e o estado inicial
   em `TOOLS_ATIVAS_DEFAULT` (`True` p/ já vir ligada, `False` p/ ficar de exemplo):
   ```python
   TOOLS_DESCRICAO_DEFAULT["minha_tool"] = "Descrição que o LLM vai ler."
   TOOLS_ATIVAS_DEFAULT["minha_tool"] = True
   ```
3. Em `app/tools/__init__.py`, importe o módulo em `montar_tools` e registre em
   `_sem_numero` (ou trate o closure se precisar do número, como `cadastrar`), e adicione-o
   também em `_modulos()` para o `SCHEMA_SQL` ser coletado no boot.
4. Pronto: a descrição aparece editável no painel, o agente enxerga a tool, e a tabela
   (se houver) é criada no próximo boot.

## Schema no boot

`garantir_schema()` (em `app/clientes.py`, chamado no lifespan) sempre cria a tabela base
`cadastro` e depois roda o DDL de cada tool (`coletar_schemas()` em `app/tools/__init__.py`,
que lê o atributo `SCHEMA_SQL` de cada módulo). Cada statement roda isolado: um DDL
inválido de uma tool não derruba o resto nem o boot.

## Como adicionar um CONFIG novo

1. Em `app/config.py`: adicione a chave em `DEFAULTS` e, se numérico, a faixa em `_FAIXAS`.
2. Use onde precisar via `(await get_config())["minha_chave"]`.
3. Em `app/painel/templates/config.html`: adicione o campo no formulário.
4. Se for `int`, inclua o nome em `_CAMPOS_INT` dentro de `app/painel/rotas.py`.

## Rodar testes

```
.venv\Scripts\python.exe -m pytest
```

## Deploy

```
docker compose up -d --build
```

Veja `README.md` para instruções completas de deploy na VPS.
