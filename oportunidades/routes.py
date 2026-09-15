from decimal import Decimal

from flask import Blueprint, jsonify, request

from config import (
    NBA_SYNC_SEASONS,
    ODDSPAPI_BOOKMAKERS,
    ODDSPAPI_ODDS_MAX_AGE_MINUTES,
)
from database import conectar
from middlewares.auth import login_required
from services.analises import (
    LADOS_PERMITIDOS,
    MERCADOS_PERMITIDOS,
    QUANTIDADES_PERMITIDAS,
    normalizar_quantidade,
    numero_json,
    validar_decimal,
)
from services.oportunidades import calcular_ranking
from services.oportunidades_reais import (
    calcular_oportunidade_real,
    ordenar_oportunidades_reais,
)


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


def _booleano(valor, campo):
    if valor == "true":
        return True
    if valor == "false":
        return False
    raise ValueError(f"{campo} invalido")


def _decimal_avancado(valor, campo):
    try:
        return validar_decimal(valor, campo, Decimal("0"))
    except ValueError:
        raise ValueError(f"{campo} invalido") from None


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

    linhas_plausiveis = _booleano(
        args.get("linhas_plausiveis", "false"), "linhas plausiveis"
    )
    percentil_inferior = _decimal_avancado(
        args.get("percentil_inferior", "25"),
        "percentil inferior",
    )
    percentil_superior = _decimal_avancado(
        args.get("percentil_superior", "75"),
        "percentil superior",
    )
    if percentil_inferior >= percentil_superior:
        raise ValueError("faixa de percentis invalida")
    if percentil_inferior > 50:
        raise ValueError("percentil inferior invalido")
    if percentil_superior < 50 or percentil_superior > 100:
        raise ValueError("percentil superior invalido")

    edge_minimo = _decimal_avancado(
        args.get("edge_minimo_percentual", "3"),
        "edge minimo",
    )
    edge_maximo = _decimal_avancado(
        args.get("edge_maximo_percentual", "20"),
        "edge maximo",
    )
    if edge_minimo >= edge_maximo:
        raise ValueError("faixa de edge invalida")
    if edge_maximo > 100:
        raise ValueError("edge maximo invalido")

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
        "linhas_plausiveis": linhas_plausiveis,
        "percentil_inferior": percentil_inferior,
        "percentil_superior": percentil_superior,
        "edge_minimo_percentual": edge_minimo,
        "edge_maximo_percentual": edge_maximo,
    }


def _validar_filtros_reais(args):
    temporada = args.get("temporada")
    if temporada not in NBA_SYNC_SEASONS:
        raise ValueError("temporada invalida")
    tipo = args.get("tipo_temporada", "Todos")
    if tipo not in TIPOS_PERMITIDOS:
        raise ValueError("tipo de temporada invalido")
    mercado = args.get("mercado")
    if mercado and mercado not in MERCADOS_PERMITIDOS:
        raise ValueError("mercado invalido")
    if mercado == "tentativas_3":
        raise ValueError("mercado sem prop real")
    lado = args.get("lado")
    if lado and lado not in LADOS_PERMITIDOS:
        raise ValueError("lado invalido")
    quantidade = normalizar_quantidade(args.get("quantidade_jogos"))
    minimo_jogos = _inteiro(args.get("minimo_jogos", "5"), "minimo de jogos", 1)
    if quantidade != "todos" and minimo_jogos > int(quantidade):
        raise ValueError("minimo de jogos invalido")
    limite = _inteiro(args.get("limite", "20"), "limite", 1, 100)
    linhas_plausiveis = _booleano(
        args.get("linhas_plausiveis", "false"), "linhas plausiveis"
    )
    percentil_inferior = _decimal_avancado(
        args.get("percentil_inferior", "25"), "percentil inferior"
    )
    percentil_superior = _decimal_avancado(
        args.get("percentil_superior", "75"), "percentil superior"
    )
    if percentil_inferior >= percentil_superior:
        raise ValueError("faixa de percentis invalida")
    if percentil_inferior > 50:
        raise ValueError("percentil inferior invalido")
    if percentil_superior < 50 or percentil_superior > 100:
        raise ValueError("percentil superior invalido")
    edge_minimo = _decimal_avancado(
        args.get("edge_minimo_percentual", "3"), "edge minimo"
    )
    edge_maximo = _decimal_avancado(
        args.get("edge_maximo_percentual", "20"), "edge maximo"
    )
    if edge_minimo >= edge_maximo:
        raise ValueError("faixa de edge invalida")
    if edge_maximo > 100:
        raise ValueError("edge maximo invalido")
    bookmaker = (args.get("bookmaker") or (
        ODDSPAPI_BOOKMAKERS[0] if ODDSPAPI_BOOKMAKERS else "betano"
    )).strip().lower()
    if not bookmaker:
        raise ValueError("bookmaker invalido")
    return {
        "temporada": temporada,
        "tipo_temporada": tipo,
        "mercado": mercado,
        "lado": lado,
        "quantidade_jogos": quantidade,
        "minimo_jogos": minimo_jogos,
        "limite": limite,
        "linhas_plausiveis": linhas_plausiveis,
        "percentil_inferior": percentil_inferior,
        "percentil_superior": percentil_superior,
        "edge_minimo_percentual": edge_minimo,
        "edge_maximo_percentual": edge_maximo,
        "bookmaker": bookmaker,
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
        linhas_plausiveis=config["linhas_plausiveis"],
        percentil_inferior=config["percentil_inferior"],
        percentil_superior=config["percentil_superior"],
        edge_minimo_percentual=config["edge_minimo_percentual"],
        edge_maximo_percentual=config["edge_maximo_percentual"],
    )
    filtros = {
        **config,
        "linha": numero_json(config["linha"]),
        "odd": numero_json(config["odd"]),
        "percentil_inferior": numero_json(config["percentil_inferior"]),
        "percentil_superior": numero_json(config["percentil_superior"]),
        "edge_minimo_percentual": numero_json(config["edge_minimo_percentual"]),
        "edge_maximo_percentual": numero_json(config["edge_maximo_percentual"]),
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


def _data_json(valor):
    if valor is None:
        return None
    if hasattr(valor, "isoformat"):
        return valor.isoformat().replace("+00:00", "Z")
    return valor


def _buscar_dados_ev_reais(config):
    filtros = [
        "c.ativa = TRUE",
        "c.jogador_id IS NOT NULL",
        "c.lado IN ('over', 'under')",
        "c.bookmaker = %s",
        "c.capturada_em >= NOW() - (%s * INTERVAL '1 minute')",
        "e.inicio_em > NOW()",
    ]
    parametros = [config["bookmaker"], ODDSPAPI_ODDS_MAX_AGE_MINUTES]
    if config["mercado"]:
        filtros.append("c.mercado = %s")
        parametros.append(config["mercado"])
    if config["lado"]:
        filtros.append("c.lado = %s")
        parametros.append(config["lado"])

    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""SELECT c.id, c.evento_id, e.provedor_fixture_id, e.inicio_em,
                           e.time_casa, e.time_fora, c.jogador_id,
                           c.jogador_nome_provedor, c.mercado, c.linha, c.lado,
                           c.odd, c.bookmaker, c.capturada_em
                    FROM odds_cotacoes c
                    JOIN odds_eventos e ON e.id = c.evento_id
                    WHERE {' AND '.join(filtros)}""",
                parametros,
            )
            linhas_cotacoes = cur.fetchall()
            if not linhas_cotacoes:
                return [], {}

            player_ids = sorted({
                int(linha[6].removeprefix("nba:"))
                for linha in linhas_cotacoes
                if str(linha[6]).startswith("nba:")
                and str(linha[6]).removeprefix("nba:").isdigit()
            })
            if not player_ids:
                return [], {}

            limite_jogos = (
                None
                if config["quantidade_jogos"] == "todos"
                else int(config["quantidade_jogos"])
            )
            parametros_jogos = [player_ids, config["temporada"]]
            filtro_tipo = ""
            if config["tipo_temporada"] != "Todos":
                filtro_tipo = " AND j.tipo_temporada = %s"
                parametros_jogos.append(config["tipo_temporada"])
            filtro_limite = ""
            if limite_jogos is not None:
                filtro_limite = "WHERE ordem_recente <= %s"
                parametros_jogos.append(limite_jogos)
            cur.execute(
                f"""WITH historico AS (
                    SELECT e.nba_player_id, j.game_id, j.data_partida,
                           e.pontos, e.assistencias, e.rebotes,
                           e.cestas_3, e.tentativas_3,
                           ROW_NUMBER() OVER (
                               PARTITION BY e.nba_player_id
                               ORDER BY j.data_partida DESC, j.game_id DESC
                           ) AS ordem_recente
                    FROM estatisticas_jogador e
                    JOIN jogos j ON j.game_id = e.game_id
                    WHERE e.nba_player_id = ANY(%s) AND j.temporada = %s
                    {filtro_tipo}
                )
                SELECT nba_player_id, game_id, data_partida, pontos,
                       assistencias, rebotes, cestas_3, tentativas_3
                FROM historico {filtro_limite}
                ORDER BY nba_player_id, ordem_recente""",
                parametros_jogos,
            )
            linhas_jogos = cur.fetchall()
    finally:
        conn.close()

    cotacoes = [
        {
            "id": linha[0],
            "evento_id": linha[1],
            "provedor_fixture_id": linha[2],
            "inicio_em": _data_json(linha[3]),
            "time_casa": linha[4],
            "time_fora": linha[5],
            "jogador_id": linha[6],
            "jogador_nome": linha[7],
            "mercado": linha[8],
            "linha": linha[9],
            "lado": linha[10],
            "odd": linha[11],
            "bookmaker": linha[12],
            "capturada_em": _data_json(linha[13]),
        }
        for linha in linhas_cotacoes
    ]
    historico = {}
    for linha in linhas_jogos:
        historico.setdefault(int(linha[0]), []).append({
            "game_id": linha[1],
            "data": linha[2],
            "pontos": linha[3],
            "assistencias": linha[4],
            "rebotes": linha[5],
            "cestas_3": linha[6],
            "tentativas_3": linha[7],
        })
    return cotacoes, historico


@oportunidades_bp.get("/ev-reais")
@login_required
def listar_ev_reais():
    try:
        config = _validar_filtros_reais(request.args)
    except ValueError as erro:
        return _erro_validacao(str(erro))
    try:
        cotacoes, historico = _buscar_dados_ev_reais(config)
    except Exception:
        return jsonify({"erro": "nao foi possivel consultar as odds reais"}), 500
    if not cotacoes:
        return jsonify({
            "status": "sem_odds",
            "mensagem": "Ainda nao existem odds da NBA disponiveis na Betano.",
            "bookmaker": config["bookmaker"],
            "oportunidades": [],
            "total": 0,
        }), 200

    oportunidades = []
    for cotacao in cotacoes:
        nba_id = str(cotacao["jogador_id"]).removeprefix("nba:")
        partidas = historico.get(int(nba_id), []) if nba_id.isdigit() else []
        oportunidade = calcular_oportunidade_real(
            cotacao,
            partidas,
            config["minimo_jogos"],
            config["linhas_plausiveis"],
            config["percentil_inferior"],
            config["percentil_superior"],
            config["edge_minimo_percentual"],
            config["edge_maximo_percentual"],
        )
        if oportunidade:
            oportunidades.append(oportunidade)
    oportunidades = ordenar_oportunidades_reais(oportunidades, config["limite"])
    filtros = {
        **config,
        "quantidade_jogos": (
            int(config["quantidade_jogos"])
            if config["quantidade_jogos"].isdigit()
            else config["quantidade_jogos"]
        ),
        "percentil_inferior": numero_json(config["percentil_inferior"]),
        "percentil_superior": numero_json(config["percentil_superior"]),
        "edge_minimo_percentual": numero_json(config["edge_minimo_percentual"]),
        "edge_maximo_percentual": numero_json(config["edge_maximo_percentual"]),
    }
    return jsonify({
        "status": "ok",
        "filtros": filtros,
        "bookmaker": config["bookmaker"],
        "total": len(oportunidades),
        "oportunidades": oportunidades,
    }), 200
