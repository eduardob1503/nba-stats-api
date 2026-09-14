import unittest
from decimal import Decimal

from services.oportunidades import calcular_percentil, calcular_ranking


def _jogador(player_id, nome, partidas):
    return {
        "nba_player_id": player_id,
        "nome": nome,
        "ativo": None,
        "partidas": partidas,
    }


class OportunidadesServiceTest(unittest.TestCase):
    def test_percentil_r7_com_indice_inteiro_e_interpolacao(self):
        self.assertEqual(
            calcular_percentil([0, 10, 20, 30], Decimal("25")),
            Decimal("7.5"),
        )
        self.assertEqual(
            calcular_percentil([0, 10, 20, 30, 40], Decimal("25")),
            Decimal("10"),
        )

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

    def test_linha_nos_limites_percentis_e_inclusiva(self):
        partidas = [{"pontos": valor} for valor in (10, 20, 30, 40, 50)]
        for linha, lado in ((Decimal("20"), "over"), (Decimal("40"), "under")):
            with self.subTest(linha=linha):
                resultado = calcular_ranking(
                    [_jogador(1, "Jogador", partidas)],
                    "pontos",
                    linha,
                    Decimal("1.5"),
                    lado,
                    5,
                    20,
                    True,
                    Decimal("25"),
                    Decimal("75"),
                    Decimal("0"),
                    Decimal("100"),
                )
                self.assertEqual(resultado["total_ev_positivo"], 1)
                self.assertTrue(resultado["oportunidades"][0]["linha_dentro_faixa"])

    def test_linha_abaixo_ou_acima_da_faixa_e_excluida(self):
        partidas = [{"pontos": valor} for valor in (10, 20, 30, 40, 50)]
        casos = ((Decimal("19"), "over"), (Decimal("41"), "under"))
        for linha, lado in casos:
            with self.subTest(linha=linha):
                resultado = calcular_ranking(
                    [_jogador(1, "Jogador", partidas)],
                    "pontos",
                    linha,
                    Decimal("2"),
                    lado,
                    5,
                    20,
                    True,
                    Decimal("25"),
                    Decimal("75"),
                    Decimal("0"),
                    Decimal("100"),
                )
                self.assertEqual(resultado["oportunidades"], [])
                self.assertEqual(resultado["exclusoes"]["linha_fora_percentis"], 1)

    def test_edge_nos_limites_e_inclusivo_e_fora_deles_e_excluido(self):
        partidas = [{"pontos": valor} for valor in (11, 11, 11, 9, 9)]
        base = (
            [_jogador(1, "Jogador", partidas)],
            "pontos",
            Decimal("10"),
            Decimal("2"),
            "over",
            5,
            20,
            True,
            Decimal("25"),
            Decimal("75"),
        )
        no_minimo = calcular_ranking(*base, Decimal("10"), Decimal("20"))
        no_maximo = calcular_ranking(*base, Decimal("0"), Decimal("10"))
        abaixo = calcular_ranking(*base, Decimal("10.01"), Decimal("20"))
        acima = calcular_ranking(*base, Decimal("0"), Decimal("9.99"))

        self.assertEqual(no_minimo["total_ev_positivo"], 1)
        self.assertEqual(no_maximo["total_ev_positivo"], 1)
        self.assertEqual(abaixo["exclusoes"]["edge_abaixo_minimo"], 1)
        self.assertEqual(acima["exclusoes"]["edge_acima_maximo"], 1)

    def test_dez_de_dez_pode_ser_excluido_pelo_edge_maximo(self):
        partidas = [{"pontos": 10}] * 10 + [{"pontos": 11}] * 10
        resultado = calcular_ranking(
            [_jogador(1, "Perfeito", partidas)],
            "pontos",
            Decimal("10"),
            Decimal("2"),
            "over",
            10,
            20,
            True,
            Decimal("25"),
            Decimal("75"),
            Decimal("3"),
            Decimal("20"),
        )

        self.assertEqual(resultado["oportunidades"], [])
        self.assertEqual(resultado["exclusoes"]["edge_acima_maximo"], 1)

    def test_nao_exige_erros_e_pushes_entram_apenas_nos_percentis(self):
        partidas = [{"pontos": 10}] * 4 + [{"pontos": 11}]
        resultado = calcular_ranking(
            [_jogador(1, "Sem erros", partidas)],
            "pontos",
            Decimal("10"),
            Decimal("1.1"),
            "over",
            5,
            20,
            True,
            Decimal("25"),
            Decimal("75"),
            Decimal("3"),
            Decimal("20"),
        )
        item = resultado["oportunidades"][0]

        self.assertEqual((item["acertos"], item["erros"], item["pushes"]), (1, 0, 4))
        self.assertEqual(item["probabilidade_historica"], 1)
        self.assertEqual(item["faixa_percentil"]["valor_inferior"], 10)
        self.assertEqual(item["faixa_percentil"]["valor_superior"], 10)

    def test_mercado_composto_define_percentis_com_valores_validos(self):
        partidas = [
            {"pontos": 10, "assistencias": 5},
            {"pontos": 20, "assistencias": 5},
            {"pontos": 30, "assistencias": 5},
            {"pontos": 40, "assistencias": None},
        ]
        resultado = calcular_ranking(
            [_jogador(1, "Composto", partidas)],
            "pa",
            Decimal("20"),
            Decimal("2"),
            "over",
            3,
            20,
        )
        item = resultado["oportunidades"][0]

        self.assertEqual(item["jogos_sem_dado"], 1)
        self.assertEqual(item["faixa_percentil"]["valor_inferior"], 20)
        self.assertEqual(item["faixa_percentil"]["valor_superior"], 30)

    def test_exclusoes_sao_mutuamente_exclusivas_e_reconciliaveis(self):
        def partidas(acertos, erros, pushes=0):
            return (
                [{"pontos": 11}] * acertos
                + [{"pontos": 9}] * erros
                + [{"pontos": 10}] * pushes
            )

        jogadores = [
            _jogador(1, "Insuficiente", partidas(1, 0)),
            _jogador(2, "Sem decisoes", partidas(0, 0, 2)),
            _jogador(3, "EV zero", partidas(1, 1)),
            _jogador(4, "Linha fora", partidas(3, 0)),
            _jogador(5, "Edge abaixo", partidas(3, 2)),
            _jogador(6, "Edge acima", partidas(4, 1, 3)),
            _jogador(7, "Aprovado", partidas(7, 3)),
        ]
        resultado = calcular_ranking(
            jogadores,
            "pontos",
            Decimal("10"),
            Decimal("2"),
            "over",
            2,
            20,
            True,
            Decimal("25"),
            Decimal("75"),
            Decimal("15"),
            Decimal("25"),
        )

        self.assertEqual(resultado["exclusoes"], {
            "jogos_insuficientes": 1,
            "sem_decisoes": 1,
            "ev_nao_positivo": 1,
            "linha_fora_percentis": 1,
            "edge_abaixo_minimo": 1,
            "edge_acima_maximo": 1,
        })
        self.assertEqual(resultado["total_elegiveis"], 5)
        self.assertEqual(resultado["total_ev_positivo_bruto"], 4)
        self.assertEqual(resultado["total_linhas_plausiveis"], 1)
        self.assertEqual(resultado["total_ev_positivo"], 1)
        self.assertEqual(resultado["total_retornado"], 1)
        self.assertEqual(sum(resultado["exclusoes"].values()) + 1, len(jogadores))

    def test_modo_desativado_preserva_ev_bruto_e_ignora_filtros_avancados(self):
        jogadores = [
            _jogador(1, "Linha fora", [{"pontos": 30}, {"pontos": 31}]),
            _jogador(2, "Edge alto", [{"pontos": 9}, {"pontos": 11}, {"pontos": 11}]),
        ]
        legado = calcular_ranking(
            jogadores, "pontos", Decimal("10"), Decimal("2"), "over", 2, 20
        )
        desligado = calcular_ranking(
            jogadores,
            "pontos",
            Decimal("10"),
            Decimal("2"),
            "over",
            2,
            20,
            False,
            Decimal("35"),
            Decimal("65"),
            Decimal("19"),
            Decimal("20"),
        )

        self.assertEqual(
            [item["jogador"]["id"] for item in legado["oportunidades"]],
            [item["jogador"]["id"] for item in desligado["oportunidades"]],
        )
        self.assertEqual(desligado["total_ev_positivo"], desligado["total_ev_positivo_bruto"])
        self.assertEqual(desligado["total_linhas_plausiveis"], desligado["total_ev_positivo"])
        self.assertEqual(desligado["exclusoes"]["linha_fora_percentis"], 0)
        self.assertEqual(desligado["exclusoes"]["edge_abaixo_minimo"], 0)
        self.assertEqual(desligado["exclusoes"]["edge_acima_maximo"], 0)

    def test_filtros_antecedem_ordenacao_e_limite(self):
        jogadores = [
            _jogador(1, "EV maior irreal", [{"pontos": 30}] * 5),
            _jogador(2, "Segundo", [{"pontos": 11}] * 7 + [{"pontos": 9}] * 3),
            _jogador(3, "Primeiro", [{"pontos": 11}] * 3 + [{"pontos": 9}] * 2),
        ]
        resultado = calcular_ranking(
            jogadores,
            "pontos",
            Decimal("10"),
            Decimal("2"),
            "over",
            5,
            1,
            True,
            Decimal("25"),
            Decimal("75"),
            Decimal("10"),
            Decimal("25"),
        )

        self.assertEqual(resultado["total_linhas_plausiveis"], 2)
        self.assertEqual(resultado["total_retornado"], 1)
        self.assertEqual(resultado["oportunidades"][0]["jogador"]["nome"], "Segundo")


if __name__ == "__main__":
    unittest.main()
