#objetivo - Criar uma api de disponibilize a consulta e retorne stats do jogador
#localhost
#localhost/jogadores
#localhost/jogadores/id (GET)
#localhost/jogadores(PUT)
#localhost/jogadores/id (POST)
#localhost/jogadores/id/pontos
from flask import Flask, jsonify, request
import os
import psycopg2
import auth

DB_CONFIG = {
    "host":"localhost",
    "port": "5432",
    "user": "postgres",
    "password": "postgres",
    "database": "nba"
}

app = Flask(__name__)
auth.init_auth(app)


   

def conectar():
    conn = psycopg2.connect(**DB_CONFIG)
    return conn


@app.route('/jogadores',methods=['GET'])
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

@app.route('/jogadores/<id>', methods=['GET'])
#def obter_por_id(id):
 #   for jogador in jogadores:
      #  if jogador.get('id') == id:
     #       return jsonify(jogador)
  #  return jsonify({
      #  "erro": "Jogador não encontrado",
       # "id_procurado": id
       # }), 404

#@app.route ('/jogadores/<id>', methods=['PUT'])
#def alterar_jogador(id):
    #jogador_alterado = request.get_json()
    #if jogador_alterado is None:
        #return jsonify({"erro": "json invalido"}),400
    #for indice,jogador in enumerate(jogadores):
        #if jogador.get('id') == id:
            #jogador_alterado.pop("id",None)
            #for chave, valor in jogador_alterado.items():
                #if valor is None:
                    #jogador.pop(chave,None)
            #jogadores[indice].update(jogador_alterado)
            #return jsonify(jogadores[indice]),200
    #else:
        #return jsonify({"erro": "Jogador não encontrado"}),404

@app.route("/jogadores/<code>",methods=['POST'])
def adicionar_pontos(code):
    conn = conectar()
    cur = conn.cursor()
    pontos_jogador = request.get_json()
    pontos = pontos_jogador.get("pontos")
    if not isinstance(pontos, list):
        return jsonify({"erro": "pontos invalidos"}),400
    if not pontos:
        return jsonify({"erro": "pontos vazio"}),400
    cur.execute("SELECT 1 FROM jogadores WHERE code_jogador = %s",(code,))
    resultado = cur.fetchone()
    if resultado is None:
        return jsonify({"erro":"jogador inexistente"}),400
    for ponto in pontos:
        if not isinstance(ponto, (int,float)):
            return jsonify({"erro": "pontos invalidos"}),400
        cur.execute("INSERT INTO ppg(pontos,id_jogador)VALUES(%s,%s)",(ponto,code))
    conn.commit()
    cur.close()
    conn.close()
    
    return jsonify(pontos_jogador),201
@app.route('/jogadores',methods=['POST'])
def adicionar_jogador():
        conn = conectar()
        cur = conn.cursor()
        novo_jogador = request.get_json()    
        if not novo_jogador:
            return jsonify({"erro": "json vazio"}),400
        nome = novo_jogador.get('nome')
        if not nome or not isinstance (nome,(str)):
            return jsonify({"erro": "sem nome"}),400
        nome = nome.lower() 
        partes = nome.split()
        if len(partes)<2:
            return jsonify({"erro": "nome curto"}),400
        sobrenome = partes[1]
        primeiro = partes[0]
        code_jogador = sobrenome[0:5]+primeiro[0:2]+"01"
        
        novo_jogador["code"] = code_jogador
        cur.execute("INSERT INTO jogadores(code_jogador,nome)VALUES(%s,%s)"
                    ,(novo_jogador["code"],novo_jogador["nome"]))
        conn.commit()
        cur.close()
        conn.close()

        return jsonify(novo_jogador),201

#@app.route('/jogadores/<id>',methods=["DELETE"])
#def deletar_jogador(id):
    #for indice,jogador in enumerate(jogadores):
     #   if jogador.get('id') == id:
       #     jogador_removido = jogadores.pop(indice)
        #    return jsonify(jogador_removido),200
   # else:
      #  return jsonify({"erro": "jogador nao encontrado"}),404
    

app.run(host="localhost",port ="5000",debug=True)
