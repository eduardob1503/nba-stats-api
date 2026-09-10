from flask import Blueprint, jsonify, request
from database import conectar
from config import SECRET_KEY
from middlewares.auth import admin_required, login_required
from datetime import timedelta,timezone,datetime
import bcrypt
import jwt
from email_validator import validate_email, EmailNotValidError

def criptografar_senha(senha):
    senha_bytes = senha.encode('utf-8')
    salt = bcrypt.gensalt()
    senha_hash = bcrypt.hashpw(senha_bytes,salt)
    senha_string = senha_hash.decode()
    return senha_string
auth_bp = Blueprint("auth",__name__)

def is_email(email: str) -> bool:
    if not isinstance(email, str):
        return False
    try:
        validate_email(email, check_deliverability=False)
        return True
    except EmailNotValidError:
        return False

@auth_bp.route('/cadastro',methods=["POST"])
def criar_login():
    cadastro_user = request.get_json()
    if not cadastro_user:
        return jsonify({"erro":"json vazio"}),400
    conn = conectar()
    cur = conn.cursor()
    email_recebido = cadastro_user.get("email")
    email = email_recebido.strip().lower() if isinstance(email_recebido, str) else email_recebido
    senha = cadastro_user.get("senha")
    nome_recebido = cadastro_user.get("nome")
    nome = nome_recebido.strip() if isinstance(nome_recebido, str) else nome_recebido
    if is_email(email) is False:
        cur.close()
        conn.close()
        return jsonify({"erro": "email invalido"}),400
    cur.execute("SELECT 1 FROM usuarios WHERE email = %s",(email,))
    resultado = cur.fetchone()
    if resultado is not None:
        cur.close()
        conn.close()
        return jsonify({"erro":"email ja existente"}),409
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
    

@auth_bp.route('/login',methods=["POST"])
def login():
    payload = {}
    login_user = request.get_json()
    if not login_user:
        return jsonify({"erro":"json vazio"}),400
    email_recebido = login_user.get("email")
    email_login = email_recebido.strip().lower() if isinstance(email_recebido, str) else email_recebido
    if not email_login:
        return jsonify({"erro":"email vazio"}),400
    senha_login = login_user.get("senha")    
    if not senha_login:
        return jsonify({"erro":"senha vazia"}),400
    conn = conectar()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, nome, email, senha, is_admin FROM usuarios WHERE LOWER(email) = %s",
        (email_login,),
    )
    resultado = cur.fetchone()
    if resultado is  None:
        cur.close()
        conn.close()
        return jsonify({"erro":"email ou senha invalidos"}),401
    senha_hash = resultado[3]
    
    if bcrypt.checkpw(senha_login.encode("utf-8"),senha_hash.encode("utf-8")):
        payload["id"] = resultado[0]
        payload["nome"] = resultado[1]
        payload["email"] = resultado[2]
        payload["is_admin"] = resultado[4]
        payload["iat"]= datetime.now(timezone.utc)
        payload["exp"] = datetime.now(timezone.utc)+timedelta(hours=1)
        token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
        cur.close()
        conn.close()
        return jsonify({"token":token}),200
    else:
        cur.close()
        conn.close()
        return jsonify({"erro":"email ou senha invalidos"}),401
