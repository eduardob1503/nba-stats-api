from functools import wraps

import jwt
from flask import g, jsonify, request

from config import SECRET_KEY


def _erro_token():
    return jsonify({"erro": "token invalido ou expirado"}), 401


def _autenticar():
    auth_header = request.headers.get("Authorization", "")
    partes = auth_header.split()
    if len(partes) != 2 or partes[0] != "Bearer":
        return _erro_token()

    try:
        payload = jwt.decode(partes[1], SECRET_KEY, algorithms=["HS256"])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return _erro_token()
    except Exception:
        return jsonify({"erro": "erro interno"}), 500

    identificador = payload.get("sub", payload.get("id"))
    if identificador in (None, ""):
        return _erro_token()

    g.usuario_id = identificador
    g.jwt_payload = payload
    return None


def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        erro = _autenticar()
        if erro:
            return erro
        if not g.jwt_payload.get("is_admin"):
            return jsonify({"erro": "acesso negado"}), 403
        return func(*args, **kwargs)

    return wrapper


def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        erro = _autenticar()
        if erro:
            return erro
        return func(*args, **kwargs)

    return wrapper
