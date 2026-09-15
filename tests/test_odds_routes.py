import os
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, Mock, patch

os.environ.setdefault("SECRET_KEY", "segredo-de-teste-com-mais-de-32-bytes")

import jwt

from app import app


def _token():
    return jwt.encode({"sub": "7"}, os.environ["SECRET_KEY"], algorithm="HS256")


class OddsRoutesTest(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True)
        self.client = app.test_client()
        self.headers = {"Authorization": f"Bearer {_token()}"}

    def test_rotas_exigem_jwt(self):
        for url in ("/odds/status", "/odds/props", "/odds/mapeamentos/pendentes"):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 401)

    @patch("odds.routes.ODDSPAPI_API_KEY", "")
    @patch("odds.routes.conectar")
    def test_status_sem_configuracao_nao_acessa_banco(self, conectar):
        resposta = self.client.get("/odds/status", headers=self.headers)

        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(resposta.json["configurado"])
        self.assertEqual(resposta.json["status_ultima_sincronizacao"], "nao_configurado")
        self.assertNotIn("api_key", resposta.get_data(as_text=True).lower())
        conectar.assert_not_called()

    @patch("services.oddspapi.OddsPapiClient._get")
    @patch("odds.routes.ODDSPAPI_API_KEY", "configurada")
    @patch("odds.routes.conectar")
    def test_status_usa_somente_postgresql(self, conectar, chamada_externa):
        agora = datetime(2026, 10, 20, tzinfo=timezone.utc)
        conn = MagicMock()
        cursor = Mock()
        cursor.fetchone.side_effect = [
            (250, 12, 238, None, "ok"),
            (agora, "concluida"),
        ]
        conn.cursor.return_value.__enter__.return_value = cursor
        conectar.return_value = conn

        resposta = self.client.get("/odds/status", headers=self.headers)

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json["quota"]["restantes"], 238)
        chamada_externa.assert_not_called()

    @patch("odds.routes.conectar")
    def test_props_filtra_ativas_e_serializa_decimal(self, conectar):
        agora = datetime(2026, 10, 20, 18, 30, tzinfo=timezone.utc)
        conn = MagicMock()
        cursor = Mock()
        cursor.fetchall.return_value = [
            (10, "fixture-1", agora, "nba:2544", "LeBron James", "pontos",
             Decimal("25.5"), "over", Decimal("1.9"), "betano", agora)
        ]
        conn.cursor.return_value.__enter__.return_value = cursor
        conectar.return_value = conn

        resposta = self.client.get(
            "/odds/props?mercado=pontos&lado=over&somente_ativas=true",
            headers=self.headers,
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json["total"], 1)
        self.assertEqual(resposta.json["props"][0]["linha"], 25.5)
        sql = cursor.execute.call_args.args[0]
        self.assertIn("c.ativa = TRUE", sql)
        self.assertIn("capturada_em", sql)

    @patch("odds.routes.conectar")
    def test_lista_mapeamentos_pendentes(self, conectar):
        agora = datetime(2026, 10, 20, tzinfo=timezone.utc)
        conn = MagicMock()
        cursor = Mock()
        cursor.fetchall.return_value = [(1, "p-x", "Nome Desconhecido", "nome desconhecido", agora)]
        conn.cursor.return_value.__enter__.return_value = cursor
        conectar.return_value = conn

        resposta = self.client.get("/odds/mapeamentos/pendentes", headers=self.headers)

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json["total"], 1)
        self.assertNotIn("is_admin", cursor.execute.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
