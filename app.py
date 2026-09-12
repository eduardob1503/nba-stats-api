#objetivo - Criar uma api de disponibilize a consulta e retorne stats do jogador
from flask import Flask, jsonify, request
from auths.routes import auth_bp
from config import AUTO_MIGRATE, CORS_ORIGINS
from jogadores.routes import jogadores_bp
from sync_data.routes import sync_bp


if AUTO_MIGRATE:
    from migrate import executar_migracoes

    executar_migracoes()


app = Flask(__name__)
app.register_blueprint(jogadores_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(sync_bp)


@app.after_request
def adicionar_cors(resposta):
    origem = request.headers.get("Origin", "").rstrip("/")
    if origem and ("*" in CORS_ORIGINS or origem in CORS_ORIGINS):
        resposta.headers["Access-Control-Allow-Origin"] = origem
        resposta.headers.add("Vary", "Origin")
        resposta.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
        resposta.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
    return resposta


@app.get("/health")
def health():
    return jsonify({"status": "ok"}), 200




if __name__ == "__main__":
    app.run(host="0.0.0.0",port ="5000",debug=True)
