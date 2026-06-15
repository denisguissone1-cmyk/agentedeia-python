"""Smoke test: carrega o agente com env fictício e lista o que foi instanciado."""
import os, importlib.util

# Variaveis de ambiente ficticias (so para o modulo carregar sem credenciais reais)
os.environ.setdefault("SUPABASE_URL", "https://exemplo.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "chave-ficticia")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("OPENAI_API_KEY", "sk-ficticia")
os.environ.setdefault("GOOGLE_API_KEY", "google-ficticia")
os.environ.setdefault("UAZAPI_URL", "https://exemplo.uazapi.com")
os.environ.setdefault("UAZAPI_TOKEN", "token-ficticio")
os.environ.setdefault("POSTGRES_CONN", "postgresql://u:p@localhost/db")
os.environ.setdefault("GOOGLE_CALENDAR_ID", "cal@group.calendar.google.com")
os.environ.setdefault("WEBHOOK_TOKEN", "segredo")

spec = importlib.util.spec_from_file_location("agente", "agente_whatsapp (1).py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

print("OK -> modulo carregado e instanciado")
print("App FastAPI:", type(mod.app).__name__)
print("Rotas HTTP expostas:")
for r in mod.app.routes:
    if hasattr(r, "methods"):
        print("   ", ",".join(r.methods), r.path)

tools = [mod.buscar_info, mod.consultar_agenda, mod.pre_marcacao, mod.desmarcar]
print("Tools do agente:", [t.name for t in tools])
print("Tool dinamica (closure):", mod.criar_tool_cadastrar("5511999@c.us").name)
