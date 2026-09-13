from decimal import Decimal

from flask import Blueprint, g, jsonify, request
from psycopg2.extras import Json

from config import NBA_SYNC_SEASONS
from database import conectar
from jogadores.routes import _buscar_jogos_salvos
from middlewares.auth import login_required
from services.analises import (
    LADOS_PERMITIDOS,
    MERCADOS_PERMITIDOS,
    QUANTIDADES_PERMITIDAS,
    calcular_analise,
    normalizar_quantidade,
    numero_json,
    validar_decimal,
)


analises_bp = Blueprint("analises", __name__, url_prefix="/analises")
TIPOS_PERMITIDOS = ("Todos", "Regular Season", "Playoffs")
COLUNAS_ANALISE = """id, usuario_id, jogador_id, nba_player_id, jogador_nome,
                     temporada, tipo_temporada, mercado, quantidade_jogos,
                     linha, odd, lado, snapshot, created_at, updated_at"""


def _usuario_id():
    try:
        usuario_id = int(g.usuario_id)
    except (TypeError, ValueError):
        return None
    return usuario_id if usuario_id > 0 else None


def _erro_validacao(mensagem, **detalhes):
    return jsonify({"erro": mensagem, **detalhes}), 422


def _data_json(valor):
    return valor.isoformat() if hasattr(valor, "isoformat") else valor


def _quantidade_json(valor):
    return int(valor) if str(valor).isdigit() else valor


def _serializar_analise(linha):
    snapshot = linha[12] or {}
    return {
        "id": linha[0],
        "usuario_id": linha[1],
        "jogador": {
            "id": linha[2],
            "nba_player_id": linha[3],
            "nome": linha[4],
        },
        "temporada": linha[5],
        "tipo_temporada": linha[6],
        "mercado": linha[7],
        "quantidade_jogos": _quantidade_json(linha[8]),
        "linha": numero_json(linha[9]),
        "odd": numero_json(linha[10]),
        "lado": linha[11],
        **snapshot,
        "created_at": _data_json(linha[13]),
        "updated_at": _data_json(linha[14]),
    }


def _buscar_jogador(code):
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT code_jogador, nome, nba_player_id
                   FROM jogadores
                   WHERE code_jogador = %s""",
                (code,),
            )
            return cur.fetchone()
    finally:
        conn.close()


def _validar_configuracao(dados):
    jogador_id = dados.get("jogador_id") or dados.get("jogador")
    if not isinstance(jogador_id, str) or not jogador_id.strip():
        raise ValueError("jogador invalido")

    temporada = dados.get("temporada")
    if temporada not in NBA_SYNC_SEASONS:
        raise ValueError("temporada invalida")

    mercado = dados.get("mercado")
    if mercado not in MERCADOS_PERMITIDOS:
        raise ValueError("mercado invalido")

    quantidade = normalizar_quantidade(dados.get("quantidade_jogos"))
    lado = dados.get("lado")
    lado = lado.strip().lower() if isinstance(lado, str) else lado
    if lado not in LADOS_PERMITIDOS:
        raise ValueError("lado invalido")

    tipo = dados.get("tipo_temporada", dados.get("tipo", "Todos"))
    if tipo not in TIPOS_PERMITIDOS:
        raise ValueError("tipo de temporada invalido")

    linha = validar_decimal(dados.get("linha"), "linha", Decimal("0"))
    odd = validar_decimal(dados.get("odd"), "odd", Decimal("0"))
    if odd <= 1:
        raise ValueError("odd invalida")

    return {
        "jogador_id": jogador_id.strip(),
        "temporada": temporada,
        "mercado": mercado,
        "quantidade": quantidade,
        "lado": lado,
        "tipo": tipo,
        "linha": linha,
        "odd": odd,
    }


@analises_bp.post("")
@login_required
def criar_analise():
    usuario_id = _usuario_id()
    if usuario_id is None:
        return jsonify({"erro": "token invalido ou expirado"}), 401

    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        return jsonify({"erro": "json invalido"}), 400

    try:
        config = _validar_configuracao(dados)
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
        jogador = _buscar_jogador(config["jogador_id"])
    except Exception:
        return jsonify({"erro": "nao foi possivel consultar o jogador"}), 500
    if jogador is None or jogador[2] is None:
        return jsonify({"erro": "jogador inexistente"}), 404

    resultado = _buscar_jogos_salvos(
        jogador[2], config["temporada"], config["tipo"]
    )
    if resultado is None:
        return jsonify({
            "erro": "estatisticas ainda nao sincronizadas para esse jogador",
            "temporada": config["temporada"],
        }), 404

    try:
        snapshot = calcular_analise(
            resultado["jogos"],
            config["mercado"],
            config["quantidade"],
            config["linha"],
            config["lado"],
        )
    except ValueError as erro:
        return _erro_validacao(str(erro))

    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO analises
                       (usuario_id, jogador_id, nba_player_id, jogador_nome,
                        temporada, tipo_temporada, mercado, quantidade_jogos,
                        linha, odd, lado, snapshot)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   RETURNING id, created_at, updated_at""",
                (
                    usuario_id,
                    jogador[0],
                    jogador[2],
                    jogador[1],
                    config["temporada"],
                    config["tipo"],
                    config["mercado"],
                    config["quantidade"],
                    config["linha"],
                    config["odd"],
                    config["lado"],
                    Json(snapshot),
                ),
            )
            analise_id, criada_em, atualizada_em = cur.fetchone()
        conn.commit()
    except Exception:
        conn.rollback()
        return jsonify({"erro": "nao foi possivel salvar a analise"}), 500
    finally:
        conn.close()

    linha_salva = (
        analise_id,
        usuario_id,
        jogador[0],
        jogador[2],
        jogador[1],
        config["temporada"],
        config["tipo"],
        config["mercado"],
        config["quantidade"],
        config["linha"],
        config["odd"],
        config["lado"],
        snapshot,
        criada_em,
        atualizada_em,
    )
    return jsonify(_serializar_analise(linha_salva)), 201


@analises_bp.get("")
@login_required
def listar_analises():
    usuario_id = _usuario_id()
    if usuario_id is None:
        return jsonify({"erro": "token invalido ou expirado"}), 401

    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""SELECT {COLUNAS_ANALISE}
                    FROM analises
                    WHERE usuario_id = %s
                    ORDER BY created_at DESC, id DESC""",
                (usuario_id,),
            )
            linhas = cur.fetchall()
    except Exception:
        return jsonify({"erro": "nao foi possivel listar as analises"}), 500
    finally:
        conn.close()
    return jsonify([_serializar_analise(linha) for linha in linhas]), 200


@analises_bp.get("/<int:analise_id>")
@login_required
def obter_analise(analise_id):
    usuario_id = _usuario_id()
    if usuario_id is None:
        return jsonify({"erro": "token invalido ou expirado"}), 401

    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""SELECT {COLUNAS_ANALISE}
                    FROM analises
                    WHERE id = %s AND usuario_id = %s""",
                (analise_id, usuario_id),
            )
            linha = cur.fetchone()
    except Exception:
        return jsonify({"erro": "nao foi possivel consultar a analise"}), 500
    finally:
        conn.close()
    if linha is None:
        return jsonify({"erro": "analise nao encontrada"}), 404
    return jsonify(_serializar_analise(linha)), 200


@analises_bp.delete("/<int:analise_id>")
@login_required
def apagar_analise(analise_id):
    usuario_id = _usuario_id()
    if usuario_id is None:
        return jsonify({"erro": "token invalido ou expirado"}), 401

    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """DELETE FROM analises
                   WHERE id = %s AND usuario_id = %s
                   RETURNING id""",
                (analise_id, usuario_id),
            )
            apagada = cur.fetchone()
        if apagada is None:
            conn.rollback()
            return jsonify({"erro": "analise nao encontrada"}), 404
        conn.commit()
    except Exception:
        conn.rollback()
        return jsonify({"erro": "nao foi possivel apagar a analise"}), 500
    finally:
        conn.close()
    return jsonify({"mensagem": "analise apagada"}), 200
