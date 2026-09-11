import psycopg2
import os
from dotenv import load_dotenv
from config import ENV

load_dotenv()

def conectar():
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL não configurada")

    opcoes = {"connect_timeout": 10, "application_name": "nba-props-api"}
    if ENV == "production" and "sslmode=" not in DATABASE_URL:
        opcoes["sslmode"] = "require"
    return psycopg2.connect(DATABASE_URL, **opcoes)
