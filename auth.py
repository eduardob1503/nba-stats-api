from flask import jsonify, request
import psycopg2
import bcrypt

DB_CONFIG = {
    "host":"localhost",
    "port": "5432",
    "user": "postgres",
    "password": "postgres",
    "database": "nba"
}




def conectar():
    conn = psycopg2.connect(**DB_CONFIG)
    return conn

def init_auth(app):
    @app.route('/cadastro',methods=["POST"])
    def criar_login():
        conn = conectar()
        cur = conn.cursor()
        cadastro_user = request.get_json()
        email = cadastro_user.get("email")
        senha = cadastro_user.get("senha")
        nome = cadastro_user.get("nome")
        senha_crypt = criptografar_senha(senha)
        cur.execute("INSERT INTO usuarios (nome,email,senha)VALUES(%s,%s,%s)",(nome,email,senha_crypt))
        conn.commit()
        cur.close()
        conn.close()
        return(jsonify(cadastro_user))

def criptografar_senha(senha):
    senha_bytes = senha.encode('utf-8')
    salt = bcrypt.gensalt()
    senha_hash = bcrypt.hashpw(senha_bytes,salt)
    senha_string = senha_hash.decode()
    return senha_string

