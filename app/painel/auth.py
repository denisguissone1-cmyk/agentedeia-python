"""Autenticação simples do painel: um usuário admin (credenciais no .env).

Gerar o hash da senha:
  python -c "import hashlib,sys;print(hashlib.sha256(sys.argv[1].encode()).hexdigest())" MINHA_SENHA
"""
import hashlib
import hmac
import os

from fastapi import Request
from fastapi.responses import RedirectResponse

PAINEL_USER      = os.getenv("PAINEL_USER", "admin")
PAINEL_PASS_HASH = os.getenv("PAINEL_PASS_HASH", "")
SESSION_SECRET   = os.getenv("SESSION_SECRET", "troque-esse-segredo")


def conferir(usuario_in: str, senha_in: str, *, usuario=None, senha_hash=None) -> bool:
    usuario = usuario if usuario is not None else PAINEL_USER
    senha_hash = senha_hash if senha_hash is not None else PAINEL_PASS_HASH
    hash_in = hashlib.sha256(senha_in.encode()).hexdigest()
    ok_user = hmac.compare_digest(usuario_in, usuario)
    ok_pass = hmac.compare_digest(hash_in, senha_hash or "")
    return ok_user and ok_pass


def logado(request: Request) -> bool:
    return bool(request.session.get("user"))


def exigir_login(request: Request):
    """Use como dependência; retorna RedirectResponse se não logado, senão None."""
    if not logado(request):
        return RedirectResponse("/admin/login", status_code=302)
    return None
