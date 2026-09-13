import os
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, Mock, patch

os.environ.setdefault("SECRET_KEY", "segredo-de-teste-com-mais-de-32-bytes")

import jwt

from app import app


def _token(usuario_id):
    return jwt.encode(
        {"sub": str(usuario_id)},
        os.environ["SECRET_KEY"],
        algorithm="HS256",
    )


def _partidas():
    return {
        "jogos": [{
            "game_id": "002",
            "data": "2026-01-02",
            "adversario": "LAL vs. GSW",
            "pontos": 20,
            "assistencias": 8,
            "rebotes": 10,
            "cestas_3": 3,
            "tentativas_3": 7,
        }]
    }


class AnalisesRoutesTest(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True)
        self.client = app.test_client()
        self.headers = {"Authorization": f"Bearer {_token(7)}"}

    @patch("analises.routes.conectar")
    @patch("analises.routes._buscar_jogos_salvos", return_value=_partidas())
    @patch(
        "analises.routes._buscar_jogador",
        return_value=("nba:2544", "LeBron James", 2544),
    )
    def test_cria_e_salva_snapshot_com_decimal(
        self, _buscar_jogador, _buscar_jogos, conectar
    ):
        agora = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)
        conn = MagicMock()
        cursor = Mock()
        cursor.fetchone.return_value = (31, agora, agora)
        conn.cursor.return_value.__enter__.return_value = cursor
        conectar.return_value = conn

        resposta = self.client.post(
            "/analises",
            headers=self.headers,
            json={
                "jogador_id": "nba:2544",
                "temporada": "2025-26",
                "tipo_temporada": "Todos",
                "mercado": "par",
                "quantidade_jogos": 5,
                "linha": "35.5",
                "odd": "1.90",
                "lado": "over",
            },
        )

        self.assertEqual(resposta.status_code, 201)
        self.assertEqual(resposta.json["id"], 31)
        self.assertEqual(resposta.json["media"], 38)
        self.assertEqual(resposta.json["acertos"], 1)
        parametros = cursor.execute.call_args.args[1]
        self.assertEqual(parametros[0], 7)
        self.assertEqual(parametros[8], Decimal("35.5"))
        self.assertEqual(parametros[9], Decimal("1.90"))
        conn.commit.assert_called_once()

    @patch("analises.routes.conectar")
    def test_lista_somente_analises_do_usuario_autenticado(self, conectar):
        agora = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)
        linha = (
            31, 7, "nba:2544", 2544, "LeBron James", "2025-26", "Todos",
            "pontos", "10", Decimal("24.50"), Decimal("1.900"), "over",
            {"media": 27, "partidas": []}, agora, agora,
        )
        conn = MagicMock()
        cursor = Mock()
        cursor.fetchall.return_value = [linha]
        conn.cursor.return_value.__enter__.return_value = cursor
        conectar.return_value = conn

        resposta = self.client.get("/analises", headers=self.headers)

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json[0]["usuario_id"], 7)
        self.assertEqual(resposta.json[0]["quantidade_jogos"], 10)
        self.assertEqual(cursor.execute.call_args.args[1], (7,))

    @patch("analises.routes.conectar")
    def test_nao_abre_analise_de_outro_usuario(self, conectar):
        conn = MagicMock()
        cursor = Mock()
        cursor.fetchone.return_value = None
        conn.cursor.return_value.__enter__.return_value = cursor
        conectar.return_value = conn

        resposta = self.client.get("/analises/99", headers=self.headers)

        self.assertEqual(resposta.status_code, 404)
        self.assertEqual(resposta.json, {"erro": "analise nao encontrada"})
        self.assertEqual(cursor.execute.call_args.args[1], (99, 7))

    @patch("analises.routes.conectar")
    def test_apaga_somente_analise_do_usuario(self, conectar):
        conn = MagicMock()
        cursor = Mock()
        cursor.fetchone.return_value = (31,)
        conn.cursor.return_value.__enter__.return_value = cursor
        conectar.return_value = conn

        resposta = self.client.delete("/analises/31", headers=self.headers)

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json, {"mensagem": "analise apagada"})
        self.assertEqual(cursor.execute.call_args.args[1], (31, 7))
        conn.commit.assert_called_once()

    def test_rejeita_mercado_temporada_linha_e_odd_invalidos(self):
        base = {
            "jogador_id": "nba:2544",
            "temporada": "2025-26",
            "mercado": "pontos",
            "quantidade_jogos": 5,
            "linha": 20.5,
            "odd": 1.9,
            "lado": "over",
        }
        casos = (
            ({"mercado": "gols"}, "mercado invalido"),
            ({"temporada": "2024-25"}, "temporada invalida"),
            ({"linha": -1}, "linha invalida"),
            ({"odd": 1}, "odd invalida"),
            ({"quantidade_jogos": 3}, "quantidade de jogos invalida"),
        )
        for alteracao, mensagem in casos:
            with self.subTest(alteracao=alteracao):
                resposta = self.client.post(
                    "/analises",
                    headers=self.headers,
                    json={**base, **alteracao},
                )
                self.assertEqual(resposta.status_code, 422)
                self.assertEqual(resposta.json["erro"], mensagem)

    def test_rejeita_token_invalido(self):
        resposta = self.client.get(
            "/analises", headers={"Authorization": "Bearer token-invalido"}
        )

        self.assertEqual(resposta.status_code, 401)
        self.assertEqual(
            resposta.json, {"erro": "token invalido ou expirado"}
        )


if __name__ == "__main__":
    unittest.main()
