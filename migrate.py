from pathlib import Path

from database import conectar


MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def executar_migracoes():
    arquivos = sorted(MIGRATIONS_DIR.glob("*.sql"))
    conn = conectar()
    try:
        with conn.cursor() as cur:
            # Serializa inicializações concorrentes e registra cada arquivo aplicado.
            cur.execute("SELECT pg_advisory_xact_lock(%s)", (73184923,))
            cur.execute(
                """CREATE TABLE IF NOT EXISTS schema_migrations (
                       nome VARCHAR(255) PRIMARY KEY,
                       aplicada_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
                   )"""
            )
            for arquivo in arquivos:
                cur.execute(
                    "SELECT 1 FROM schema_migrations WHERE nome = %s",
                    (arquivo.name,),
                )
                if cur.fetchone() is not None:
                    continue
                cur.execute(arquivo.read_text(encoding="utf-8"))
                cur.execute(
                    "INSERT INTO schema_migrations (nome) VALUES (%s)",
                    (arquivo.name,),
                )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    executar_migracoes()
    print("Migrações aplicadas com sucesso.")
