from decimal import Decimal, InvalidOperation


MERCADOS_COMPONENTES = {
    "pontos": ("pontos",),
    "assistencias": ("assistencias",),
    "rebotes": ("rebotes",),
    "cestas_3": ("cestas_3",),
    "tentativas_3": ("tentativas_3",),
    "pa": ("pontos", "assistencias"),
    "ar": ("assistencias", "rebotes"),
    "par": ("pontos", "assistencias", "rebotes"),
}
MERCADOS_PERMITIDOS = tuple(MERCADOS_COMPONENTES)
QUANTIDADES_PERMITIDAS = ("5", "10", "15", "20", "todos")
LADOS_PERMITIDOS = ("over", "under")


def _decimal(valor):
    if valor is None or isinstance(valor, bool):
        return None
    try:
        numero = Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return numero if numero.is_finite() else None


def numero_json(valor):
    if isinstance(valor, Decimal):
        return int(valor) if valor == valor.to_integral() else float(valor)
    return valor


def valor_mercado(partida, mercado):
    componentes = MERCADOS_COMPONENTES.get(mercado)
    if componentes is None:
        raise ValueError("mercado invalido")

    valores = [_decimal(partida.get(campo)) for campo in componentes]
    if any(valor is None for valor in valores):
        return None
    return sum(valores, Decimal("0"))


def adicionar_compostos(partida):
    partida_completa = dict(partida)
    for mercado in ("pa", "ar", "par"):
        valor = valor_mercado(partida_completa, mercado)
        if valor is not None:
            partida_completa[mercado] = numero_json(valor)
    return partida_completa


def medias_por_mercado(partidas):
    medias = {}
    for mercado in MERCADOS_PERMITIDOS:
        valores = [
            valor
            for partida in partidas
            if (valor := valor_mercado(partida, mercado)) is not None
        ]
        if valores:
            medias[mercado] = numero_json(sum(valores) / len(valores))
    return medias


def normalizar_quantidade(valor):
    if isinstance(valor, int) and not isinstance(valor, bool):
        valor = str(valor)
    if isinstance(valor, str):
        valor = valor.strip().lower()
    if valor not in QUANTIDADES_PERMITIDAS:
        raise ValueError("quantidade de jogos invalida")
    return valor


def validar_decimal(valor, campo, minimo):
    numero = _decimal(valor)
    if numero is None or numero < minimo:
        raise ValueError(f"{campo} invalida")
    return numero


def calcular_analise(partidas, mercado, quantidade, linha, lado):
    if mercado not in MERCADOS_PERMITIDOS:
        raise ValueError("mercado invalido")
    quantidade = normalizar_quantidade(quantidade)
    lado = lado.strip().lower() if isinstance(lado, str) else lado
    if lado not in LADOS_PERMITIDOS:
        raise ValueError("lado invalido")

    linha = validar_decimal(linha, "linha", Decimal("0"))
    limite = None if quantidade == "todos" else int(quantidade)
    partidas_selecionadas = partidas[:limite]
    resultados = []

    for partida in partidas_selecionadas:
        valor = valor_mercado(partida, mercado)
        if valor is None:
            continue
        if valor == linha:
            situacao = "push"
        else:
            acertou = valor > linha if lado == "over" else valor < linha
            situacao = "acerto" if acertou else "erro"
        resultados.append({
            "game_id": partida.get("game_id"),
            "data": (
                partida["data"].isoformat()
                if hasattr(partida.get("data"), "isoformat")
                else partida.get("data")
            ),
            "adversario": partida.get("adversario"),
            "valor": numero_json(valor),
            "resultado": situacao,
        })

    if not resultados:
        raise ValueError("nenhum jogo possui dados validos para esse mercado")

    valores = [Decimal(str(item["valor"])) for item in resultados]
    valores_ordenados = sorted(valores)
    meio = len(valores_ordenados) // 2
    if len(valores_ordenados) % 2:
        mediana = valores_ordenados[meio]
    else:
        mediana = (valores_ordenados[meio - 1] + valores_ordenados[meio]) / 2

    acertos = sum(item["resultado"] == "acerto" for item in resultados)
    erros = sum(item["resultado"] == "erro" for item in resultados)
    pushes = sum(item["resultado"] == "push" for item in resultados)
    decisoes = acertos + erros
    percentual = Decimal("0") if not decisoes else Decimal(acertos * 100) / decisoes

    return {
        "jogos_considerados": len(resultados),
        "jogos_sem_dado": len(partidas_selecionadas) - len(resultados),
        "media": numero_json(sum(valores) / len(valores)),
        "mediana": numero_json(mediana),
        "maior_valor": numero_json(max(valores)),
        "menor_valor": numero_json(min(valores)),
        "acertos": acertos,
        "erros": erros,
        "pushes": pushes,
        "percentual_acerto": numero_json(percentual.quantize(Decimal("0.01"))),
        "sequencia_recente": [item["resultado"] for item in resultados],
        "partidas": resultados,
    }
