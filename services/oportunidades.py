from decimal import Decimal, ROUND_HALF_UP

from services.analises import numero_json, valor_mercado


def _arredondar(valor, casas):
    passo = Decimal("1").scaleb(-casas)
    return numero_json(valor.quantize(passo, rounding=ROUND_HALF_UP))


def _mediana(valores):
    ordenados = sorted(valores)
    meio = len(ordenados) // 2
    if len(ordenados) % 2:
        return ordenados[meio]
    return (ordenados[meio - 1] + ordenados[meio]) / Decimal("2")


def calcular_ranking(jogadores, mercado, linha, odd, lado, minimo_jogos, limite):
    """Calcula o ranking sem arredondar antes da filtragem e ordenacao."""
    probabilidade_implicita = Decimal("1") / odd
    oportunidades = []
    total_elegiveis = 0

    for jogador in jogadores:
        partidas = jogador["partidas"]
        valores = []
        acertos = erros = pushes = 0
        ultima_partida = None

        for partida in partidas:
            valor = valor_mercado(partida, mercado)
            if valor is None:
                continue
            valores.append(valor)
            if ultima_partida is None:
                ultima_partida = partida.get("data")
            if valor == linha:
                pushes += 1
            elif (lado == "over" and valor > linha) or (
                lado == "under" and valor < linha
            ):
                acertos += 1
            else:
                erros += 1

        jogos_validos = len(valores)
        decisoes = acertos + erros
        if jogos_validos < minimo_jogos or decisoes == 0:
            continue

        total_elegiveis += 1
        probabilidade_historica = Decimal(acertos) / Decimal(decisoes)
        edge = probabilidade_historica - probabilidade_implicita
        ev = probabilidade_historica * odd - Decimal("1")
        if ev <= 0:
            continue

        oportunidades.append({
            "_probabilidade_historica": probabilidade_historica,
            "_ev": ev,
            "_decisoes": decisoes,
            "jogador": {
                "id": f"nba:{jogador['nba_player_id']}",
                "nba_player_id": jogador["nba_player_id"],
                "nome": jogador["nome"],
                "ativo": jogador.get("ativo"),
            },
            "jogos_selecionados": len(partidas),
            "jogos_validos": jogos_validos,
            "jogos_sem_dado": len(partidas) - jogos_validos,
            "acertos": acertos,
            "erros": erros,
            "pushes": pushes,
            "probabilidade_historica": _arredondar(probabilidade_historica, 6),
            "percentual_acerto": _arredondar(
                probabilidade_historica * Decimal("100"), 2
            ),
            "probabilidade_implicita": _arredondar(probabilidade_implicita, 6),
            "percentual_implicito": _arredondar(
                probabilidade_implicita * Decimal("100"), 2
            ),
            "edge": _arredondar(edge, 6),
            "edge_percentual": _arredondar(edge * Decimal("100"), 2),
            "ev": _arredondar(ev, 6),
            "ev_percentual": _arredondar(ev * Decimal("100"), 2),
            "media": _arredondar(sum(valores, Decimal("0")) / jogos_validos, 2),
            "mediana": _arredondar(_mediana(valores), 2),
            "maior_valor": numero_json(max(valores)),
            "menor_valor": numero_json(min(valores)),
            "ultimo_valor": numero_json(valores[0]),
            "valores_recentes": [numero_json(valor) for valor in valores],
            "ultima_partida": (
                ultima_partida.isoformat()
                if hasattr(ultima_partida, "isoformat")
                else ultima_partida
            ),
        })

    oportunidades.sort(
        key=lambda item: (
            -item["_ev"],
            -item["_probabilidade_historica"],
            -item["_decisoes"],
            item["jogador"]["nome"].casefold(),
            item["jogador"]["nba_player_id"],
        )
    )
    total_ev_positivo = len(oportunidades)
    oportunidades = oportunidades[:limite]
    for posicao, item in enumerate(oportunidades, start=1):
        item["posicao"] = posicao
        item.pop("_probabilidade_historica")
        item.pop("_ev")
        item.pop("_decisoes")

    return {
        "total_elegiveis": total_elegiveis,
        "total_ev_positivo": total_ev_positivo,
        "oportunidades": oportunidades,
    }
