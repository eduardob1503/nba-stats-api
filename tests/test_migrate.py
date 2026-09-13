import unittest
from unittest.mock import MagicMock, Mock, patch

from migrate import executar_migracoes


class MigrateTest(unittest.TestCase):
    @patch("migrate.conectar")
    @patch("migrate.MIGRATIONS_DIR")
    def test_executa_somente_migrations_pendentes_e_registra(self, diretorio, conectar):
        class ArquivoFalso:
            def __init__(self, nome, conteudo):
                self.name = nome
                self.read_text = Mock(return_value=conteudo)

            def __lt__(self, outro):
                return self.name < outro.name

        pendente = ArquivoFalso("005_name_login.sql", "SQL DA MIGRATION 005")
        aplicada = ArquivoFalso("006_analises.sql", "SQL DA MIGRATION 006")
        diretorio.glob.return_value = [pendente, aplicada]

        conn = MagicMock()
        cursor = Mock()
        cursor.fetchone.side_effect = [None, (1,)]
        conn.cursor.return_value.__enter__.return_value = cursor
        conectar.return_value = conn

        executar_migracoes()

        comandos = [chamada.args[0] for chamada in cursor.execute.call_args_list]
        self.assertIn("SQL DA MIGRATION 005", comandos)
        self.assertTrue(any("INSERT INTO schema_migrations" in sql for sql in comandos))
        aplicada.read_text.assert_not_called()
        conn.commit.assert_called_once()

    @patch("migrate.conectar")
    @patch("migrate.MIGRATIONS_DIR")
    def test_falha_reverte_toda_a_transacao(self, diretorio, conectar):
        migration = Mock()
        migration.name = "005_name_login.sql"
        migration.read_text.side_effect = RuntimeError("falha")
        diretorio.glob.return_value = [migration]

        conn = MagicMock()
        cursor = Mock()
        cursor.fetchone.return_value = None
        conn.cursor.return_value.__enter__.return_value = cursor
        conectar.return_value = conn

        with self.assertRaises(RuntimeError):
            executar_migracoes()

        conn.rollback.assert_called_once()
        conn.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
