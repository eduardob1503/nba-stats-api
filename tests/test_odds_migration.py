import unittest
from pathlib import Path


class OddsMigrationTest(unittest.TestCase):
    def test_migration_preserva_snapshots_e_restringe_campos(self):
        sql = (Path(__file__).parents[1] / "migrations" / "007_odds_reais.sql").read_text(
            encoding="utf-8"
        )
        self.assertIn("CREATE TABLE IF NOT EXISTS odds_eventos", sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS odds_cotacoes", sql)
        self.assertIn("payload_hash", sql)
        self.assertIn("NUMERIC(10, 3)", sql)
        self.assertIn("'over', 'under', 'yes', 'no'", sql)
        self.assertNotIn("api_key", sql.lower())
        self.assertNotIn("DELETE FROM", sql.upper())


if __name__ == "__main__":
    unittest.main()
