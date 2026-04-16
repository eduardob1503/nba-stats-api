from flask import jsonify, request
import psycopg2
import bcrypt
from email_validator import validate_email, EmailNotValidError
import jwt
import datetime
import os
from dotenv import load_dotenv
from email_validator import validate_email, EmailNotValidError

load_dotenv()
DB_CONFIG = {
    "host":os.getenv("host"),
    "port": os.getenv("port"),
    "user": os.getenv("user"),
    "password": os.getenv("password"),
    "database": os.getenv("database")
}
SECRET_KEY = os.getenv("SECRET_KEY") 



def conectar():
    conn = psycopg2.connect(**DB_CONFIG)
    return conn



def is_email(email: str) -> bool:
    try:
        validate_email(email)  # Valida formato e domínio
        return True
    except EmailNotValidError:
        return False
    
def init_auth(app):
    @app.route('/cadastro',methods=["POST"])
    def criar_login():
        conn = conectar()
        cur = conn.cursor()
        cadastro_user = request.get_json()
        if not cadastro_user:
            cur.close()
            conn.close()
            return jsonify({"erro":"json vazio"}),400
        email = cadastro_user.get("email")
        senha = cadastro_user.get("senha")
        nome = cadastro_user.get("nome")
        if is_email(email) is False:
            cur.close()
            conn.close()
            return jsonify({"erro": "email invalido"}),400
        cur.execute("SELECT 1 FROM usuarios WHERE email = %s",(email,))
        resultado = cur.fetchone()
        if resultado is not None:
            cur.close()
            conn.close()
            return jsonify({"erro":"email ja existente"}),400
        if not senha or not isinstance(senha,(str)):
            cur.close()
            conn.close()
            return jsonify({"erro":"senha invalida"}),400
        
        if not nome or not isinstance (nome,(str)):
            cur.close()
            conn.close()
            return jsonify({"erro": "nome invalido"}),400
        senha_crypt = criptografar_senha(senha)
        cur.execute("INSERT INTO usuarios (nome,email,senha)VALUES(%s,%s,%s)",(nome,email,senha_crypt))
        conn.commit()
        cur.close()
        conn.close()
        return(jsonify("usuario criado com sucesso")),200
    

    @app.route('/login',methods=["POST"])
    def login():
        payload = {}
        login_user = request.get_json()
        if not login_user:
            return jsonify({"erro":"json vazio"}),400
        email_login = login_user.get("email")
        if not email_login:
            return jsonify({"erro":"email vazio"}),400
        senha_login = login_user.get("senha")    
        if not senha_login:
            return jsonify({"erro":"senha vazia"}),400
        conn = conectar()
        cur = conn.cursor()
        cur.execute("SELECT * FROM usuarios WHERE email = %s",(email_login,))
        resultado = cur.fetchone()
        if resultado is  None:
            cur.close()
            conn.close()
            return jsonify({"erro":"email ou senha invalidos"}),400
        senha_hash = resultado[3]
        payload["id"] = resultado[0]
        payload["email"] = resultado[2]
        payload["is_admin"] = resultado[4]
        if bcrypt.checkpw(senha_login.encode("utf-8"),senha_hash.encode("utf-8")):
            token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
            cur.close()
            conn.close()
            return jsonify(token),200
        else:
            cur.close()
            conn.close()
            return jsonify({"erro":"email ou senha invalidos"}),400
                

def criptografar_senha(senha):
    senha_bytes = senha.encode('utf-8')
    salt = bcrypt.gensalt()
    senha_hash = bcrypt.hashpw(senha_bytes,salt)
    senha_string = senha_hash.decode()
    return senha_string

