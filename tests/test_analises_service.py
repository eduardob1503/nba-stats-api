import unittest

from services.analises import (
    MERCADOS_PERMITIDOS,
    calcular_analise,
    normalizar_quantidade,
    valor_mercado,
)


class AnalisesServiceTest(unittest.TestCase):
    def setUp(self):
        self.partidas = [
            {
                "game_id": "002",
                "data": "2026-01-02",
                "adversario": "LAL vs. GSW",
                "pontos": 10,
                "assistencias": 5,
                "rebotes": 7,
                "cestas_3": 2,
                "tentativas_3": 6,
            },
            {
                "game_id": "001",
                "data": "2026-01-01",
                "adversario": "LAL @ MIN",
                "pontos": 8,
                "assistencias": 2,
                "rebotes": 4,
                "cestas_3": 0,
                "tentativas_3": 0,
            },
        ]

    def test_calcula_todos_os_mercados_inclusive_zeros(self):
        esperados = {
            "pontos": 10,
            "assistencias": 5,
            "rebotes": 7,
            "cestas_3": 2,
            "tentativas_3": 6,
            "pa": 15,
            "ar": 12,
            "par": 22,
        }

        self.assertEqual(tuple(esperados), MERCADOS_PERMITIDOS)
        for mercado, esperado in esperados.items():
            with self.subTest(mercado=mercado):
                self.assertEqual(
                    int(valor_mercado(self.partidas[0], mercado)), esperado
                )
        self.assertEqual(valor_mercado(self.partidas[1], "cestas_3"), 0)
        self.assertEqual(valor_mercado(self.partidas[1], "tentativas_3"), 0)

    def test_over_under_e_push(self):
        over = calcular_analise(self.partidas, "pontos", "todos", 10, "over")
        under = calcular_analise(self.partidas, "pontos", "todos", 10, "under")

        self.assertEqual(over["media"], 9)
        self.assertEqual(over["mediana"], 9)
        self.assertEqual(over["maior_valor"], 10)
        self.assertEqual(over["menor_valor"], 8)
        self.assertEqual((over["acertos"], over["erros"], over["pushes"]), (0, 1, 1))
        self.assertEqual(over["percentual_acerto"], 0)
        self.assertEqual((under["acertos"], under["erros"], under["pushes"]), (1, 0, 1))
        self.assertEqual(under["percentual_acerto"], 100)

    def test_percentual_sem_divisao_por_zero(self):
        partidas = [
            {"game_id": "1", "pontos": 10},
            {"game_id": "2", "pontos": 10},
        ]

        resultado = calcular_analise(partidas, "pontos", "todos", 10, "over")

        self.assertEqual(resultado["pushes"], 2)
        self.assertEqual(resultado["percentual_acerto"], 0)

    def test_dado_ausente_e_ignorado_sem_virar_zero(self):
        partidas = [
            {"game_id": "2", "pontos": 12, "assistencias": None},
            {"game_id": "1", "pontos": 10, "assistencias": 5},
        ]

        resultado = calcular_analise(partidas, "pa", "todos", 14.5, "over")

        self.assertEqual(resultado["jogos_considerados"], 1)
        self.assertEqual(resultado["jogos_sem_dado"], 1)
        self.assertEqual(resultado["partidas"][0]["valor"], 15)

    def test_quantidades_permitidas_limitam_os_jogos_mais_recentes(self):
        partidas = [{"game_id": str(i), "pontos": i} for i in range(20, 0, -1)]
        for quantidade in (5, 10, 15, 20, "todos"):
            with self.subTest(quantidade=quantidade):
                normalizada = normalizar_quantidade(quantidade)
                resultado = calcular_analise(
                    partidas, "pontos", normalizada, 0, "over"
                )
                esperado = 20 if quantidade == "todos" else quantidade
                self.assertEqual(resultado["jogos_considerados"], esperado)


if __name__ == "__main__":
    unittest.main()
