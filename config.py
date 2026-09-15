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


def _variavel_inteira(nome, padrao, minimo=1):
    try:
        valor = int(os.getenv(nome, str(padrao)))
    except (TypeError, ValueError):
        return padrao
    return valor if valor >= minimo else padrao


ODDSPAPI_API_KEY = os.getenv("ODDSPAPI_API_KEY", "").strip()
ODDSPAPI_BASE_URL = os.getenv("ODDSPAPI_BASE_URL", "https://api.oddspapi.io/v4").rstrip("/")
ODDSPAPI_BOOKMAKERS = tuple(
    item.strip().lower()
    for item in os.getenv("ODDSPAPI_BOOKMAKERS", "betano").split(",")
    if item.strip()
)
ODDSPAPI_SPORT_ID = _variavel_inteira("ODDSPAPI_SPORT_ID", 11)
ODDSPAPI_TOURNAMENT_ID = _variavel_inteira("ODDSPAPI_TOURNAMENT_ID", 132)
ODDSPAPI_TIMEOUT = _variavel_inteira("ODDSPAPI_TIMEOUT", 20)
ODDSPAPI_SYNC_MAX_REQUESTS = _variavel_inteira("ODDSPAPI_SYNC_MAX_REQUESTS", 15)
ODDSPAPI_SYNC_COOLDOWN_MINUTES = _variavel_inteira(
    "ODDSPAPI_SYNC_COOLDOWN_MINUTES", 30
)
ODDSPAPI_FIXTURE_WINDOW_HOURS = _variavel_inteira("ODDSPAPI_FIXTURE_WINDOW_HOURS", 48)
ODDSPAPI_ODDS_MAX_AGE_MINUTES = _variavel_inteira(
    "ODDSPAPI_ODDS_MAX_AGE_MINUTES", 60
)
ODDSPAPI_MARKETS_CACHE_HOURS = _variavel_inteira("ODDSPAPI_MARKETS_CACHE_HOURS", 168)
