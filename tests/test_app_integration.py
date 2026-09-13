import unittest

from app import app


class AppIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_health(self):
        resposta = self.client.get("/health")

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.get_json(), {"status": "ok"})

    def test_cors_para_frontend_local(self):
        resposta = self.client.options(
            "/jogadores",
            headers={
                "Origin": "http://localhost:8080",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(
            resposta.headers.get("Access-Control-Allow-Origin"),
            "http://localhost:8080",
        )
        self.assertIn("Authorization", resposta.headers.get("Access-Control-Allow-Headers", ""))

    def test_cors_nao_libera_origem_desconhecida(self):
        resposta = self.client.get(
            "/health",
            headers={"Origin": "https://site-nao-configurado.example"},
        )

        self.assertIsNone(resposta.headers.get("Access-Control-Allow-Origin"))

    def test_cors_libera_frontend_oficial(self):
        resposta = self.client.options(
            "/analises",
            headers={
                "Origin": "https://nba-prop-insights.vercel.app",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(
            resposta.headers.get("Access-Control-Allow-Origin"),
            "https://nba-prop-insights.vercel.app",
        )


if __name__ == "__main__":
    unittest.main()
