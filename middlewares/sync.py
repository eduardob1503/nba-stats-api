import hmac
from functools import wraps

from flask import jsonify, request

from config import SYNC_TOKEN


def sync_token_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not SYNC_TOKEN:
            return jsonify({"erro": "sincronização não configurada"}), 503

        token = request.headers.get("X-Sync-Token", "")
        if not token or not hmac.compare_digest(token, SYNC_TOKEN):
            return jsonify({"erro": "token de sincronização inválido"}), 401

        return func(*args, **kwargs)

    return wrapper
