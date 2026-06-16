# Deploy no EasyPanel (Create from Schema)

O arquivo [`easypanel-schema.json`](easypanel-schema.json) cria o projeto inteiro de uma vez,
já interligado: **app** (painel + webhook) + **worker** (fila) + **Postgres** + **Redis**.

## Passo a passo

1. No EasyPanel, crie um projeto chamado **`sofia`** (precisa ser esse nome — é o
   `projectName` do schema; se quiser outro, troque os 4 `"projectName": "sofia"` no JSON).
2. Importe o schema **a nível de PROJETO**, não de serviço:
   - abra o projeto `sofia` → menu/aba **Schema** → **Import / Create from Schema**.
   - ⚠️ Não use o "Create Service → From Schema" (esse cria **um** serviço e espera só
     `{type, data}`; colar o `{services:[…]}` ali dá o erro *React #31 / object with keys
     {services}*).
3. Cole o conteúdo de `easypanel-schema.json` e confirme.
4. O EasyPanel cria os 4 serviços. O `app` e o `worker` são buildados direto deste
   repositório no GitHub (via Dockerfile). Aguarde o primeiro build terminar.
5. Acesse o painel pelo domínio gerado do serviço **app** → `/admin`.

> O repositório precisa estar **acessível** pelo EasyPanel: ou público, ou com a conta
> GitHub conectada no EasyPanel (Settings → Git). Se o seu EasyPanel pedir source por URL
> em vez de owner/repo, troque o bloco `source` por
> `{"type":"git","repo":"https://github.com/denisguissone1-cmyk/agentedeia-python.git","ref":"main"}`.

## Como a interligação funciona

- Os serviços se enxergam pelo host interno `$(PROJECT_NAME)_<serviço>`.
- O app e o worker já recebem, prontos:
  - `REDIS_URL=redis://default:…@$(PROJECT_NAME)_redis:6379`
  - `POSTGRES_CONN=postgresql://postgres:…@$(PROJECT_NAME)_postgres:5432/elizabeth`
- A tabela `cadastro` é criada **automaticamente no boot** (não depende de init.sql).
- `WEBHOOK_BASE_URL` já vem como `https://$(EASYPANEL_DOMAIN)`, então a URL do webhook
  aparece pronta no painel.

## Depois do deploy (importante)

1. **Troque a senha do painel.** O schema vem com `admin` / `elizabeth2025` (hash embutido).
   Gere um novo hash e atualize a env `PAINEL_PASS_HASH` do serviço `app`:
   ```bash
   python -c "import hashlib;print(hashlib.sha256(b'SUA_NOVA_SENHA').hexdigest())"
   ```
2. **Preencha os tokens** em `/admin/config`: Google Gemini (obrigatório p/ a IA),
   UAZAPI (URL + token), OpenAI (áudio/imagem). Aplicam na hora, sem restart.
3. **Registre o webhook**: em `/admin/config → Webhook`, clique em *Registrar na UAZAPI*
   (ou copie a URL e cole na sua instância).
4. (Opcional) Google Calendar: para as tools de agenda, adicione as envs
   `GOOGLE_CALENDAR_ID` e `GOOGLE_CALENDAR_CREDS` (caminho de um arquivo de service account
   montado no container).

## Escalar o worker

Para aguentar mais volume, aumente as réplicas do serviço `worker` no EasyPanel
(ou `replicas` no schema). A fila no Redis distribui os jobs entre eles.

## Segurança

Os segredos no schema (senhas do Postgres/Redis, `SESSION_SECRET`, hash do painel) foram
gerados para este deploy. Se for reutilizar o schema publicamente, **gere novos valores**.
