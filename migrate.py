from pathlib import Path

from database import conectar


MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def executar_migracoes():
    arquivos = sorted(MIGRATIONS_DIR.glob("*.sql"))
    conn = conectar()
    try:
        with conn.cursor() as cur:
            # Evita que duas inicializações serverless executem a migração juntas.
            cur.execute("SELECT pg_advisory_xact_lock(%s)", (73184923,))
            for arquivo in arquivos:
                cur.execute(arquivo.read_text(encoding="utf-8"))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    executar_migracoes()
    print("Migrações aplicadas com sucesso.")
