import unittest
from unittest.mock import Mock, call, patch

from scripts.sync_last_season import enviar_temporada


class SyncScriptTest(unittest.TestCase):
    @patch("scripts.sync_last_season.requests.post")
    @patch("scripts.sync_last_season.obter_status")
    def test_envio_incremental_reenvia_somente_ultimo_dia(
        self, obter_status, post
    ):
        obter_status.side_effect = [
            {"ultima_partida": "2026-04-12"},
            {"ultima_partida": None},
            {"registros": 2, "ultima_partida": "2026-04-12"},
        ]
        post.return_value = Mock(ok=True)
        dados = {
            "season": "2025-26",
            "season_types": {
                "Regular Season": [
                    {"game_date": "2026-04-11", "game_id": "001"},
                    {"game_date": "2026-04-12", "game_id": "002"},
                ],
                "Playoffs": [],
            },
        }

        enviar_temporada(dados, "https://api.example", "token", 400)

        self.assertEqual(post.call_count, 1)
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["season"], "2025-26")
        self.assertEqual(payload["records"], [{"game_date": "2026-04-12", "game_id": "002"}])
        self.assertEqual(
            obter_status.call_args_list,
            [
                call("https://api.example", "token", "2025-26", "Regular Season"),
                call("https://api.example", "token", "2025-26", "Playoffs"),
                call("https://api.example", "token", "2025-26"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
