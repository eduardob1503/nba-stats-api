#objetivo - Criar uma api de disponibilize a consulta e retorne stats do jogador
from flask import Flask, jsonify, request
import auth
from functools import wraps
import jwt
from math import sqrt
DB_CONFIG = auth.DB_CONFIG

app = Flask(__name__)
auth.init_auth(app)

def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return jsonify({"erro":"sem header"}),401
        auth_header_splited = auth_header.split(" ")
        if len(auth_header_splited) != 2:
            return jsonify({"erro":"header invalido"}),401
        if auth_header_splited[0] != "Bearer":
            return jsonify({"erro":"header invalido"}),401
        try:
            token = auth_header_splited[1]
            payload = jwt.decode(token, auth.SECRET_KEY, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return jsonify({"erro":"token expirado"}),401
        except jwt.InvalidTokenError:
            return jsonify({"erro":"token invalido"}),401
        except Exception:
            return jsonify({"erro":"erro interno"}),500
        if not payload.get("is_admin"):
            return jsonify({"erro":"acesso negado"}),403
        return func(*args,**kwargs)
    return wrapper

def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return jsonify({"erro":"sem header"}),401
        auth_header_splited = auth_header.split(" ")
        if len(auth_header_splited) != 2:
            return jsonify({"erro":"header invalido"}),401
        if auth_header_splited[0] != "Bearer":
            return jsonify({"erro":"header invalido"}),401
        try:
            token = auth_header_splited[1]
            jwt.decode(token, auth.SECRET_KEY, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return jsonify({"erro":"token expirado"}),401
        except jwt.InvalidTokenError:
            return jsonify({"erro":"token invalido"}),401
        except Exception:
            return jsonify({"erro":"erro interno"}),500
        return func(*args,**kwargs)


        
    return wrapper




@app.route('/jogadores',methods=['GET'])
@login_required
def obter_jogadores():
    conn = auth.conectar()
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

@app.route('/jogadores/<code>', methods=['GET'])
@login_required
def obter_por_id(code):
    conn = auth.conectar()
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
    desvios=0
    for partida in jogador_banco:
        pontos_totais.append(partida[2])
        id_partidas.append(partida[0])
    dados_jogador["id_partida"]=id_partidas
    dados_jogador["pontos"]=pontos_totais
    dados_jogador["media"] = sum(pontos_totais)/len(pontos_totais)
    dados_jogador["jogos"] = len(pontos_totais)
    dados_jogador["maximo"] = max(pontos_totais)
    dados_jogador["minimo"] = min(pontos_totais)
    for ponto in pontos_totais:
        desvios += ((ponto - dados_jogador["media"])**2)/dados_jogador["jogos"]
    dados_jogador["desvio_padrao"] = sqrt(desvios)
    cur.close()
    conn.close()
    return jsonify(dados_jogador),200


@app.route("/jogadores/<code>",methods=['POST'])
@admin_required
def adicionar_pontos(code):
    conn = auth.conectar()
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
@app.route('/jogadores',methods=['POST'])
@admin_required
def adicionar_jogador():
        conn = auth.conectar()
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

@app.route('/jogadores/<code>',methods=["DELETE"])
@admin_required
def deletar_jogador(code):
    conn = auth.conectar()
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
    
    
if __name__ == "__main__":
    app.run(host="localhost",port ="5000",debug=True)
