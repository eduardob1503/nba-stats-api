import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")

_cors_padrao = ",".join(
    [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
)

CORS_ORIGINS = {
    origem.strip().rstrip("/")
    for origem in os.getenv("CORS_ORIGINS", _cors_padrao).split(",")
    if origem.strip()
}
