import os
from dotenv import load_dotenv

load_dotenv()

ENV = os.getenv("ENV", "development").strip().lower()
SECRET_KEY = os.getenv("SECRET_KEY")
SYNC_TOKEN = os.getenv("SYNC_TOKEN", "").strip()
NBA_SYNC_SEASON = os.getenv("NBA_SYNC_SEASON", "2025-26").strip()
NBA_SYNC_SEASONS = tuple(
    temporada.strip()
    for temporada in os.getenv("NBA_SYNC_SEASONS", "2025-26,2026-27").split(",")
    if temporada.strip()
)


def _variavel_booleana(nome, padrao="false"):
    return os.getenv(nome, padrao).strip().lower() in {"1", "true", "yes", "on"}

# Facilita o primeiro acesso ao painel administrativo em uma instalação local.
# Deve permanecer desativado em produção.
FIRST_USER_ADMIN = ENV != "production" and _variavel_booleana("FIRST_USER_ADMIN")
AUTO_MIGRATE = _variavel_booleana("AUTO_MIGRATE")
ADMIN_EMAILS = {
    email.strip().lower()
    for email in os.getenv("ADMIN_EMAILS", "").split(",")
    if email.strip()
}

_cors_padrao = ",".join(
    [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "https://nba-prop-insights.vercel.app",
    ]
)

CORS_ORIGINS = {"https://nba-prop-insights.vercel.app"} | {
    origem.strip().rstrip("/")
    for origem in os.getenv("CORS_ORIGINS", _cors_padrao).split(",")
    if origem.strip()
}
