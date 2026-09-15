from flask import Blueprint, jsonify, request

from config import (
    ODDSPAPI_API_KEY,
    ODDSPAPI_BOOKMAKERS,
    ODDSPAPI_ODDS_MAX_AGE_MINUTES,
    ODDSPAPI_SPORT_ID,
    ODDSPAPI_TOURNAMENT_ID,
)
from database import conectar
from middlewares.auth import login_required
from services.analises import numero_json
from services.odds_normalizacao import MERCADOS_REAIS


odds_bp = Blueprint("odds", __name__, url_prefix="/odds")


def _data_json(valor):
    if valor is None:
        return None
    if hasattr(valor, "isoformat"):
        return valor.isoformat().replace("+00:00", "Z")
    return valor


def _booleano(valor, padrao=True):
    if valor is None:
        return padrao
    if valor == "true":
        return True
    if valor == "false":
        return False
    raise ValueError("somente_ativas invalido")


@odds_bp.get("/status")
@login_required
def status_odds():
    bookmaker = ODDSPAPI_BOOKMAKERS[0] if ODDSPAPI_BOOKMAKERS else "betano"
    base = {
        "configurado": bool(ODDSPAPI_API_KEY),
        "provedor": "oddspapi",
        "bookmaker": bookmaker,
        "sport_id": ODDSPAPI_SPORT_ID,
        "tournament_id": ODDSPAPI_TOURNAMENT_ID,
    }
    if not ODDSPAPI_API_KEY:
        return jsonify({
            **base,
            "quota": None,
            "ultima_sincronizacao": None,
            "status_ultima_sincronizacao": "nao_configurado",
        }), 200

    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT limite_mensal, requisicoes_utilizadas,
                          requisicoes_restantes, renova_em,
                          status_ultima_verificacao
                   FROM odds_provedor_status WHERE provedor = 'oddspapi'"""
            )
            status = cur.fetchone()
            cur.execute(
                """SELECT finalizada_em, status
                   FROM odds_sincronizacoes
                   WHERE provedor = 'oddspapi' AND bookmaker = %s
                   ORDER BY iniciada_em DESC LIMIT 1""",
                (bookmaker,),
            )
            sincronizacao = cur.fetchone()
    except Exception:
        return jsonify({"erro": "nao foi possivel consultar o status de odds"}), 500
    finally:
        conn.close()

    quota = None
    if status:
        quota = {
            "limite": status[0],
            "utilizadas": status[1],
            "restantes": status[2],
            "renova_em": _data_json(status[3]),
            "status": status[4],
        }
    return jsonify({
        **base,
        "quota": quota,
        "ultima_sincronizacao": _data_json(sincronizacao[0]) if sincronizacao else None,
        "status_ultima_sincronizacao": sincronizacao[1] if sincronizacao else "nunca_executada",
    }), 200


@odds_bp.get("/mapeamentos/pendentes")
@login_required
def mapeamentos_pendentes():
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, provedor_player_id, provedor_player_nome,
                          nome_normalizado, criado_em
                   FROM odds_jogadores_mapeamento
                   WHERE provedor = 'oddspapi' AND confirmado = FALSE
                   ORDER BY criado_em DESC, id DESC"""
            )
            linhas = cur.fetchall()
    except Exception:
        return jsonify({"erro": "nao foi possivel consultar os mapeamentos"}), 500
    finally:
        conn.close()
    return jsonify({
        "total": len(linhas),
        "mapeamentos": [
            {
                "id": linha[0],
                "provedor_player_id": linha[1],
                "jogador_nome_provedor": linha[2],
                "nome_normalizado": linha[3],
                "criado_em": _data_json(linha[4]),
            }
            for linha in linhas
        ],
    }), 200


@odds_bp.get("/props")
@login_required
def listar_props():
    mercado = request.args.get("mercado")
    if mercado and mercado not in MERCADOS_REAIS:
        return jsonify({"erro": "mercado invalido"}), 422
    lado = request.args.get("lado")
    if lado and lado not in {"over", "under", "yes", "no"}:
        return jsonify({"erro": "lado invalido"}), 422
    bookmaker = (request.args.get("bookmaker") or (
        ODDSPAPI_BOOKMAKERS[0] if ODDSPAPI_BOOKMAKERS else "betano"
    )).lower()
    try:
        somente_ativas = _booleano(request.args.get("somente_ativas"), True)
        evento_id = int(request.args["evento_id"]) if request.args.get("evento_id") else None
    except (ValueError, TypeError):
        return jsonify({"erro": "filtro invalido"}), 422

    filtros = ["c.bookmaker = %s"]
    parametros = [bookmaker]
    if mercado:
        filtros.append("c.mercado = %s")
        parametros.append(mercado)
    if lado:
        filtros.append("c.lado = %s")
        parametros.append(lado)
    if request.args.get("jogador_id"):
        filtros.append("c.jogador_id = %s")
        parametros.append(request.args["jogador_id"])
    if evento_id is not None:
        filtros.append("c.evento_id = %s")
        parametros.append(evento_id)
    if somente_ativas:
        filtros.extend([
            "c.ativa = TRUE",
            "c.capturada_em >= NOW() - (%s * INTERVAL '1 minute')",
            "e.inicio_em > NOW()",
        ])
        parametros.append(ODDSPAPI_ODDS_MAX_AGE_MINUTES)

    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""SELECT c.evento_id, e.provedor_fixture_id, e.inicio_em,
                           c.jogador_id, c.jogador_nome_provedor, c.mercado,
                           c.linha, c.lado, c.odd, c.bookmaker, c.capturada_em
                    FROM odds_cotacoes c
                    JOIN odds_eventos e ON e.id = c.evento_id
                    WHERE {' AND '.join(filtros)}
                    ORDER BY e.inicio_em, c.jogador_nome_provedor,
                             c.mercado, c.linha, c.lado""",
                parametros,
            )
            linhas = cur.fetchall()
    except Exception:
        return jsonify({"erro": "nao foi possivel consultar as props"}), 500
    finally:
        conn.close()

    props = [
        {
            "evento_id": linha[0],
            "provedor_fixture_id": linha[1],
            "inicio_em": _data_json(linha[2]),
            "jogador_id": linha[3],
            "jogador_nome": linha[4],
            "mercado": linha[5],
            "linha": numero_json(linha[6]),
            "lado": linha[7],
            "odd": numero_json(linha[8]),
            "bookmaker": linha[9],
            "capturada_em": _data_json(linha[10]),
        }
        for linha in linhas
    ]
    return jsonify({
        "bookmaker": bookmaker,
        "mercado": mercado,
        "atualizado_em": max((item["capturada_em"] for item in props), default=None),
        "total": len(props),
        "props": props,
    }), 200
