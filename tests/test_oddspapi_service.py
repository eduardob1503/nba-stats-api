import unittest
from unittest.mock import Mock

import requests

from services.oddspapi import (
    OddsPapiAuthenticationError,
    OddsPapiClient,
    OddsPapiConfigError,
    OddsPapiQuotaError,
    OddsPapiResponseError,
    OddsPapiUnavailableError,
    normalizar_quota,
)


class RespostaFalsa:
    def __init__(self, status_code=200, payload=None, erro_json=None):
        self.status_code = status_code
        self.payload = payload
        self.erro_json = erro_json

    def json(self):
        if self.erro_json:
            raise self.erro_json
        return self.payload


class HttpFalso:
    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.chamadas = []

    def get(self, url, params, timeout):
        self.chamadas.append((url, params, timeout))
        resposta = self.respostas.pop(0)
        if isinstance(resposta, Exception):
            raise resposta
        return resposta


class OddsPapiServiceTest(unittest.TestCase):
    def test_configuracao_ausente_e_tratada_sem_expor_chave(self):
        client = OddsPapiClient(api_key="", http_client=HttpFalso([]))
        with self.assertRaises(OddsPapiConfigError) as contexto:
            client.account()
        self.assertNotIn("apiKey", str(contexto.exception))

    def test_consulta_conta_e_normaliza_quota(self):
        http = HttpFalso([
            RespostaFalsa(200, {"plan": {"monthlyLimit": 250, "requestsUsed": 12}})
        ])
        client = OddsPapiClient(api_key="segredo", http_client=http)

        quota = normalizar_quota(client.account())

        self.assertEqual(quota, {
            "limite": 250,
            "utilizadas": 12,
            "restantes": 238,
            "renova_em": None,
        })
        self.assertEqual(http.chamadas[0][1]["apiKey"], "segredo")

    def test_normaliza_data_de_renovacao_sem_aceitar_valor_invalido(self):
        quota = normalizar_quota({"limit": 250, "used": 1, "resetAt": "2026-11-01T00:00:00Z"})
        self.assertEqual(quota["renova_em"].year, 2026)
        self.assertIsNone(normalizar_quota({"resetAt": "nao-e-data"})["renova_em"])

    def test_401_e_403_geram_erro_de_autenticacao_sem_chave(self):
        for status in (401, 403):
            with self.subTest(status=status):
                client = OddsPapiClient(
                    api_key="chave-super-secreta",
                    http_client=HttpFalso([RespostaFalsa(status, {})]),
                )
                with self.assertRaises(OddsPapiAuthenticationError) as contexto:
                    client.account()
                self.assertNotIn("chave-super-secreta", str(contexto.exception))

    def test_429_nao_e_repetido(self):
        http = HttpFalso([RespostaFalsa(429, {})])
        client = OddsPapiClient(api_key="segredo", http_client=http, max_tentativas=3)

        with self.assertRaises(OddsPapiQuotaError):
            client.account()

        self.assertEqual(len(http.chamadas), 1)
        self.assertEqual(client.requisicoes_utilizadas, 1)

    def test_5xx_e_timeout_possuem_tentativas_limitadas(self):
        sleep = Mock()
        http_5xx = HttpFalso([
            RespostaFalsa(500, {}),
            RespostaFalsa(503, {}),
            RespostaFalsa(200, {"ok": True}),
        ])
        client = OddsPapiClient(
            api_key="segredo", http_client=http_5xx, max_tentativas=3, sleep=sleep
        )
        self.assertEqual(client.account(), {"ok": True})
        self.assertEqual(len(http_5xx.chamadas), 3)

        http_timeout = HttpFalso([requests.Timeout(), requests.Timeout()])
        client = OddsPapiClient(
            api_key="segredo", http_client=http_timeout, max_tentativas=2, sleep=sleep
        )
        with self.assertRaises(OddsPapiUnavailableError):
            client.account()
        self.assertEqual(len(http_timeout.chamadas), 2)

    def test_404_e_json_invalido_geram_resposta_invalida(self):
        casos = (
            RespostaFalsa(404, {}),
            RespostaFalsa(200, erro_json=ValueError("invalido")),
            RespostaFalsa(200, payload="texto"),
        )
        for resposta in casos:
            with self.subTest(resposta=resposta.status_code):
                client = OddsPapiClient(
                    api_key="segredo", http_client=HttpFalso([resposta])
                )
                with self.assertRaises(OddsPapiResponseError):
                    client.account()

    def test_metodos_constroem_parametros_sem_colocar_chave_na_url(self):
        http = HttpFalso([RespostaFalsa(200, [])])
        client = OddsPapiClient(
            api_key="segredo", base_url="https://api.example/v4", http_client=http
        )

        client.odds("fixture-1", "betano")

        url, params, _ = http.chamadas[0]
        self.assertEqual(url, "https://api.example/v4/odds")
        self.assertNotIn("segredo", url)
        self.assertEqual(params["fixtureId"], "fixture-1")
        self.assertEqual(params["bookmakers"], "betano")

    def test_limite_local_tambem_bloqueia_retries(self):
        http = HttpFalso([RespostaFalsa(500, {}), RespostaFalsa(200, {})])
        client = OddsPapiClient(
            api_key="segredo",
            http_client=http,
            max_tentativas=3,
            limite_requisicoes=1,
            sleep=Mock(),
        )

        with self.assertRaises(OddsPapiQuotaError):
            client.account()
        self.assertEqual(len(http.chamadas), 1)


if __name__ == "__main__":
    unittest.main()
