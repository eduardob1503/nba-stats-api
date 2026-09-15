import unittest
from decimal import Decimal
from unittest.mock import MagicMock, Mock, patch

from services.odds_storage import mapear_jogador, salvar_props_evento


def _prop(nome="Nikola Jokić", player_id="p1"):
    return {
        "provedor_market_id": "m-points",
        "mercado": "pontos",
        "provedor_player_id": player_id,
        "jogador_nome_provedor": nome,
        "nome_normalizado": "nikola jokic",
        "linha": Decimal("25.5"),
        "lado": "over",
        "odd": Decimal("1.9"),
        "atualizada_em_provedor": None,
        "payload_hash": "a" * 64,
    }


class OddsStorageTest(unittest.TestCase):
    def test_mapeia_nome_unico_com_acento_para_id_interno(self):
        conn = MagicMock()
        cursor = Mock()
        cursor.fetchone.return_value = None
        cursor.fetchall.return_value = [("Nikola Jokić", 203999)]
        conn.cursor.return_value.__enter__.return_value = cursor

        jogador_id = mapear_jogador(conn, _prop())

        self.assertEqual(jogador_id, "nba:203999")
        parametros_insert = cursor.execute.call_args.args[1]
        self.assertEqual(parametros_insert[-2:], ("nba:203999", True))

    def test_nao_confirma_nome_ambiguo_ou_desconhecido(self):
        for jogadores in (
            [],
            [("Nome Igual", 1), ("Nome Igual", 2)],
        ):
            with self.subTest(jogadores=jogadores):
                conn = MagicMock()
                cursor = Mock()
                cursor.fetchone.return_value = None
                cursor.fetchall.return_value = jogadores
                conn.cursor.return_value.__enter__.return_value = cursor
                prop = _prop(nome="Nome Igual", player_id=None)
                prop["nome_normalizado"] = "nome igual"

                self.assertIsNone(mapear_jogador(conn, prop))
                self.assertEqual(cursor.execute.call_args.args[1][-2:], (None, False))

    @patch("services.odds_storage.mapear_jogador", return_value="nba:2544")
    def test_inativa_ausentes_e_upsert_deduplica_snapshot(self, mapear):
        conn = MagicMock()
        cursor = Mock()
        cursor.fetchone.return_value = (10,)
        conn.cursor.return_value.__enter__.return_value = cursor

        salvas, sem_jogador = salvar_props_evento(conn, 5, "betano", [_prop()])

        self.assertEqual((salvas, sem_jogador), (1, 0))
        comandos = [chamada.args[0] for chamada in cursor.execute.call_args_list]
        self.assertIn("SET ativa = FALSE", comandos[0])
        self.assertIn("ON CONFLICT", comandos[1])
        self.assertIn("payload_hash", comandos[1])


if __name__ == "__main__":
    unittest.main()
