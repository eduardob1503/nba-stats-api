import time
from datetime import datetime, timezone

import requests

from config import (
    ODDSPAPI_API_KEY,
    ODDSPAPI_BASE_URL,
    ODDSPAPI_BOOKMAKERS,
    ODDSPAPI_SPORT_ID,
    ODDSPAPI_TIMEOUT,
    ODDSPAPI_TOURNAMENT_ID,
)


class OddsPapiError(Exception):
    codigo = "oddspapi_erro"


class OddsPapiConfigError(OddsPapiError):
    codigo = "configuracao_ausente"


class OddsPapiAuthenticationError(OddsPapiError):
    codigo = "autenticacao"


class OddsPapiQuotaError(OddsPapiError):
    codigo = "cota_esgotada"


class OddsPapiUnavailableError(OddsPapiError):
    codigo = "indisponivel"


class OddsPapiResponseError(OddsPapiError):
    codigo = "resposta_invalida"


class OddsPapiClient:
    def __init__(
        self,
        api_key=None,
        base_url=ODDSPAPI_BASE_URL,
        timeout=ODDSPAPI_TIMEOUT,
        http_client=None,
        max_tentativas=3,
        limite_requisicoes=None,
        sleep=None,
    ):
        self.api_key = ODDSPAPI_API_KEY if api_key is None else str(api_key).strip()
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.http_client = http_client or requests.Session()
        self.max_tentativas = max(1, int(max_tentativas))
        self.limite_requisicoes = limite_requisicoes
        self.sleep = sleep or time.sleep
        self.requisicoes_utilizadas = 0

    def _get(self, caminho, parametros=None):
        if not self.api_key:
            raise OddsPapiConfigError("ODDSPAPI_API_KEY nao configurada")

        params = dict(parametros or {})
        params["apiKey"] = self.api_key
        for tentativa in range(1, self.max_tentativas + 1):
            if (
                self.limite_requisicoes is not None
                and self.requisicoes_utilizadas >= self.limite_requisicoes
            ):
                raise OddsPapiQuotaError("limite local de requisicoes atingido")
            self.requisicoes_utilizadas += 1
            try:
                resposta = self.http_client.get(
                    f"{self.base_url}/{caminho.lstrip('/')}",
                    params=params,
                    timeout=self.timeout,
                )
            except (requests.RequestException, TimeoutError) as erro:
                if tentativa == self.max_tentativas:
                    raise OddsPapiUnavailableError(
                        "provedor de odds indisponivel"
                    ) from erro
                self.sleep(min(tentativa, 2))
                continue

            if resposta.status_code in (401, 403):
                raise OddsPapiAuthenticationError(
                    "credenciais do provedor de odds rejeitadas"
                )
            if resposta.status_code == 429:
                raise OddsPapiQuotaError("cota do provedor de odds esgotada")
            if resposta.status_code == 404:
                raise OddsPapiResponseError("recurso nao encontrado no provedor de odds")
            if resposta.status_code >= 500:
                if tentativa == self.max_tentativas:
                    raise OddsPapiUnavailableError(
                        "provedor de odds temporariamente indisponivel"
                    )
                self.sleep(min(tentativa, 2))
                continue
            if resposta.status_code >= 400:
                raise OddsPapiResponseError("provedor de odds rejeitou a requisicao")

            try:
                payload = resposta.json()
            except (TypeError, ValueError) as erro:
                raise OddsPapiResponseError(
                    "provedor de odds retornou JSON invalido"
                ) from erro
            if not isinstance(payload, (dict, list)):
                raise OddsPapiResponseError("provedor de odds retornou resposta invalida")
            return payload

        raise OddsPapiUnavailableError("provedor de odds indisponivel")

    def definir_limite_requisicoes(self, limite):
        limite = max(0, int(limite))
        if self.limite_requisicoes is None:
            self.limite_requisicoes = limite
        else:
            self.limite_requisicoes = min(self.limite_requisicoes, limite)

    def account(self):
        return self._get("account")

    def markets(self, sport_id=ODDSPAPI_SPORT_ID):
        return self._get("markets", {"sportId": int(sport_id)})

    def fixtures(self, data_inicial, data_final, tournament_id=ODDSPAPI_TOURNAMENT_ID):
        return self._get(
            "fixtures",
            {
                "tournamentId": int(tournament_id),
                "from": data_inicial.isoformat(),
                "to": data_final.isoformat(),
            },
        )

    def odds(self, fixture_id, bookmaker=None):
        bookmaker = bookmaker or (ODDSPAPI_BOOKMAKERS[0] if ODDSPAPI_BOOKMAKERS else "betano")
        return self._get(
            "odds",
            {"fixtureId": str(fixture_id), "bookmakers": bookmaker},
        )


def _buscar_valor(payload, nomes):
    if isinstance(payload, dict):
        for chave, valor in payload.items():
            if chave.casefold() in nomes and valor not in (None, ""):
                return valor
        for valor in payload.values():
            encontrado = _buscar_valor(valor, nomes)
            if encontrado not in (None, ""):
                return encontrado
    elif isinstance(payload, list):
        for item in payload:
            encontrado = _buscar_valor(item, nomes)
            if encontrado not in (None, ""):
                return encontrado
    return None


def normalizar_quota(payload):
    def inteiro(nomes):
        valor = _buscar_valor(payload, nomes)
        try:
            return int(valor) if valor is not None else None
        except (TypeError, ValueError):
            return None

    limite = inteiro({"limit", "monthlylimit", "monthly_limit", "requestlimit"})
    utilizadas = inteiro({"used", "requestsused", "requests_used", "usage"})
    restantes = inteiro({"remaining", "requestsremaining", "requests_remaining"})
    if restantes is None and limite is not None and utilizadas is not None:
        restantes = max(limite - utilizadas, 0)
    renovacao = _buscar_valor(
        payload, {"renewsat", "renews_at", "resetat", "reset_at", "renewaldate"}
    )
    if renovacao not in (None, ""):
        try:
            if isinstance(renovacao, (int, float)) or str(renovacao).isdigit():
                timestamp = float(renovacao)
                if timestamp > 10_000_000_000:
                    timestamp /= 1000
                renovacao = datetime.fromtimestamp(timestamp, tz=timezone.utc)
            elif not isinstance(renovacao, datetime):
                renovacao = datetime.fromisoformat(
                    str(renovacao).strip().replace("Z", "+00:00")
                )
            if renovacao.tzinfo is None:
                renovacao = renovacao.replace(tzinfo=timezone.utc)
        except (OverflowError, TypeError, ValueError):
            renovacao = None
    return {
        "limite": limite,
        "utilizadas": utilizadas,
        "restantes": restantes,
        "renova_em": renovacao,
    }
