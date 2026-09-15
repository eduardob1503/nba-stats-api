import os
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", "segredo-de-teste-com-mais-de-32-bytes")

import jwt

from app import app


def _token():
    return jwt.encode({"sub": "7"}, os.environ["SECRET_KEY"], algorithm="HS256")


URL = (
    "/oportunidades/ev-reais?temporada=2025-26&tipo_temporada=Regular%20Season"
    "&mercado=pontos&lado=over&quantidade_jogos=5&minimo_jogos=5"
    "&bookmaker=betano&limite=20"
)


class OportunidadesReaisRoutesTest(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True)
        self.client = app.test_client()
        self.headers = {"Authorization": f"Bearer {_token()}"}

    def test_exige_autenticacao(self):
        self.assertEqual(self.client.get(URL).status_code, 401)

    @patch("oportunidades.routes._buscar_dados_ev_reais", return_value=([], {}))
    def test_sem_odds_retorna_200(self, buscar):
        resposta = self.client.get(URL, headers=self.headers)

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json["status"], "sem_odds")
        self.assertEqual(resposta.json["oportunidades"], [])

    @patch("services.oddspapi.OddsPapiClient._get")
    @patch("oportunidades.routes._buscar_dados_ev_reais")
    def test_usa_linha_odd_reais_sem_api_externa(self, buscar, externa):
        agora = datetime(2026, 10, 20, tzinfo=timezone.utc)
        cotacao = {
            "evento_id": 10,
            "provedor_fixture_id": "fixture-1",
            "inicio_em": "2026-10-21T00:30:00Z",
            "time_casa": "Lakers",
            "time_fora": "Warriors",
            "jogador_id": "nba:2544",
            "jogador_nome": "LeBron James",
            "mercado": "pontos",
            "linha": Decimal("25.5"),
            "lado": "over",
            "odd": Decimal("1.9"),
            "bookmaker": "betano",
            "capturada_em": agora.isoformat(),
        }
        historico = {2544: [{"pontos": valor} for valor in (30, 29, 28, 20, 18)]}
        buscar.return_value = ([cotacao], historico)

        resposta = self.client.get(URL, headers=self.headers)

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json["total"], 1)
        self.assertEqual(resposta.json["oportunidades"][0]["linha"], 25.5)
        self.assertEqual(resposta.json["oportunidades"][0]["odd"], 1.9)
        externa.assert_not_called()

    @patch("oportunidades.routes._buscar_dados_ev_reais")
    def test_cotacao_sem_historico_nba_retorna_lista_vazia(self, buscar):
        buscar.return_value = ([{
            "evento_id": 10,
            "provedor_fixture_id": "fixture-1",
            "inicio_em": "2026-10-21T00:30:00Z",
            "time_casa": "Lakers",
            "time_fora": "Warriors",
            "jogador_id": "nba:2544",
            "jogador_nome": "LeBron James",
            "mercado": "pontos",
            "linha": Decimal("25.5"),
            "lado": "over",
            "odd": Decimal("1.9"),
            "bookmaker": "betano",
            "capturada_em": "2026-10-20T18:30:00Z",
        }], {})

        resposta = self.client.get(URL, headers=self.headers)

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json["total"], 0)
        self.assertEqual(resposta.json["oportunidades"], [])

    def test_rejeita_tentativas_de_tres_como_prop_inventada(self):
        resposta = self.client.get(
            URL.replace("mercado=pontos", "mercado=tentativas_3"),
            headers=self.headers,
        )
        self.assertEqual(resposta.status_code, 422)
        self.assertEqual(resposta.json["erro"], "mercado sem prop real")


if __name__ == "__main__":
    unittest.main()
