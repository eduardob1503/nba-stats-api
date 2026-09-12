from datetime import date

from flask import Blueprint, jsonify, request
from psycopg2.extras import execute_values

from config import NBA_SYNC_SEASON
from database import conectar
from middlewares.sync import sync_token_required


sync_bp = Blueprint("sync", __name__, url_prefix="/sync")
TIPOS_PERMITIDOS = {"Regular Season", "Playoffs"}
LIMITE_POR_LOTE = 500


def _inteiro(valor):
    if valor in (None, ""):
        return None
    return int(float(valor))


def _decimal(valor):
    if valor in (None, ""):
        return None
    if isinstance(valor, str) and ":" in valor:
        minutos, segundos = valor.split(":", 1)
        return round(float(minutos) + float(segundos) / 60, 2)
    return float(valor)


def _texto(valor, limite):
    if valor is None:
        return None
    return str(valor).strip()[:limite] or None


def _normalizar_registro(registro):
    if not isinstance(registro, dict):
        raise ValueError("cada estatística deve ser um objeto")

    game_id = _texto(registro.get("game_id"), 20)
    nome = _texto(registro.get("player_name"), 120)
    nba_player_id = _inteiro(registro.get("player_id"))
    data_texto = _texto(registro.get("game_date"), 10)

    if not game_id or not nome or not nba_player_id or not data_texto:
        raise ValueError("game_id, player_id, player_name e game_date são obrigatórios")

    try:
        data_partida = date.fromisoformat(data_texto)
    except ValueError as erro:
        raise ValueError("game_date deve usar o formato AAAA-MM-DD") from erro

    resultado = _texto(registro.get("wl"), 1)
    if resultado not in {None, "W", "L"}:
        resultado = None

    return {
        "game_id": game_id,
        "data_partida": data_partida,
        "nba_player_id": nba_player_id,
        "nome_jogador": nome,
        "team_id": _inteiro(registro.get("team_id")),
        "time_sigla": _texto(registro.get("team_abbreviation"), 5),
        "adversario": _texto(registro.get("matchup"), 30),
        "resultado": resultado,
        "minutos": _decimal(registro.get("min")),
        "pontos": _inteiro(registro.get("pts")),
        "rebotes": _inteiro(registro.get("reb")),
        "assistencias": _inteiro(registro.get("ast")),
        "roubos": _inteiro(registro.get("stl")),
        "tocos": _inteiro(registro.get("blk")),
        "turnovers": _inteiro(registro.get("tov")),
        "cestas": _inteiro(registro.get("fgm")),
        "tentativas": _inteiro(registro.get("fga")),
        "cestas_3": _inteiro(registro.get("fg3m")),
        "tentativas_3": _inteiro(registro.get("fg3a")),
        "lances_livres": _inteiro(registro.get("ftm")),
        "tentativas_livres": _inteiro(registro.get("fta")),
        "plus_minus": _decimal(registro.get("plus_minus")),
    }


@sync_bp.post("/nba")
@sync_token_required
def receber_dados_nba():
    dados = request.get_json(silent=True) or {}
    temporada = str(dados.get("season") or "").strip()
    tipo_temporada = str(dados.get("season_type") or "").strip()
    registros_recebidos = dados.get("records")

    if temporada != NBA_SYNC_SEASON:
        return jsonify({
            "erro": f"esta instalação aceita somente a temporada {NBA_SYNC_SEASON}"
        }), 400
    if tipo_temporada not in TIPOS_PERMITIDOS:
        return jsonify({"erro": "season_type deve ser Regular Season ou Playoffs"}), 400
    if not isinstance(registros_recebidos, list) or not registros_recebidos:
        return jsonify({"erro": "records deve ser uma lista não vazia"}), 400
    if len(registros_recebidos) > LIMITE_POR_LOTE:
        return jsonify({"erro": f"cada lote aceita no máximo {LIMITE_POR_LOTE} registros"}), 400

    try:
        registros = [_normalizar_registro(item) for item in registros_recebidos]
    except (TypeError, ValueError) as erro:
        return jsonify({"erro": str(erro)}), 400

    jogadores = {
        registro["nba_player_id"]: registro["nome_jogador"]
        for registro in registros
    }
    jogos = {
        registro["game_id"]: registro["data_partida"]
        for registro in registros
    }

    conn = conectar()
    try:
        with conn.cursor() as cur:
            execute_values(
                cur,
                """INSERT INTO jogadores (code_jogador, nome, nba_player_id)
                   VALUES %s
                   ON CONFLICT (nba_player_id) WHERE nba_player_id IS NOT NULL
                   DO UPDATE SET nome = EXCLUDED.nome""",
                [
                    (f"nba:{player_id}", nome, player_id)
                    for player_id, nome in jogadores.items()
                ],
            )
            execute_values(
                cur,
                """INSERT INTO jogos
                       (game_id, temporada, tipo_temporada, data_partida)
                   VALUES %s
                   ON CONFLICT (game_id) DO UPDATE SET
                       temporada = EXCLUDED.temporada,
                       tipo_temporada = EXCLUDED.tipo_temporada,
                       data_partida = EXCLUDED.data_partida""",
                [
                    (game_id, temporada, tipo_temporada, data_partida)
                    for game_id, data_partida in jogos.items()
                ],
            )
            execute_values(
                cur,
                """INSERT INTO estatisticas_jogador
                       (game_id, nba_player_id, nome_jogador, team_id, time_sigla,
                        adversario, resultado, minutos, pontos, rebotes, assistencias,
                        roubos, tocos, turnovers, cestas, tentativas, cestas_3,
                        tentativas_3, lances_livres, tentativas_livres, plus_minus)
                   VALUES %s
                   ON CONFLICT (game_id, nba_player_id) DO UPDATE SET
                       nome_jogador = EXCLUDED.nome_jogador,
                       team_id = EXCLUDED.team_id,
                       time_sigla = EXCLUDED.time_sigla,
                       adversario = EXCLUDED.adversario,
                       resultado = EXCLUDED.resultado,
                       minutos = EXCLUDED.minutos,
                       pontos = EXCLUDED.pontos,
                       rebotes = EXCLUDED.rebotes,
                       assistencias = EXCLUDED.assistencias,
                       roubos = EXCLUDED.roubos,
                       tocos = EXCLUDED.tocos,
                       turnovers = EXCLUDED.turnovers,
                       cestas = EXCLUDED.cestas,
                       tentativas = EXCLUDED.tentativas,
                       cestas_3 = EXCLUDED.cestas_3,
                       tentativas_3 = EXCLUDED.tentativas_3,
                       lances_livres = EXCLUDED.lances_livres,
                       tentativas_livres = EXCLUDED.tentativas_livres,
                       plus_minus = EXCLUDED.plus_minus,
                       atualizado_em = NOW()""",
                [
                    (
                        registro["game_id"],
                        registro["nba_player_id"],
                        registro["nome_jogador"],
                        registro["team_id"],
                        registro["time_sigla"],
                        registro["adversario"],
                        registro["resultado"],
                        registro["minutos"],
                        registro["pontos"],
                        registro["rebotes"],
                        registro["assistencias"],
                        registro["roubos"],
                        registro["tocos"],
                        registro["turnovers"],
                        registro["cestas"],
                        registro["tentativas"],
                        registro["cestas_3"],
                        registro["tentativas_3"],
                        registro["lances_livres"],
                        registro["tentativas_livres"],
                        registro["plus_minus"],
                    )
                    for registro in registros
                ],
                page_size=LIMITE_POR_LOTE,
            )
        conn.commit()
    except Exception:
        conn.rollback()
        return jsonify({"erro": "não foi possível salvar o lote"}), 500
    finally:
        conn.close()

    return jsonify({
        "mensagem": "lote sincronizado",
        "temporada": temporada,
        "tipo_temporada": tipo_temporada,
        "registros": len(registros),
        "jogadores": len(jogadores),
        "jogos": len(jogos),
    }), 200


@sync_bp.get("/status")
@sync_token_required
def status_sincronizacao():
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT COUNT(*), COUNT(DISTINCT nba_player_id), MAX(j.data_partida)
                   FROM estatisticas_jogador e
                   JOIN jogos j ON j.game_id = e.game_id
                   WHERE j.temporada = %s""",
                (NBA_SYNC_SEASON,),
            )
            registros, jogadores, ultima_data = cur.fetchone()
    finally:
        conn.close()

    return jsonify({
        "temporada": NBA_SYNC_SEASON,
        "registros": registros,
        "jogadores": jogadores,
        "ultima_partida": ultima_data.isoformat() if ultima_data else None,
    }), 200
