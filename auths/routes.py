from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from email_validator import EmailNotValidError, validate_email
from flask import Blueprint, jsonify, request

from config import ADMIN_EMAILS, FIRST_USER_ADMIN, SECRET_KEY
from database import conectar


auth_bp = Blueprint("auth", __name__)
NOME_MINIMO = 2
NOME_MAXIMO = 100


def criptografar_senha(senha):
    senha_bytes = senha.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(senha_bytes, salt).decode()


def normalizar_nome(nome):
    if not isinstance(nome, str):
        raise ValueError("nome invalido")

    nome_exibicao = " ".join(nome.split())
    if not NOME_MINIMO <= len(nome_exibicao) <= NOME_MAXIMO:
        raise ValueError("nome invalido")
    return nome_exibicao, nome_exibicao.lower()


def is_email(email: str) -> bool:
    if not isinstance(email, str):
        return False
    try:
        validate_email(email, check_deliverability=False)
        return True
    except EmailNotValidError:
        return False


def _gerar_token(usuario_id, nome, is_admin=False):
    agora = datetime.now(timezone.utc)
    payload = {
        "sub": str(usuario_id),
        # Mantido temporariamente para consumidores dos tokens antigos.
        "id": usuario_id,
        "nome": nome,
        "is_admin": bool(is_admin),
        "iat": agora,
        "exp": agora + timedelta(hours=1),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


@auth_bp.post("/cadastro")
def criar_login():
    """Cadastro legado por e-mail e senha; o fluxo normal usa POST /login."""
    cadastro_user = request.get_json(silent=True) or {}
    try:
        nome, nome_normalizado = normalizar_nome(cadastro_user.get("nome"))
    except ValueError as erro:
        return jsonify({"erro": str(erro)}), 400

    email_recebido = cadastro_user.get("email")
    email = (
        email_recebido.strip().lower()
        if isinstance(email_recebido, str)
        else email_recebido
    )
    senha = cadastro_user.get("senha")
    if not is_email(email):
        return jsonify({"erro": "email invalido"}), 400
    if not isinstance(senha, str) or not senha:
        return jsonify({"erro": "senha invalida"}), 400

    conn = conectar()
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1 FROM usuarios WHERE email = %s", (email,))
        if cur.fetchone() is not None:
            return jsonify({"erro": "email ja existente"}), 409

        is_admin = email in ADMIN_EMAILS
        if FIRST_USER_ADMIN and not is_admin:
            cur.execute("SELECT NOT EXISTS (SELECT 1 FROM usuarios)")
            is_admin = bool(cur.fetchone()[0])

        senha_crypt = criptografar_senha(senha)
        cur.execute(
            """INSERT INTO usuarios
                   (nome, nome_normalizado, email, senha, is_admin)
               VALUES (%s, %s, %s, %s, %s)""",
            (nome, nome_normalizado, email, senha_crypt, is_admin),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()
    return jsonify({"mensagem": "usuario criado com sucesso"}), 201


@auth_bp.post("/login")
def login():
    dados = request.get_json(silent=True) or {}
    try:
        nome, nome_normalizado = normalizar_nome(dados.get("nome"))
    except ValueError as erro:
        return jsonify({"erro": str(erro)}), 400

    conn = conectar()
    cur = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO usuarios (nome, nome_normalizado, is_admin)
               VALUES (%s, %s, FALSE)
               ON CONFLICT (nome_normalizado) DO UPDATE SET
                   nome_normalizado = EXCLUDED.nome_normalizado
               RETURNING id, nome, is_admin""",
            (nome, nome_normalizado),
        )
        usuario_id, nome_salvo, is_admin = cur.fetchone()
        conn.commit()
    finally:
        cur.close()
        conn.close()

    token = _gerar_token(usuario_id, nome_salvo, is_admin)
    return jsonify({
        "token": token,
        "usuario": {"id": usuario_id, "nome": nome_salvo},
    }), 200
