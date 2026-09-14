import unittest
from decimal import Decimal

from services.oportunidades import calcular_ranking


def _jogador(player_id, nome, partidas):
    return {
        "nba_player_id": player_id,
        "nome": nome,
        "ativo": None,
        "partidas": partidas,
    }


class OportunidadesServiceTest(unittest.TestCase):
    def test_calcula_cestas_tentativas_e_compostos(self):
        partida = {
            "data": "2026-01-02",
            "pontos": 20,
            "assistencias": 8,
            "rebotes": 10,
            "cestas_3": 3,
            "tentativas_3": 7,
        }
        casos = {
            "cestas_3": Decimal("2.5"),
            "tentativas_3": Decimal("6.5"),
            "pa": Decimal("27.5"),
            "ar": Decimal("17.5"),
            "par": Decimal("37.5"),
        }
        for mercado, linha in casos.items():
            with self.subTest(mercado=mercado):
                resultado = calcular_ranking(
                    [_jogador(1, "Jogador", [partida])],
                    mercado,
                    linha,
                    Decimal("2"),
                    "over",
                    1,
                    20,
                )
                self.assertEqual(resultado["total_ev_positivo"], 1)
                self.assertEqual(resultado["oportunidades"][0]["acertos"], 1)

    def test_over_under_push_e_partida_sem_dado(self):
        partidas = [
            {"data": "2026-01-04", "pontos": 12},
            {"data": "2026-01-03", "pontos": 10},
            {"data": "2026-01-02", "pontos": 8},
            {"data": "2026-01-01", "pontos": None},
        ]
        over = calcular_ranking(
            [_jogador(1, "Jogador", partidas)],
            "pontos",
            Decimal("10"),
            Decimal("2.1"),
            "over",
            3,
            20,
        )["oportunidades"][0]
        under = calcular_ranking(
            [_jogador(1, "Jogador", partidas)],
            "pontos",
            Decimal("10"),
            Decimal("2.1"),
            "under",
            3,
            20,
        )["oportunidades"][0]

        self.assertEqual((over["acertos"], over["erros"], over["pushes"]), (1, 1, 1))
        self.assertEqual((under["acertos"], under["erros"], under["pushes"]), (1, 1, 1))
        self.assertEqual(over["jogos_sem_dado"], 1)
        self.assertEqual(over["probabilidade_historica"], 0.5)
        self.assertEqual(over["valores_recentes"], [12, 10, 8])

    def test_composto_ignora_partida_se_um_componente_esta_ausente(self):
        partidas = [
            {"data": "2026-01-02", "pontos": 20, "assistencias": None},
            {"data": "2026-01-01", "pontos": 20, "assistencias": 5},
        ]
        resultado = calcular_ranking(
            [_jogador(1, "Jogador", partidas)],
            "pa",
            Decimal("20"),
            Decimal("1.9"),
            "over",
            1,
            20,
        )["oportunidades"][0]

        self.assertEqual(resultado["jogos_validos"], 1)
        self.assertEqual(resultado["jogos_sem_dado"], 1)
        self.assertEqual(resultado["ultimo_valor"], 25)

    def test_minimo_jogos_e_pushes_sem_decisao_excluem_jogador(self):
        poucos = _jogador(1, "Poucos", [{"pontos": 20}])
        pushes = _jogador(2, "Pushes", [{"pontos": 10}, {"pontos": 10}])

        resultado = calcular_ranking(
            [poucos, pushes], "pontos", Decimal("10"), Decimal("2"), "over", 2, 20
        )

        self.assertEqual(resultado["total_elegiveis"], 0)
        self.assertEqual(resultado["oportunidades"], [])

    def test_retorna_somente_ev_positivo_e_contabiliza_zero_e_negativo(self):
        jogadores = [
            _jogador(1, "Positivo", [{"pontos": 11}, {"pontos": 12}]),
            _jogador(2, "Zero", [{"pontos": 11}, {"pontos": 9}]),
            _jogador(3, "Negativo", [{"pontos": 9}, {"pontos": 8}]),
        ]
        resultado = calcular_ranking(
            jogadores, "pontos", Decimal("10"), Decimal("2"), "over", 2, 20
        )

        self.assertEqual(resultado["total_elegiveis"], 3)
        self.assertEqual(resultado["total_ev_positivo"], 1)
        self.assertEqual(
            [item["jogador"]["nome"] for item in resultado["oportunidades"]],
            ["Positivo"],
        )
        self.assertEqual(resultado["oportunidades"][0]["ev"], 1)

    def test_ordena_por_ev_probabilidade_decisoes_nome_e_aplica_limite(self):
        jogadores = [
            _jogador(1, "Menor probabilidade", [{"pontos": 11}, {"pontos": 9}, {"pontos": 11}]),
            _jogador(2, "Zulu", [{"pontos": 11}, {"pontos": 11}]),
            _jogador(3, "Beta", [{"pontos": 11}, {"pontos": 11}]),
            _jogador(4, "Alfa", [{"pontos": 11}]),
            _jogador(5, "Intermediario", [{"pontos": 11}] * 3 + [{"pontos": 9}]),
        ]
        resultado = calcular_ranking(
            jogadores, "pontos", Decimal("10"), Decimal("2"), "over", 1, 3
        )

        self.assertEqual(resultado["total_ev_positivo"], 5)
        self.assertEqual(
            [item["jogador"]["nome"] for item in resultado["oportunidades"]],
            ["Beta", "Zulu", "Alfa"],
        )
        self.assertEqual([item["posicao"] for item in resultado["oportunidades"]], [1, 2, 3])

    def test_formula_edge_ev_e_estatisticas_usam_decimal(self):
        partidas = [
            {"data": "2026-01-03", "pontos": Decimal("3")},
            {"data": "2026-01-02", "pontos": Decimal("2")},
            {"data": "2026-01-01", "pontos": Decimal("1")},
        ]
        item = calcular_ranking(
            [_jogador(1, "Jogador", partidas)],
            "pontos",
            Decimal("1.5"),
            Decimal("1.9"),
            "over",
            3,
            20,
        )["oportunidades"][0]

        self.assertEqual(item["probabilidade_historica"], 0.666667)
        self.assertEqual(item["probabilidade_implicita"], 0.526316)
        self.assertEqual(item["edge"], 0.140351)
        self.assertEqual(item["ev"], 0.266667)
        self.assertEqual(item["media"], 2)
        self.assertEqual(item["mediana"], 2)
        self.assertEqual(item["ultima_partida"], "2026-01-03")


if __name__ == "__main__":
    unittest.main()
