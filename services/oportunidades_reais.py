from decimal import Decimal, ROUND_HALF_UP

from services.analises import numero_json, valor_mercado
from services.oportunidades import calcular_percentil


def _arredondar(valor, casas):
    passo = Decimal("1").scaleb(-casas)
    arredondado = valor.quantize(passo, rounding=ROUND_HALF_UP)
    return numero_json(arredondado)


def calcular_oportunidade_real(
    cotacao,
    partidas,
    minimo_jogos,
    linhas_plausiveis,
    percentil_inferior,
    percentil_superior,
    edge_minimo_percentual,
    edge_maximo_percentual,
):
    valores = []
    acertos = erros = pushes = 0
    linha = cotacao["linha"]
    odd = cotacao["odd"]
    lado = cotacao["lado"]
    for partida in partidas:
        valor = valor_mercado(partida, cotacao["mercado"])
        if valor is None:
            continue
        valores.append(valor)
        if valor == linha:
            pushes += 1
        elif (lado == "over" and valor > linha) or (
            lado == "under" and valor < linha
        ):
            acertos += 1
        else:
            erros += 1

    if len(valores) < minimo_jogos or acertos + erros == 0:
        return None

    probabilidade_historica = Decimal(acertos) / Decimal(acertos + erros)
    probabilidade_implicita = Decimal("1") / odd
    edge = probabilidade_historica - probabilidade_implicita
    edge_percentual = edge * Decimal("100")
    ev = probabilidade_historica * odd - Decimal("1")
    if ev <= 0:
        return None

    valor_inferior = calcular_percentil(valores, percentil_inferior)
    valor_superior = calcular_percentil(valores, percentil_superior)
    linha_dentro = valor_inferior <= linha <= valor_superior
    edge_dentro = edge_minimo_percentual <= edge_percentual <= edge_maximo_percentual
    if linhas_plausiveis and (not linha_dentro or not edge_dentro):
        return None

    return {
        "_ev": ev,
        "_edge": edge,
        "_decisoes": acertos + erros,
        "jogador_id": cotacao["jogador_id"],
        "jogador_nome": cotacao["jogador_nome"],
        "evento": {
            "id": cotacao["evento_id"],
            "provedor_fixture_id": cotacao["provedor_fixture_id"],
            "inicio_em": cotacao["inicio_em"],
            "time_casa": cotacao["time_casa"],
            "time_fora": cotacao["time_fora"],
        },
        "bookmaker": cotacao["bookmaker"],
        "mercado": cotacao["mercado"],
        "linha": numero_json(linha),
        "lado": lado,
        "odd": numero_json(odd),
        "probabilidade_historica": _arredondar(probabilidade_historica, 6),
        "probabilidade_implicita": _arredondar(probabilidade_implicita, 6),
        "edge": _arredondar(edge, 6),
        "edge_percentual": _arredondar(edge_percentual, 2),
        "ev": _arredondar(ev, 6),
        "ev_percentual": _arredondar(ev * Decimal("100"), 2),
        "acertos": acertos,
        "erros": erros,
        "pushes": pushes,
        "quantidade_jogos": len(valores),
        "jogos_sem_dado": len(partidas) - len(valores),
        "faixa_percentil": {
            "percentil_inferior": numero_json(percentil_inferior),
            "valor_inferior": _arredondar(valor_inferior, 2),
            "percentil_superior": numero_json(percentil_superior),
            "valor_superior": _arredondar(valor_superior, 2),
        },
        "linha_dentro_faixa": linha_dentro,
        "edge_dentro_faixa": edge_dentro,
        "odd_capturada_em": cotacao["capturada_em"],
    }


def ordenar_oportunidades_reais(oportunidades, limite):
    oportunidades.sort(
        key=lambda item: (
            -item["_ev"],
            -item["_edge"],
            -item["_decisoes"],
            item["jogador_nome"].casefold(),
            item["jogador_id"],
        )
    )
    oportunidades = oportunidades[:limite]
    for item in oportunidades:
        item.pop("_ev")
        item.pop("_edge")
        item.pop("_decisoes")
    return oportunidades
