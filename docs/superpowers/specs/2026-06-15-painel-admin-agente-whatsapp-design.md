# Painel Admin + Modularização do Agente WhatsApp (Elizabeth)

**Data:** 2026-06-15
**Status:** Histórico — substituído (ver aviso abaixo)

> **⚠️ Documento histórico (substituído).** O painel Jinja em `/admin` descrito aqui foi
> entregue e, depois, **substituído por um SPA React** (`frontend/`) servido na raiz `/` e
> consumindo a API JSON em `/api/*`. Os templates Jinja e as rotas `/admin/*` **não existem
> mais**. Este texto fica apenas como registro do design original — não use as rotas/telas
> citadas como referência do sistema atual.

## Contexto

Hoje o agente é um único arquivo `agente_whatsapp (1).py` (~950 linhas) — um servidor
FastAPI que atende pacientes da clínica SB Fisio no WhatsApp via uazapi, usando
LangChain + Gemini, com memória em Postgres, estado em Redis e agenda no Google Calendar.

Todos os ajustes de comportamento são **constantes fixas no código** (ex:
`BUFFER_SEGUNDOS = 6`, bloqueio humano `ex=900`). Mudar qualquer coisa exige editar o
código e redeployar.

## Objetivo

1. **Painel web simples** (`/admin`) para configurar o agente sem mexer no código e
   visualizar cada conversa (sessão por número) separadamente.
2. **Modularizar** o `.py` monolítico em arquivos pequenos com responsabilidade única.
3. **Deploy via Docker/GitHub numa VPS**, acessível por link.
4. **Documentação** (`AGENTS.md`) ensinando como estender o projeto (novas tools, novos
   configs).

## Não-objetivos (YAGNI)

- Multiusuário/permissões granulares (só um login admin: usuário + senha).
- Configs por grupo de números (todos os números usam a mesma config global).
- Reescrever o RAG (`buscar_info` continua como está, é um TODO pré-existente).
- Métricas/analytics avançados.

## Descoberta importante: o buffer já é um debounce deslizante

O comportamento desejado — *"mandou uma mensagem, conta 6s; mandou outra, reseta pra 6s
de novo"* — **já está implementado** na função `buffer_mensagens` (Seção 11 do código
atual). Cada mensagem grava um token único em `{number}:atividade` e dorme
`BUFFER_SEGUNDOS`. Se uma mensagem nova chega durante a espera, ela sobrescreve o token;
quando a execução antiga acorda, vê que o token mudou e se descarta. Só a **última**
mensagem (a que ficar `BUFFER_SEGUNDOS` em silêncio) sobrevive e processa o lote inteiro.

**Conclusão:** não reescrevemos essa lógica. Só trocamos a constante fixa pelo valor lido
do config ao vivo.

## Arquitetura: Abordagem A — app único, modularizado

Um único serviço FastAPI roda o agente (`/webhook`) e o painel (`/admin`). Um container.
Config no Redis, lido a cada mensagem (vale na hora, sem restart).

### Estrutura de arquivos

```
app/
├── main.py            # cria o FastAPI, registra rotas, lifespan
├── config.py          # get_config()/set_config() no Redis + DEFAULTS embutidos
├── clientes.py        # clientes globais: Supabase, Redis, OpenAI, Gemini, Calendar
├── webhook.py         # rota /webhook + processar_em_background (orquestração)
├── buffer.py          # debounce deslizante (lê o tempo do config)
├── memoria.py         # histórico Postgres (carregar/salvar/inserir)
├── midia.py           # transcrição de áudio, análise de imagem/documento
├── bloqueios.py       # grupos, atendente humano, rate limit
├── agente.py          # monta o agente LangChain + injeta system prompt do config
├── tools/
│   ├── __init__.py    # registry: junta as tools e injeta descrições do config
│   ├── base.py        # helpers comuns (ex: get_calendar_service)
│   ├── cadastrar.py   # factory com closure do número
│   ├── buscar_info.py
│   ├── consultar_agenda.py
│   ├── pre_marcacao.py
│   └── desmarcar.py
└── painel/
    ├── rotas.py       # /admin: login, configurações, sessões
    ├── auth.py        # usuário+senha (hash), sessão por cookie
    └── templates/     # HTML Jinja2 (login, config, sessoes, conversa)
```

Cada módulo mantém **exatamente o comportamento atual** — só reorganizado. As funções
existentes migram para o arquivo correspondente sem mudança de lógica, exceto onde
indicado (config ao vivo, tools como factory).

## Camada de configuração ao vivo

### Armazenamento

- Chave Redis `config:agente` → JSON com todos os ajustes.
- `config.py` define `DEFAULTS` (os valores de hoje) e:
  - `async def get_config() -> dict` — lê a chave, faz merge com `DEFAULTS` (campos
    ausentes caem no padrão), retorna o dict. Lida com chave inexistente.
  - `async def set_config(parcial: dict) -> dict` — valida, faz merge com o atual, grava.
- **Validação:** números dentro de faixas sãs (ex: buffer 1–60s, bloqueio 1–120min,
  rate limit 1–500). Texto não-vazio para prompt. Erros voltam pro painel como mensagem.

### Campos configuráveis

| Campo                  | Tipo   | Padrão (hoje) | Onde é usado                         |
|------------------------|--------|---------------|--------------------------------------|
| `buffer_segundos`      | int    | 6             | `buffer.py` (tempo do debounce)      |
| `bloqueio_humano_min`  | int    | 15            | `bloqueios.py` (ex = min*60)         |
| `rate_limit_max`       | int    | 30            | `bloqueios.py`                       |
| `rate_limit_janela`    | int    | 60            | `bloqueios.py`                       |
| `historico_max`        | int    | 40            | `memoria.py`                         |
| `agent_timeout_seg`    | int    | 30            | `agente.py`                          |
| `system_prompt`        | texto  | (atual)       | `agente.py`                          |
| `tools_descricao`      | dict   | (docstrings)  | `tools/__init__.py` (uma por tool)   |

### Fluxo

```
Painel salva "8s" → set_config() → Redis (config:agente)
                                       ↓
Próxima mensagem do cliente → buffer.py chama get_config() → lê 8s
```

Sem cache em memória do lado do agente (ou cache curto de poucos segundos) para garantir
que a mudança vale "na hora". O custo de uma leitura Redis por mensagem é desprezível.

### Tools com descrição dinâmica (mudança real)

Hoje as tools usam `@tool` com docstring fixa, que o LLM lê para decidir quando usá-las.
Para editar essas descrições pelo painel, cada arquivo em `tools/` expõe uma **factory**
`def criar(descricao: str, ...) -> Tool` que monta a tool com a `description` vinda do
config. O `tools/__init__.py` chama as factories a cada construção do agente, passando
`tools_descricao[nome]`. A `cadastrar` continua factory por causa do closure do número.

## O painel (`/admin`)

HTML server-rendered (Jinja2) + JS puro. Sem framework de frontend. Mobile-friendly básico.

### Telas

1. **Login** (`GET/POST /admin/login`)
   - Usuário + senha. Credenciais no `.env` (`PAINEL_USER`, `PAINEL_PASS_HASH`).
   - Senha conferida com hash (`hmac.compare_digest` sobre hash, sem texto puro).
   - Sucesso → cookie de sessão assinado (HttpOnly). Sem cookie válido → redireciona.

2. **Configurações** (`GET/POST /admin/config`)
   - Formulário com: buffer (s), bloqueio humano (min), rate limit (max/janela),
     histórico máx, timeout do agente, **system prompt** (textarea grande), e **uma
     textarea por tool** para a descrição.
   - "Salvar" → `set_config()` → aviso "Salvo ✓". Erros de validação mostrados no form.

3. **Sessões** (`GET /admin/sessoes`)
   - Lista os números que já conversaram (do `cadastro` no Supabase), com nome, e status:
     ativo / bloqueado-humano / pausado (lido do Redis: `{number}_block`).
   - Clicar abre `GET /admin/sessoes/{number}`: histórico daquela conversa (do Postgres),
     com botões **Pausar bot** e **Despausar**.
     - Despausar reusa a lógica do `/unblock` existente (`del {number}_block`).
     - Pausar grava `{number}_block=true` **sem TTL** (fica pausado até você despausar
       manualmente — diferente do bloqueio automático de atendente humano, que expira).

Todas as rotas `/admin/*` (exceto login) exigem sessão válida via dependência FastAPI.

## Deploy (Docker + GitHub → VPS)

- **`Dockerfile`** — imagem Python com as dependências e o `app/`. Roda
  `uvicorn app.main:app`.
- **`docker-compose.yml`** — 2 serviços: `app` (agente + painel, porta 8000) e `redis`.
  Postgres/Supabase continuam externos (os que o usuário já usa). Volume para persistir o
  Redis.
- **`requirements.txt`** — versões fixas que funcionam (LangChain 0.3.x, pydantic ≥2.10,
  rodando em **Python 3.12** — 3.14 é incompatível com a stack LangChain 0.3).
- **`.env.example`** — todas as variáveis: credenciais dos serviços + `PAINEL_USER`,
  `PAINEL_PASS_HASH`, `SESSION_SECRET`.
- **Subir na VPS:** `git clone <repo>` → `docker compose up -d`. Agente em
  `:8000/webhook`, painel em `:8000/admin`.
- **HTTPS (recomendado):** exemplo de `Caddy` como reverse proxy na frente, terminando
  TLS automático. Login num link público **sem** HTTPS vaza a senha — incluído no
  `docker-compose` como serviço opcional comentado + instruções no README.

## Documentação (`AGENTS.md`)

`AGENTS.md` na raiz (+ `CLAUDE.md` curto apontando pra ele) cobrindo:

- Visão geral da arquitetura e o papel de cada módulo.
- Como o **config ao vivo** funciona (Redis → `get_config()`).
- **Passo a passo "como criar uma tool nova"**: criar `tools/minha_tool.py` com a factory
  `criar(descricao)`, registrar no `tools/__init__.py`, adicionar a chave em
  `tools_descricao` nos `DEFAULTS`, e o campo aparece sozinho no painel.
- **Passo a passo "como adicionar um config novo"**: incluir em `DEFAULTS`, usar via
  `get_config()`, adicionar o campo no template de configurações.
- Como rodar local (venv 3.12) e como deployar (compose).

## Tratamento de erros

- Config inválido no painel → mensagem no formulário, não grava.
- Redis indisponível ao ler config → cai nos `DEFAULTS` (agente nunca trava por causa de
  config).
- Login: senha errada → 401; rota admin sem sessão → redireciona pro login.
- Comportamento de erro do agente (timeout, fallback, retry de envio) **permanece igual**.

## Testes

- **Config:** lê `DEFAULTS` quando a chave não existe; grava e relê; rejeita valores fora
  da faixa.
- **Buffer:** confirma o reset deslizante (mensagem nova zera a contagem; só a última
  processa) e que lê o tempo do config.
- **Auth:** sem cookie → redireciona; senha errada → 401; cookie válido → acessa.
- **Smoke test:** o app sobe, `/health` responde, `/admin/login` responde, tools são
  instanciadas (extensão do smoke test que já roda hoje).

## Migração / sequência sugerida

1. Modularizar o código mantendo o comportamento (refactor puro, smoke test verde).
2. Introduzir `config.py` + trocar as constantes por `get_config()`.
3. Tools como factory com descrição dinâmica.
4. Painel: login → config → sessões.
5. Docker/compose + `.env.example` + HTTPS opcional.
6. `AGENTS.md`.

Cada passo é verificável de forma independente.
