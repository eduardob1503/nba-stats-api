import unittest
from datetime import datetime, timezone
from decimal import Decimal

from services.oportunidades_reais import (
    calcular_oportunidade_real,
    ordenar_oportunidades_reais,
)


def _cotacao(mercado="pontos", linha="10", odd="2", lado="over"):
    return {
        "evento_id": 1,
        "provedor_fixture_id": "fixture-1",
        "inicio_em": "2026-10-21T00:30:00Z",
        "time_casa": "Lakers",
        "time_fora": "Warriors",
        "jogador_id": "nba:2544",
        "jogador_nome": "LeBron James",
        "mercado": mercado,
        "linha": Decimal(linha),
        "lado": lado,
        "odd": Decimal(odd),
        "bookmaker": "betano",
        "capturada_em": "2026-10-20T18:30:00Z",
    }


class OportunidadesReaisTest(unittest.TestCase):
    def test_calcula_todos_os_mercados_reais_com_linha_e_odd_individuais(self):
        partida = {
            "pontos": 20,
            "assistencias": 8,
            "rebotes": 10,
            "cestas_3": 3,
        }
        linhas = {
            "pontos": "19.5",
            "assistencias": "7.5",
            "rebotes": "9.5",
            "cestas_3": "2.5",
            "pa": "27.5",
            "ar": "17.5",
            "par": "37.5",
        }
        for mercado, linha in linhas.items():
            with self.subTest(mercado=mercado):
                resultado = calcular_oportunidade_real(
                    _cotacao(mercado, linha, "1.9"),
                    [partida],
                    1,
                    False,
                    Decimal("25"),
                    Decimal("75"),
                    Decimal("3"),
                    Decimal("20"),
                )
                self.assertIsNotNone(resultado)
                self.assertEqual(resultado["mercado"], mercado)
                self.assertEqual(resultado["odd"], 1.9)

    def test_push_nao_entra_nas_decisoes(self):
        resultado = calcular_oportunidade_real(
            _cotacao(linha="10", odd="2.1"),
            [{"pontos": 11}, {"pontos": 10}, {"pontos": 9}],
            3,
            False,
            Decimal("25"),
            Decimal("75"),
            Decimal("0"),
            Decimal("100"),
        )

        self.assertEqual((resultado["acertos"], resultado["erros"], resultado["pushes"]), (1, 1, 1))
        self.assertEqual(resultado["probabilidade_historica"], 0.5)

    def test_plausibilidade_e_ev_filtram_resultado(self):
        partidas = [{"pontos": 11}] * 7 + [{"pontos": 9}] * 3
        aprovada = calcular_oportunidade_real(
            _cotacao(linha="10", odd="2"),
            partidas,
            10,
            True,
            Decimal("25"),
            Decimal("75"),
            Decimal("10"),
            Decimal("25"),
        )
        fora = calcular_oportunidade_real(
            _cotacao(linha="5", odd="2"),
            partidas,
            10,
            True,
            Decimal("25"),
            Decimal("75"),
            Decimal("10"),
            Decimal("25"),
        )

        self.assertTrue(aprovada["linha_dentro_faixa"])
        self.assertTrue(aprovada["edge_dentro_faixa"])
        self.assertIsNone(fora)

    def test_ordena_por_ev_edge_decisoes_e_nome(self):
        itens = [
            {"_ev": Decimal("0.2"), "_edge": Decimal("0.1"), "_decisoes": 8, "jogador_nome": "Zulu", "jogador_id": "nba:2"},
            {"_ev": Decimal("0.3"), "_edge": Decimal("0.1"), "_decisoes": 5, "jogador_nome": "Alfa", "jogador_id": "nba:1"},
        ]
        resultado = ordenar_oportunidades_reais(itens, 1)
        self.assertEqual(resultado[0]["jogador_nome"], "Alfa")
        self.assertNotIn("_ev", resultado[0])


if __name__ == "__main__":
    unittest.main()
