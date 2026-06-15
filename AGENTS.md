# AGENTS.md — Guia de manutenção do Agente Elizabeth

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
faixas de validação estão em `app/config.py`.

## Como criar uma TOOL nova

1. Crie `app/tools/minha_tool.py`:
   ```python
   from langchain.tools import tool

   def criar(descricao: str):
       @tool("minha_tool", description=descricao)
       async def minha_tool(param: str) -> str:
           return "resultado"
       return minha_tool
   ```
2. Em `app/config.py`, adicione a chave em `TOOLS_DESCRICAO_DEFAULT`:
   ```python
   TOOLS_DESCRICAO_DEFAULT["minha_tool"] = "Descrição que o LLM vai ler."
   ```
3. Em `app/tools/__init__.py`, importe o módulo e registre em `_SEM_NUMERO`
   (ou trate o closure se precisar do número, como `cadastrar`).
4. Pronto: a descrição já aparece editável no painel e o agente já enxerga a tool.

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
