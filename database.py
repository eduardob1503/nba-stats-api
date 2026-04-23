import psycopg2
import os
from dotenv import load_dotenv
from config import DATABASE_URL
load_dotenv()

def conectar():
    ENV = os.getenv("ENV")

    if ENV == "production":
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        return conn
    else:
        conn = psycopg2.connect(**DATABASE_URL)
        return conn