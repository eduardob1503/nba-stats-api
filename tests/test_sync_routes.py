import unittest
from unittest.mock import MagicMock, Mock, patch

from app import app
from sync_data.routes import _normalizar_registro


class SyncRoutesTest(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True)
        self.client = app.test_client()

    def test_normaliza_minutos_no_formato_relogio(self):
        registro = _normalizar_registro({
            "game_id": "001",
            "game_date": "2026-01-10",
            "player_id": 2544,
            "player_name": "LeBron James",
            "min": "30:30",
            "pts": 25,
        })

        self.assertEqual(registro["minutos"], 30.5)
        self.assertEqual(registro["pontos"], 25)

    @patch("middlewares.sync.SYNC_TOKEN", "token-de-teste")
    @patch("sync_data.routes.execute_values")
    @patch("sync_data.routes.conectar")
    def test_recebe_lote_da_temporada_permitida(self, conectar, execute_values):
        conn = MagicMock()
        cursor = Mock()
        conn.cursor.return_value.__enter__.return_value = cursor
        conectar.return_value = conn

        resposta = self.client.post(
            "/sync/nba",
            headers={"X-Sync-Token": "token-de-teste"},
            json={
                "season": "2025-26",
                "season_type": "Regular Season",
                "records": [{
                    "game_id": "001",
                    "game_date": "2026-01-10",
                    "player_id": 2544,
                    "player_name": "LeBron James",
                    "team_id": 1610612747,
                    "team_abbreviation": "LAL",
                    "matchup": "LAL vs. GSW",
                    "wl": "W",
                    "pts": 25,
                }],
            },
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json["registros"], 1)
        self.assertEqual(execute_values.call_count, 3)
        conn.commit.assert_called_once()

    @patch("middlewares.sync.SYNC_TOKEN", "token-de-teste")
    def test_rejeita_outra_temporada(self):
        resposta = self.client.post(
            "/sync/nba",
            headers={"X-Sync-Token": "token-de-teste"},
            json={
                "season": "2024-25",
                "season_type": "Regular Season",
                "records": [{}],
            },
        )

        self.assertEqual(resposta.status_code, 400)
        self.assertIn("2025-26", resposta.json["erro"])

    def test_rejeita_token_invalido(self):
        with patch("middlewares.sync.SYNC_TOKEN", "token-correto"):
            resposta = self.client.post(
                "/sync/nba",
                headers={"X-Sync-Token": "token-errado"},
                json={},
            )

        self.assertEqual(resposta.status_code, 401)


if __name__ == "__main__":
    unittest.main()
