import hashlib

from app.painel import auth


def test_senha_correta_confere():
    h = hashlib.sha256("segredo123".encode()).hexdigest()
    assert auth.conferir("admin", "segredo123", usuario="admin", senha_hash=h) is True


def test_usuario_ou_senha_errado_falha():
    h = hashlib.sha256("segredo123".encode()).hexdigest()
    assert auth.conferir("admin", "errada", usuario="admin", senha_hash=h) is False
    assert auth.conferir("outro", "segredo123", usuario="admin", senha_hash=h) is False
