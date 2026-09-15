import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from services.odds_normalizacao import (
    fixture_elegivel,
    identificar_mercado,
    normalizar_catalogo_mercados,
    normalizar_fixtures,
    normalizar_nome_jogador,
    normalizar_odds,
)


FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(nome):
    return json.loads((FIXTURES / nome).read_text(encoding="utf-8"))


class OddsNormalizacaoTest(unittest.TestCase):
    def test_identifica_mercados_suportados_e_rejeita_ambiguo(self):
        catalogo = normalizar_catalogo_mercados(
            _fixture("oddspapi_markets.json"), 11
        )
        detectados = {
            item["provedor_market_id"]: item["mercado"] for item in catalogo
        }

        self.assertEqual(detectados["m-points"], "pontos")
        self.assertEqual(detectados["m-assists"], "assistencias")
        self.assertEqual(detectados["m-rebounds"], "rebotes")
        self.assertEqual(detectados["m-threes"], "cestas_3")
        self.assertEqual(detectados["m-pa"], "pa")
        self.assertEqual(detectados["m-ar"], "ar")
        self.assertEqual(detectados["m-par"], "par")
        self.assertIsNone(detectados["m-pr"])
        self.assertIsNone(detectados["m-team"])
        self.assertNotIn("tentativas_3", detectados.values())

    def test_nao_confunde_sport_ou_nome_generico(self):
        self.assertIsNone(identificar_mercado({
            "sportId": 12, "marketName": "Points", "playerProp": True
        }, 11))
        self.assertIsNone(identificar_mercado({
            "sportId": 11, "marketName": "First Team to Score", "playerProp": True
        }, 11))

    def test_normaliza_fixtures_e_filtra_finalizadas(self):
        fixtures = normalizar_fixtures(
            _fixture("oddspapi_fixtures.json"), 11, 132
        )
        agora = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
        fim = datetime(2026, 10, 22, 12, tzinfo=timezone.utc)

        self.assertEqual(fixtures[0]["time_casa"], "Los Angeles Lakers")
        self.assertTrue(fixture_elegivel(fixtures[0], agora, fim))
        self.assertFalse(fixture_elegivel(fixtures[1], agora, fim))
        self.assertEqual(normalizar_fixtures({"fixtures": []}, 11, 132), [])

    def test_processa_apenas_betano_alternativas_over_under_e_odds_validas(self):
        catalogo = {
            "m-points": "pontos",
            "m-assists": "assistencias",
        }
        props = normalizar_odds(
            _fixture("oddspapi_odds.json"), "betano", catalogo
        )

        self.assertEqual(len(props), 4)
        self.assertEqual(
            [(str(item["linha"]), item["lado"]) for item in props[:3]],
            [("25.5", "over"), ("25.5", "under"), ("27.5", "over")],
        )
        self.assertEqual(props[3]["mercado"], "assistencias")
        self.assertEqual(props[3]["nome_normalizado"], "nikola jokic")
        self.assertTrue(all(item["odd"] > 1 for item in props))

    def test_partida_sem_betano_ou_betano_sem_props_retorna_vazio(self):
        self.assertEqual(normalizar_odds({"bookmakers": []}, "betano"), [])
        self.assertEqual(normalizar_odds({
            "bookmakers": [{"name": "outra", "markets": []}]
        }, "betano"), [])
        self.assertEqual(normalizar_odds({
            "bookmakers": [{"name": "betano", "markets": []}]
        }, "betano"), [])

    def test_normaliza_acentos_espacos_e_sobrenome_primeiro(self):
        self.assertEqual(normalizar_nome_jogador(" Nikola   Jokić "), "nikola jokic")
        self.assertEqual(normalizar_nome_jogador("James, LeBron"), "lebron james")


if __name__ == "__main__":
    unittest.main()
