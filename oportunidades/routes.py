from decimal import Decimal

from flask import Blueprint, jsonify, request

from config import NBA_SYNC_SEASONS
from database import conectar
from middlewares.auth import login_required
from services.analises import (
    LADOS_PERMITIDOS,
    MERCADOS_PERMITIDOS,
    QUANTIDADES_PERMITIDAS,
    normalizar_quantidade,
    validar_decimal,
)
from services.oportunidades import calcular_ranking


oportunidades_bp = Blueprint("oportunidades", __name__, url_prefix="/oportunidades")
TIPOS_PERMITIDOS = ("Todos", "Regular Season", "Playoffs")


def _erro_validacao(mensagem, **detalhes):
    return jsonify({"erro": mensagem, **detalhes}), 422


def _inteiro(valor, campo, minimo, maximo=None):
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        raise ValueError(f"{campo} invalido") from None
    if isinstance(valor, str) and str(numero) != valor.strip():
        raise ValueError(f"{campo} invalido")
    if numero < minimo or (maximo is not None and numero > maximo):
        raise ValueError(f"{campo} invalido")
    return numero


def _validar_filtros(args):
    temporada = args.get("temporada")
    if temporada not in NBA_SYNC_SEASONS:
        raise ValueError("temporada invalida")

    tipo = args.get("tipo_temporada", "Todos")
    if tipo not in TIPOS_PERMITIDOS:
        raise ValueError("tipo de temporada invalido")

    mercado = args.get("mercado")
    if mercado not in MERCADOS_PERMITIDOS:
        raise ValueError("mercado invalido")

    quantidade = normalizar_quantidade(args.get("quantidade_jogos"))
    linha = validar_decimal(args.get("linha"), "linha", Decimal("0"))
    odd = validar_decimal(args.get("odd"), "odd", Decimal("0"))
    if odd <= 1:
        raise ValueError("odd invalida")

    lado = args.get("lado")
    lado = lado.strip().lower() if isinstance(lado, str) else lado
    if lado not in LADOS_PERMITIDOS:
        raise ValueError("lado invalido")

    minimo_jogos = _inteiro(args.get("minimo_jogos", "5"), "minimo de jogos", 1)
    if quantidade != "todos" and minimo_jogos > int(quantidade):
        raise ValueError("minimo de jogos invalido")
    limite = _inteiro(args.get("limite", "20"), "limite", 1, 100)

    return {
        "temporada": temporada,
        "tipo_temporada": tipo,
        "mercado": mercado,
        "linha": linha,
        "odd": odd,
        "lado": lado,
        "quantidade_jogos": quantidade,
        "minimo_jogos": minimo_jogos,
        "limite": limite,
    }


def _buscar_partidas(config):
    limite_por_jogador = (
        None
        if config["quantidade_jogos"] == "todos"
        else int(config["quantidade_jogos"])
    )
    parametros = [config["temporada"]]
    filtro_tipo = ""
    if config["tipo_temporada"] != "Todos":
        filtro_tipo = " AND j.tipo_temporada = %s"
        parametros.append(config["tipo_temporada"])

    filtro_limite = ""
    if limite_por_jogador is not None:
        filtro_limite = "WHERE ordem_recente <= %s"
        parametros.append(limite_por_jogador)

    consulta = f"""WITH partidas_ordenadas AS (
        SELECT e.nba_player_id, e.nome_jogador, j.game_id, j.data_partida,
               e.pontos, e.assistencias, e.rebotes, e.cestas_3, e.tentativas_3,
               ROW_NUMBER() OVER (
                   PARTITION BY e.nba_player_id
                   ORDER BY j.data_partida DESC, j.game_id DESC
               ) AS ordem_recente
        FROM estatisticas_jogador e
        JOIN jogos j ON j.game_id = e.game_id
        WHERE j.temporada = %s{filtro_tipo}
    )
    SELECT nba_player_id, nome_jogador, game_id, data_partida, pontos,
           assistencias, rebotes, cestas_3, tentativas_3
    FROM partidas_ordenadas
    {filtro_limite}
    ORDER BY nba_player_id, ordem_recente"""

    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute(consulta, parametros)
            linhas = cur.fetchall()
    finally:
        conn.close()

    jogadores = []
    por_id = {}
    for linha in linhas:
        nba_player_id = int(linha[0])
        jogador = por_id.get(nba_player_id)
        if jogador is None:
            jogador = {
                "nba_player_id": nba_player_id,
                "nome": linha[1],
                "ativo": None,
                "partidas": [],
            }
            por_id[nba_player_id] = jogador
            jogadores.append(jogador)
        jogador["partidas"].append({
            "game_id": linha[2],
            "data": linha[3],
            "pontos": linha[4],
            "assistencias": linha[5],
            "rebotes": linha[6],
            "cestas_3": linha[7],
            "tentativas_3": linha[8],
        })
    return jogadores


@oportunidades_bp.get("/ev")
@login_required
def listar_ev_positivo():
    try:
        config = _validar_filtros(request.args)
    except ValueError as erro:
        mensagem = str(erro)
        detalhes = {}
        if mensagem == "mercado invalido":
            detalhes["mercados_permitidos"] = list(MERCADOS_PERMITIDOS)
        elif mensagem == "temporada invalida":
            detalhes["temporadas_permitidas"] = list(NBA_SYNC_SEASONS)
        elif mensagem == "quantidade de jogos invalida":
            detalhes["quantidades_permitidas"] = [
                int(item) if item.isdigit() else item
                for item in QUANTIDADES_PERMITIDAS
            ]
        return _erro_validacao(mensagem, **detalhes)

    try:
        jogadores = _buscar_partidas(config)
    except Exception:
        return jsonify({"erro": "nao foi possivel consultar as oportunidades"}), 500

    if not jogadores:
        return jsonify({
            "erro": "temporada ainda nao sincronizada",
            "temporada": config["temporada"],
        }), 404

    ranking = calcular_ranking(
        jogadores,
        config["mercado"],
        config["linha"],
        config["odd"],
        config["lado"],
        config["minimo_jogos"],
        config["limite"],
    )
    filtros = {
        **config,
        "linha": float(config["linha"]),
        "odd": float(config["odd"]),
        "quantidade_jogos": (
            int(config["quantidade_jogos"])
            if config["quantidade_jogos"].isdigit()
            else config["quantidade_jogos"]
        ),
    }
    return jsonify({
        "filtros": filtros,
        "total_jogadores_avaliados": len(jogadores),
        **ranking,
    }), 200
