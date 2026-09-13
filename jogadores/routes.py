from flask import Blueprint, jsonify, request
from database import conectar
from middlewares.auth import admin_required, login_required
from datetime import date
from math import sqrt
from services.nba import (
    JogadorNBAInexistente,
    NBAIndisponivel,
    buscar_jogadores_nba,
    buscar_jogos,
    encontrar_jogador_por_id,
)
from config import ENV, NBA_SYNC_SEASON, NBA_SYNC_SEASONS

jogadores_bp = Blueprint("jogadores", __name__)
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


def _valor_valido(valor):
    return isinstance(valor, (int, float)) and not isinstance(valor, bool)


def adicionar_mercados_calculados(jogo):
    jogo = dict(jogo)
    for mercado, componentes in MERCADOS_COMPONENTES.items():
        if len(componentes) == 1:
            continue
        valores = [jogo.get(componente) for componente in componentes]
        if all(_valor_valido(valor) for valor in valores):
            jogo[mercado] = sum(valores)
    return jogo


def valores_do_mercado(jogos, mercado):
    return [
        jogo[mercado]
        for jogo in jogos
        if _valor_valido(jogo.get(mercado))
    ]


def _erro_nba(erro):
    if isinstance(erro, ValueError):
        return jsonify({"erro": str(erro)}), 400
    if isinstance(erro, JogadorNBAInexistente):
        return jsonify({"erro": str(erro)}), 404
    return jsonify({"erro": str(erro)}), 503


def _buscar_jogos_salvos(nba_player_id, temporada, tipo_temporada):
    conn = conectar()
    try:
        with conn.cursor() as cur:
            consulta = """SELECT j.game_id, j.data_partida, e.nome_jogador, e.adversario,
                                 e.resultado, e.minutos, e.pontos, e.rebotes, e.assistencias,
                                 e.roubos, e.tocos, e.turnovers, e.cestas_3, e.tentativas_3,
                                 e.plus_minus
                          FROM estatisticas_jogador e
                          JOIN jogos j ON j.game_id = e.game_id
                          WHERE e.nba_player_id = %s
                            AND j.temporada = %s"""
            parametros = [nba_player_id, temporada]
            if tipo_temporada != "Todos":
                consulta += " AND j.tipo_temporada = %s"
                parametros.append(tipo_temporada)
            consulta += " ORDER BY j.data_partida DESC, j.game_id DESC"
            cur.execute(consulta, parametros)
            linhas = cur.fetchall()
    except Exception:
        conn.rollback()
        return None
    finally:
        conn.close()

    if not linhas:
        return None

    return {
        "jogador": {"id": int(nba_player_id), "nome": linhas[0][2], "ativo": None},
        "temporada": temporada,
        "tipo_temporada": tipo_temporada,
        "origem": "banco",
        "jogos": [
            {
                "game_id": linha[0],
                "data": linha[1],
                "adversario": linha[3],
                "resultado": linha[4],
                "minutos": float(linha[5]) if linha[5] is not None else None,
                "pontos": linha[6],
                "rebotes": linha[7],
                "assistencias": linha[8],
                "roubos": linha[9],
                "tocos": linha[10],
                "turnovers": linha[11],
                "cestas_3": linha[12],
                "tentativas_3": linha[13],
                "plus_minus": float(linha[14]) if linha[14] is not None else None,
            }
            for linha in linhas
        ],
    }

@jogadores_bp.route('/jogadores',methods=['GET'])
@login_required
def obter_jogadores():
    busca = (request.args.get("busca") or "").strip()
    if busca:
        return jsonify(buscar_jogadores_nba(busca)), 200

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
    temporada = request.args.get("temporada") or NBA_SYNC_SEASON
    if temporada not in NBA_SYNC_SEASONS:
        return jsonify({
            "erro": "temporada não permitida",
            "temporadas_permitidas": list(NBA_SYNC_SEASONS),
        }), 400
    tipo_temporada = request.args.get("tipo", "Todos")
    if tipo_temporada not in {"Todos", "Regular Season", "Playoffs"}:
        return jsonify({"erro": "tipo deve ser Todos, Regular Season ou Playoffs"}), 400

    conn = conectar()
    cur = conn.cursor()
    cur.execute(
        "SELECT code_jogador, nome, nba_player_id FROM jogadores WHERE code_jogador = %s",
        (code,),
    )
    jogador = cur.fetchone()
    cur.close()
    conn.close()

    jogador_diretorio = None
    if jogador is None and code.startswith("nba:"):
        try:
            jogador_diretorio = encontrar_jogador_por_id(code.removeprefix("nba:"))
        except JogadorNBAInexistente as erro:
            return _erro_nba(erro)
    elif jogador is None:
        return jsonify({"erro": "jogador inexistente"}), 404

    nome = jogador[1] if jogador else jogador_diretorio["nome"]
    nba_player_id = jogador[2] if jogador else jogador_diretorio["id"]

    resultado = None
    if nba_player_id:
        resultado = _buscar_jogos_salvos(nba_player_id, temporada, tipo_temporada)

    if resultado is None:
        if ENV == "production":
            return jsonify({
                "erro": "estatísticas ainda não sincronizadas para esse jogador",
                "temporada": temporada,
            }), 404
        try:
            tipos_consulta = (
                ("Regular Season", "Playoffs")
                if tipo_temporada == "Todos"
                else (tipo_temporada,)
            )
            resultados = [
                buscar_jogos(
                    nome,
                    temporada=temporada,
                    tipo_temporada=tipo,
                    nba_player_id=nba_player_id,
                )
                for tipo in tipos_consulta
            ]
            resultado = resultados[0]
            if len(resultados) > 1:
                resultado["jogos"] = sorted(
                    [jogo for item in resultados for jogo in item["jogos"]],
                    key=lambda jogo: jogo["data"] or date.min,
                    reverse=True,
                )
                resultado["tipo_temporada"] = "Todos"
            resultado["origem"] = "nba_api"
        except (ValueError, JogadorNBAInexistente, NBAIndisponivel) as erro:
            return _erro_nba(erro)

    jogos = [
        adicionar_mercados_calculados(jogo)
        for jogo in resultado["jogos"]
    ]
    pontos = valores_do_mercado(jogos, "pontos")
    medias = {}
    for mercado in MERCADOS_COMPONENTES:
        valores = valores_do_mercado(jogos, mercado)
        if valores:
            medias[mercado] = sum(valores) / len(valores)
    resposta = {
        "code": jogador[0] if jogador else code,
        "nome": resultado["jogador"]["nome"],
        "nba_player_id": resultado["jogador"]["id"],
        "temporada": resultado["temporada"],
        "tipo_temporada": resultado["tipo_temporada"],
        "origem": resultado.get("origem", "nba_api"),
        "pontos": pontos,
        "medias": medias,
        "partidas": [
            {
                **jogo,
                "data": jogo["data"].isoformat() if jogo["data"] else None,
            }
            for jogo in jogos
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
        nome = " ".join(nome.split())
        partes = nome.lower().split()
        if len(partes)<2:
            cur.close()
            conn.close()
            return jsonify({"erro": "nome curto"}),400
        sobrenome = partes[1]
        primeiro = partes[0]
        indice = 1
        code_jogador = sobrenome[0:5]+primeiro[0:2]+"0"+str(indice)
        cur.execute("SELECT 1 FROM jogadores where code_jogador = %s",(code_jogador,))
        resultado = cur.fetchone()
        while resultado is not None:
            indice += 1
            code_jogador = sobrenome[0:5]+primeiro[0:2]+"0"+str(indice)
            cur.execute("SELECT 1 FROM jogadores where code_jogador = %s",(code_jogador,))
            resultado = cur.fetchone()
        novo_jogador["id"] = code_jogador
        novo_jogador["code"] = code_jogador
        cur.execute("INSERT INTO jogadores(code_jogador,nome)VALUES(%s,%s)"
        ,(novo_jogador["code"],nome))
        novo_jogador["nome"] = nome
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
