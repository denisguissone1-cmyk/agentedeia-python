# Deploy no EasyPanel (Create from Schema)

O arquivo [`easypanel-schema.json`](easypanel-schema.json) cria o projeto inteiro de uma vez,
já interligado: **app** (painel + webhook) + **worker** (fila) + **Postgres** + **Redis**.

## Passo a passo

O `createFromSchema` do EasyPanel espera o **objeto raiz `{ "services": [ … ] }`** (um
array com os serviços). Cole o [`easypanel-schema.json`](easypanel-schema.json) inteiro,
de uma vez.

1. **Crie antes o projeto `sofia`** no EasyPanel (dependendo da versão o import não cria
   o projeto sozinho e retorna 400 se o `projectName` não existir). Se quiser outro nome,
   troque os `"projectName": "sofia"` no JSON.
2. No projeto, use **Create from Schema** e cole o conteúdo de `easypanel-schema.json`.
3. O `app` e o `worker` usam a **imagem pronta** `ghcr.io/denisguissone1-cmyk/agentedeia-python:latest`
   (buildada pelo GitHub Action — veja abaixo). O EasyPanel só baixa e roda.
4. Acesse o painel pelo domínio gerado do serviço **app** → `/admin`.

> Formato que funciona: raiz `{ "services": [ … ] }`. Colar um array `[…]` dá *"Expected
> object, received array"*. No serviço `postgres` **não** inclua `username` (não é campo
> válido do schema e dispara 400) — o superusuário `postgres` já é criado pela imagem;
> a connection string usa ele.

## A imagem Docker (GHCR)

A imagem é **ghcr.io/denisguissone1-cmyk/agentedeia-python:latest**. O build do dia a dia
é **local** (mais rápido que na nuvem):

```bash
# 1. Login no GHCR (uma vez) — precisa de um PAT classic com escopo write:packages
#    GitHub → Settings → Developer settings → Personal access tokens (classic)
echo SEU_PAT | docker login ghcr.io -u denisguissone1-cmyk --password-stdin

# 2. Build (na raiz do projeto)
docker build -t ghcr.io/denisguissone1-cmyk/agentedeia-python:latest .

# 3. Push
docker push ghcr.io/denisguissone1-cmyk/agentedeia-python:latest
```

Depois do push, no EasyPanel clique em **Deploy** nos serviços `app` e `worker` para
puxarem a imagem nova.

**Uma vez só:** o pacote precisa estar **público** para o EasyPanel puxar sem login —
GitHub → perfil → **Packages** → `agentedeia-python` → *Package settings* → *Change
visibility* → **Public**. (Alternativa: manter privado e cadastrar credenciais do GHCR no
EasyPanel em Cluster → Registries, com um PAT de escopo `read:packages`.)

O workflow [`.github/workflows/docker.yml`](.github/workflows/docker.yml) faz o mesmo build
na nuvem, mas roda **só manualmente** (Actions → build-image → Run workflow) — fallback
para quando você não estiver na sua máquina.

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
