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


def calcular_percentil(valores, percentil):
    """Calcula um percentil pelo metodo R-7/NumPy linear usando Decimal."""
    if not valores:
        raise ValueError("percentil requer ao menos um valor")
    ordenados = sorted(
        valor if isinstance(valor, Decimal) else Decimal(str(valor))
        for valor in valores
    )
    indice = Decimal(len(ordenados) - 1) * (percentil / Decimal("100"))
    indice_inferior = int(indice)
    fracao = indice - Decimal(indice_inferior)
    if fracao == 0:
        return ordenados[indice_inferior]
    inferior = ordenados[indice_inferior]
    superior = ordenados[indice_inferior + 1]
    return inferior + (superior - inferior) * fracao


def calcular_ranking(
    jogadores,
    mercado,
    linha,
    odd,
    lado,
    minimo_jogos,
    limite,
    linhas_plausiveis=False,
    percentil_inferior=Decimal("25"),
    percentil_superior=Decimal("75"),
    edge_minimo_percentual=Decimal("3"),
    edge_maximo_percentual=Decimal("20"),
):
    """Calcula o ranking sem arredondar antes da filtragem e ordenacao."""
    probabilidade_implicita = Decimal("1") / odd
    oportunidades = []
    total_elegiveis = 0
    total_ev_positivo_bruto = 0
    exclusoes = {
        "jogos_insuficientes": 0,
        "sem_decisoes": 0,
        "ev_nao_positivo": 0,
        "linha_fora_percentis": 0,
        "edge_abaixo_minimo": 0,
        "edge_acima_maximo": 0,
    }

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
        if jogos_validos < minimo_jogos:
            exclusoes["jogos_insuficientes"] += 1
            continue

        valor_percentil_inferior = calcular_percentil(valores, percentil_inferior)
        valor_percentil_superior = calcular_percentil(valores, percentil_superior)
        linha_dentro_faixa = valor_percentil_inferior <= linha <= valor_percentil_superior

        if decisoes == 0:
            exclusoes["sem_decisoes"] += 1
            continue

        total_elegiveis += 1
        probabilidade_historica = Decimal(acertos) / Decimal(decisoes)
        edge = probabilidade_historica - probabilidade_implicita
        edge_percentual = edge * Decimal("100")
        ev = probabilidade_historica * odd - Decimal("1")
        if ev <= 0:
            exclusoes["ev_nao_positivo"] += 1
            continue

        total_ev_positivo_bruto += 1
        edge_dentro_faixa = (
            edge_minimo_percentual <= edge_percentual <= edge_maximo_percentual
        )
        if linhas_plausiveis:
            if not linha_dentro_faixa:
                exclusoes["linha_fora_percentis"] += 1
                continue
            if edge_percentual < edge_minimo_percentual:
                exclusoes["edge_abaixo_minimo"] += 1
                continue
            if edge_percentual > edge_maximo_percentual:
                exclusoes["edge_acima_maximo"] += 1
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
            "edge_percentual": _arredondar(edge_percentual, 2),
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
            "faixa_percentil": {
                "percentil_inferior": numero_json(percentil_inferior),
                "valor_inferior": _arredondar(valor_percentil_inferior, 2),
                "percentil_superior": numero_json(percentil_superior),
                "valor_superior": _arredondar(valor_percentil_superior, 2),
            },
            "linha_dentro_faixa": linha_dentro_faixa,
            "edge_dentro_faixa": edge_dentro_faixa,
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
        "total_ev_positivo_bruto": total_ev_positivo_bruto,
        "total_linhas_plausiveis": total_ev_positivo,
        "total_retornado": len(oportunidades),
        "exclusoes": exclusoes,
        "oportunidades": oportunidades,
    }
