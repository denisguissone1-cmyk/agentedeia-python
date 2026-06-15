# Agente WhatsApp Elizabeth + Painel

## Deploy na VPS

1. `git clone <repo> && cd <repo>`
2. `cp .env.example .env` e preencha as variáveis.
3. Gere o hash da senha do painel:
   `python -c "import hashlib;print(hashlib.sha256(b'SUA_SENHA').hexdigest())"`
4. `docker compose up -d --build`
5. Agente: `http://SEU_IP:8000/webhook` · Painel: `http://SEU_IP:8000/admin`

> Use HTTPS em produção (serviço `caddy` comentado no compose). Login sem HTTPS expõe a senha.

## Desenvolvimento local (Python 3.12)

`.venv\Scripts\python.exe -m pytest` roda os testes.
