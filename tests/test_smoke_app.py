import os

os.environ.setdefault("SUPABASE_URL", "https://exemplo.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "x")
os.environ.setdefault("OPENAI_API_KEY", "x")
os.environ.setdefault("GOOGLE_API_KEY", "x")
os.environ.setdefault("UAZAPI_URL", "https://x")
os.environ.setdefault("UAZAPI_TOKEN", "x")
os.environ.setdefault("POSTGRES_CONN", "postgresql://u:p@localhost/db")
os.environ.setdefault("GOOGLE_CALENDAR_ID", "x")
os.environ.setdefault("PAINEL_USER", "admin")
os.environ.setdefault("PAINEL_PASS_HASH", "x")
os.environ.setdefault("SESSION_SECRET", "dev-secret")


def test_app_monta_e_expoe_rotas():
    from app.main import app

    # Rotas de nível raiz
    paths = {r.path for r in app.routes if hasattr(r, "path")}
    assert "/webhook" in paths
    assert "/health" in paths

    # API JSON do painel (consumida pelo SPA React; APIRouter com prefix="/api")
    # url_path_for confirma que a rota está registrada no roteador da aplicação
    assert str(app.url_path_for("login")) == "/api/login"
    assert str(app.url_path_for("dashboard")) == "/api/dashboard"
    assert str(app.url_path_for("tools")) == "/api/tools"
    assert str(app.url_path_for("prompt_get")) == "/api/prompt"
    assert str(app.url_path_for("sessoes")) == "/api/sessoes"
    assert str(app.url_path_for("logs")) == "/api/logs"
    assert str(app.url_path_for("config_get")) == "/api/config"
