import os
import unittest
from datetime import date
from unittest.mock import Mock, patch

os.environ.setdefault("SECRET_KEY", "segredo-de-teste-com-mais-de-32-bytes")

import jwt

from app import app


def _token(is_admin=False):
    return jwt.encode(
        {"sub": "teste", "is_admin": is_admin},
        os.environ["SECRET_KEY"],
        algorithm="HS256",
    )


class NBARoutesTest(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True)
        self.client = app.test_client()

    @patch("jogadores.routes.buscar_jogos")
    @patch("jogadores.routes.conectar")
    def test_consulta_direta_retorna_estatisticas(self, conectar, buscar_jogos):
        cursor = Mock()
        cursor.fetchone.return_value = ("jamesle01", "LeBron James", 2544)
        conectar.return_value.cursor.return_value = cursor
        buscar_jogos.return_value = {
            "jogador": {"id": 2544, "nome": "LeBron James", "ativo": True},
            "temporada": "2025-26",
            "tipo_temporada": "Regular Season",
            "jogos": [
                {
                    "game_id": "001",
                    "data": date(2025, 10, 21),
                    "adversario": "LAL vs. GSW",
                    "pontos": 20,
                },
                {
                    "game_id": "002",
                    "data": date(2025, 10, 23),
                    "adversario": "LAL @ MIN",
                    "pontos": 30,
                },
            ],
        }

        resposta = self.client.get(
            "/jogadores/jamesle01/nba?temporada=2025-26",
            headers={"Authorization": f"Bearer {_token()}"},
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json["pontos"], [20, 30])
        self.assertEqual(resposta.json["media"], 25)
        self.assertEqual(resposta.json["jogos"], 2)
        self.assertEqual(resposta.json["partidas"][0]["data"], "2025-10-21")

    @patch("jogadores.routes.buscar_jogadores_nba")
    def test_busca_jogadores_no_catalogo_completo(self, buscar_jogadores):
        buscar_jogadores.return_value = [
            {"id": "nba:203999", "nome": "Nikola Jokić", "ativo": True}
        ]

        resposta = self.client.get(
            "/jogadores?busca=jokic",
            headers={"Authorization": f"Bearer {_token()}"},
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json[0]["id"], "nba:203999")
        buscar_jogadores.assert_called_once_with("jokic")

    @patch("jogadores.routes.buscar_jogos")
    @patch("jogadores.routes.conectar")
    def test_sincronizacao_faz_upsert_por_game_id(self, conectar, buscar_jogos):
        conn = Mock()
        cursor = Mock()
        cursor.fetchone.return_value = ("jamesle01", "LeBron James", None)
        conn.cursor.return_value = cursor
        conectar.return_value = conn
        buscar_jogos.return_value = {
            "jogador": {"id": 2544, "nome": "LeBron James", "ativo": True},
            "temporada": "2025-26",
            "tipo_temporada": "Regular Season",
            "jogos": [
                {
                    "game_id": "001",
                    "data": date(2025, 10, 21),
                    "adversario": "LAL vs. GSW",
                    "pontos": 20,
                }
            ],
        }

        resposta = self.client.post(
            "/jogadores/jamesle01/sincronizar",
            json={"temporada": "2025-26"},
            headers={"Authorization": f"Bearer {_token(is_admin=True)}"},
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json["jogos_sincronizados"], 1)
        conn.commit.assert_called_once()
        comandos = [execucao.args[0] for execucao in cursor.execute.call_args_list]
        self.assertTrue(any("ON CONFLICT (id_jogador, game_id)" in sql for sql in comandos))

    @patch("jogadores.routes.conectar")
    def test_cadastro_de_jogador_retorna_id_compativel_com_frontend(self, conectar):
        conn = Mock()
        cursor = Mock()
        cursor.fetchone.return_value = None
        conn.cursor.return_value = cursor
        conectar.return_value = conn

        resposta = self.client.post(
            "/jogadores",
            json={"nome": "LeBron James"},
            headers={"Authorization": f"Bearer {_token(is_admin=True)}"},
        )

        self.assertEqual(resposta.status_code, 201)
        self.assertEqual(resposta.json["id"], resposta.json["code"])
        self.assertEqual(resposta.json["nome"], "LeBron James")


if __name__ == "__main__":
    unittest.main()
