import psycopg2
from config import DATABASE_URL
def conectar():
    conn = psycopg2.connect(**DATABASE_URL)
    return conn