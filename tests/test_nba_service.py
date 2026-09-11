import unittest
from datetime import date
from unittest.mock import Mock, patch

from services.nba import (
    JogadorNBAInexistente,
    buscar_jogos,
    buscar_jogadores_nba,
    encontrar_jogador,
    encontrar_jogador_por_id,
    temporada_atual,
    validar_temporada,
)


class NBAServiceTest(unittest.TestCase):
    def test_temporada_atual_muda_em_outubro(self):
        self.assertEqual(temporada_atual(date(2026, 9, 9)), "2025-26")
        self.assertEqual(temporada_atual(date(2026, 10, 1)), "2026-27")

    def test_validar_temporada_rejeita_intervalo_incorreto(self):
        with self.assertRaises(ValueError):
            validar_temporada("2025-27")

    @patch("services.nba.nba_players.get_players")
    def test_encontrar_jogador_ignora_acentos_e_prioriza_ativo(self, get_players):
        get_players.return_value = [
            {"id": 1, "full_name": "Nikola Jokić", "is_active": False},
            {"id": 2, "full_name": "Nikola Jokić", "is_active": True},
        ]

        jogador = encontrar_jogador("Nikola Jokic")

        self.assertEqual(jogador["id"], 2)

    @patch("services.nba.nba_players.get_players", return_value=[])
    def test_encontrar_jogador_inexistente(self, _get_players):
        with self.assertRaises(JogadorNBAInexistente):
            encontrar_jogador("Jogador Inventado")

    @patch("services.nba.nba_players.get_players")
    def test_busca_inteligente_ignora_acentos_e_prioriza_ativo(self, get_players):
        get_players.return_value = [
            {"id": 1, "full_name": "Nikola Jokić", "is_active": False},
            {"id": 2, "full_name": "Nikola Jović", "is_active": True},
            {"id": 3, "full_name": "Johnny Davis", "is_active": True},
        ]

        jogadores = buscar_jogadores_nba("nik jo")

        self.assertEqual([jogador["id"] for jogador in jogadores], ["nba:2", "nba:1"])
        self.assertEqual(jogadores[1]["nome"], "Nikola Jokić")

    @patch("services.nba.nba_players.find_player_by_id")
    def test_encontrar_jogador_por_id(self, find_player_by_id):
        find_player_by_id.return_value = {
            "id": 2544,
            "full_name": "LeBron James",
            "is_active": True,
        }

        jogador = encontrar_jogador_por_id("2544")

        self.assertEqual(jogador["nome"], "LeBron James")

    @patch("services.nba.playergamelog.PlayerGameLog")
    def test_buscar_jogos_normaliza_e_ordena_resposta(self, player_game_log):
        endpoint = Mock()
        endpoint.get_normalized_dict.return_value = {
            "PlayerGameLog": [
                {
                    "Game_ID": "002",
                    "GAME_DATE": "NOV 01, 2025",
                    "MATCHUP": "LAL vs. MIA",
                    "PTS": 31,
                },
                {
                    "Game_ID": "001",
                    "GAME_DATE": "OCT 29, 2025",
                    "MATCHUP": "LAL @ MIN",
                    "PTS": 27,
                },
            ]
        }
        player_game_log.return_value = endpoint

        resultado = buscar_jogos(
            "LeBron James", temporada="2025-26", nba_player_id=2544
        )

        self.assertEqual([jogo["pontos"] for jogo in resultado["jogos"]], [31, 27])
        self.assertEqual(resultado["jogos"][0]["game_id"], "002")


if __name__ == "__main__":
    unittest.main()
