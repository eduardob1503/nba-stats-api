from flask import Blueprint, jsonify, request
from database import conectar
from middlewares.auth import admin_required, login_required
from math import sqrt
from services.nba import (
    JogadorNBAInexistente,
    NBAIndisponivel,
    buscar_jogos,
)

jogadores_bp = Blueprint("jogadores", __name__)


def _resumo_estatistico(pontos):
    if not pontos:
        return {"media": 0, "jogos": 0, "maximo": None, "minimo": None, "desvio_padrao": 0}

    media = sum(pontos) / len(pontos)
    variancia = sum((ponto - media) ** 2 for ponto in pontos) / len(pontos)
    return {
        "media": media,
        "jogos": len(pontos),
        "maximo": max(pontos),
        "minimo": min(pontos),
        "desvio_padrao": sqrt(variancia),
    }


def _erro_nba(erro):
    if isinstance(erro, ValueError):
        return jsonify({"erro": str(erro)}), 400
    if isinstance(erro, JogadorNBAInexistente):
        return jsonify({"erro": str(erro)}), 404
    return jsonify({"erro": str(erro)}), 503

@jogadores_bp.route('/jogadores',methods=['GET'])
@login_required
def obter_jogadores():
    conn = conectar()
    cur = conn.cursor()
    jogadores = []
    cur.execute("""SELECT * FROM jogadores""")
    jogadores_banco = cur.fetchall()
    for jogador in jogadores_banco:
        novo = {
        }
        novo["id"] = jogador[1]
        novo["nome"] = jogador[2]
        jogadores.append(novo)
    conn.close()
    return jsonify(jogadores)

@jogadores_bp.route('/jogadores/<code>', methods=['GET'])
@login_required
def obter_por_id(code):
    conn = conectar()
    cur = conn.cursor()
    if not code:
        cur.close()
        conn.close()    
        return jsonify({"erro":"sem code"}),400
    cur.execute("SELECT * FROM ppg WHERE id_jogador = %s",(code,))
    jogador_banco = cur.fetchall()
    if not jogador_banco:
        cur.execute("SELECT * FROM jogadores WHERE code_jogador = %s",(code,))
        jogador_banco = cur.fetchall()
        if not jogador_banco:
            cur.close()
            conn.close()
            return jsonify({"erro":"jogador inexistente"}),404
        dados_jogador={}
        dados_jogador["code"] = jogador_banco[0][1]
        dados_jogador["nome"] = jogador_banco[0][2]
        cur.close()
        conn.close()
        return jsonify(dados_jogador),200
    

    pontos_totais=[]
    dados_jogador={}
    dados_jogador["id"] = jogador_banco[0][1]
    id_partidas=[]
    for partida in jogador_banco:
        pontos_totais.append(partida[2])
        id_partidas.append(partida[0])
    dados_jogador["id_partida"]=id_partidas
    dados_jogador["pontos"]=pontos_totais
    dados_jogador.update(_resumo_estatistico(pontos_totais))
    cur.close()
    conn.close()
    return jsonify(dados_jogador),200


@jogadores_bp.route('/jogadores/<code>/nba', methods=['GET'])
@login_required
def obter_dados_nba(code):
    conn = conectar()
    cur = conn.cursor()
    cur.execute(
        "SELECT code_jogador, nome FROM jogadores WHERE code_jogador = %s",
        (code,),
    )
    jogador = cur.fetchone()
    cur.close()
    conn.close()

    if jogador is None:
        return jsonify({"erro": "jogador inexistente"}), 404

    try:
        resultado = buscar_jogos(
            jogador[1],
            temporada=request.args.get("temporada"),
            tipo_temporada=request.args.get("tipo", "Regular Season"),
        )
    except (ValueError, JogadorNBAInexistente, NBAIndisponivel) as erro:
        return _erro_nba(erro)

    pontos = [jogo["pontos"] for jogo in resultado["jogos"]]
    resposta = {
        "code": jogador[0],
        "nome": resultado["jogador"]["nome"],
        "nba_player_id": resultado["jogador"]["id"],
        "temporada": resultado["temporada"],
        "tipo_temporada": resultado["tipo_temporada"],
        "pontos": pontos,
        "partidas": [
            {
                **jogo,
                "data": jogo["data"].isoformat() if jogo["data"] else None,
            }
            for jogo in resultado["jogos"]
        ],
    }
    resposta.update(_resumo_estatistico(pontos))
    return jsonify(resposta), 200


@jogadores_bp.route('/jogadores/<code>/sincronizar', methods=['POST'])
@admin_required
def sincronizar_dados_nba(code):
    dados = request.get_json(silent=True) or {}
    conn = conectar()
    cur = conn.cursor()

    try:
        cur.execute(
            """SELECT code_jogador, nome, nba_player_id
               FROM jogadores
               WHERE code_jogador = %s""",
            (code,),
        )
        jogador = cur.fetchone()
    except Exception:
        conn.rollback()
        cur.close()
        conn.close()
        return jsonify({
            "erro": "migração pendente",
            "detalhe": "execute migrations/001_nba_sync.sql antes de sincronizar",
        }), 503

    if jogador is None:
        cur.close()
        conn.close()
        return jsonify({"erro": "jogador inexistente"}), 404

    try:
        resultado = buscar_jogos(
            jogador[1],
            temporada=dados.get("temporada"),
            tipo_temporada=dados.get("tipo", "Regular Season"),
            nba_player_id=jogador[2],
        )
    except (ValueError, JogadorNBAInexistente, NBAIndisponivel) as erro:
        cur.close()
        conn.close()
        return _erro_nba(erro)

    try:
        cur.execute(
            "UPDATE jogadores SET nba_player_id = %s WHERE code_jogador = %s",
            (resultado["jogador"]["id"], code),
        )
        for jogo in resultado["jogos"]:
            cur.execute(
                """INSERT INTO ppg
                       (pontos, id_jogador, game_id, temporada, data_partida, adversario)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   ON CONFLICT (id_jogador, game_id) DO UPDATE SET
                       pontos = EXCLUDED.pontos,
                       temporada = EXCLUDED.temporada,
                       data_partida = EXCLUDED.data_partida,
                       adversario = EXCLUDED.adversario""",
                (
                    jogo["pontos"],
                    code,
                    jogo["game_id"],
                    resultado["temporada"],
                    jogo["data"],
                    jogo["adversario"],
                ),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        return jsonify({"erro": "não foi possível salvar a sincronização"}), 500
    finally:
        cur.close()
        conn.close()

    return jsonify({
        "mensagem": "dados da NBA sincronizados",
        "code": code,
        "nba_player_id": resultado["jogador"]["id"],
        "temporada": resultado["temporada"],
        "tipo_temporada": resultado["tipo_temporada"],
        "jogos_sincronizados": len(resultado["jogos"]),
    }), 200


@jogadores_bp.route("/jogadores/<code>",methods=['POST'])
@admin_required
def adicionar_pontos(code):
    conn = conectar()
    cur = conn.cursor()
    pontos_jogador = request.get_json()
    
    pontos = pontos_jogador.get("pontos")
    if not isinstance(pontos, list):
        cur.close()
        conn.close()
        return jsonify({"erro": "pontos invalidos"}),400
    if not pontos:
        cur.close()
        conn.close()    
        return jsonify({"erro": "pontos vazio"}),400
    cur.execute("SELECT 1 FROM jogadores WHERE code_jogador = %s",(code,))
    resultado = cur.fetchone()
    if resultado is None:
        cur.close()
        conn.close()   
        return jsonify({"erro":"jogador inexistente"}),400
    for ponto in pontos:
        if not isinstance(ponto, (int,float)):
            cur.close()
            conn.close()
            return jsonify({"erro": "pontos invalidos"}),400
        cur.execute("INSERT INTO ppg(pontos,id_jogador)VALUES(%s,%s)",(ponto,code))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify(pontos_jogador),201
@jogadores_bp.route('/jogadores',methods=['POST'])
@admin_required
def adicionar_jogador():
        conn = conectar()
        cur = conn.cursor()
        novo_jogador = request.get_json()    
        if not novo_jogador:
            cur.close()
            conn.close()
            return jsonify({"erro": "json vazio"}),400
    
        nome = novo_jogador.get('nome')
        if not nome or not isinstance (nome,(str)):
            cur.close()
            conn.close()
            return jsonify({"erro": "sem nome"}),400
        nome = nome.lower() 
        partes = nome.split()
        if len(partes)<2:
            cur.close()
            conn.close()
            return jsonify({"erro": "nome curto"}),400
        sobrenome = partes[1]
        primeiro = partes[0]
        indice = 1
        code_jogador = sobrenome[0:5]+primeiro[0:2]+"0"+str(indice)
        novo_jogador["code"] = code_jogador
        cur.execute("SELECT 1 FROM jogadores where code_jogador = %s",(code_jogador,))
        resultado = cur.fetchone()
        while resultado is not None:
            indice += 1
            code_jogador = sobrenome[0:5]+primeiro[0:2]+"0"+str(indice)
            cur.execute("SELECT 1 FROM jogadores where code_jogador = %s",(code_jogador,))
            resultado = cur.fetchone()
        novo_jogador["code"] = code_jogador
        cur.execute("INSERT INTO jogadores(code_jogador,nome)VALUES(%s,%s)"
        ,(novo_jogador["code"],novo_jogador["nome"]))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify(novo_jogador),201

@jogadores_bp.route('/jogadores/<code>',methods=["DELETE"])
@admin_required
def deletar_jogador(code):
    conn = conectar()
    cur = conn.cursor()
    if not code:
        cur.close()
        conn.close()
        return jsonify({"erro":"sem code"}),400
    cur.execute("SELECT 1 FROM jogadores WHERE code_jogador = %s",(code,))
    resultado = cur.fetchone()
    if resultado is None:
        cur.close()
        conn.close()
        return jsonify({"erro":"jogador inexistente"}),400
    cur.execute("DELETE FROM ppg WHERE id_jogador = %s",(code,))
    conn.commit()
    cur.execute("DELETE FROM jogadores WHERE code_jogador = %s",(code,))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"mensagem":"jogador deletado"}),200
