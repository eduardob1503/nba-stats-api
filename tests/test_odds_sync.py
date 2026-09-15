import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from services.odds_sync import (
    OddsSyncBudgetError,
    OddsSyncBusyError,
    OddsSyncCooldownError,
    sincronizar_odds,
)


FIXTURES = Path(__file__).parent / "fixtures"


class ClientFalso:
    def __init__(self):
        self.requisicoes_utilizadas = 0
        self.odds_chamadas = 0

    def account(self):
        self.requisicoes_utilizadas += 1
        return {"monthlyLimit": 250, "requestsUsed": 10, "remaining": 240}

    def fixtures(self, inicio, fim, tournament_id):
        self.requisicoes_utilizadas += 1
        return json.loads(
            (FIXTURES / "oddspapi_fixtures.json").read_text(encoding="utf-8")
        )

    def markets(self, sport_id):
        self.requisicoes_utilizadas += 1
        return json.loads(
            (FIXTURES / "oddspapi_markets.json").read_text(encoding="utf-8")
        )

    def odds(self, fixture_id, bookmaker):
        self.requisicoes_utilizadas += 1
        self.odds_chamadas += 1
        return json.loads(
            (FIXTURES / "oddspapi_odds.json").read_text(encoding="utf-8")
        )


class ClientSemCota(ClientFalso):
    def account(self):
        self.requisicoes_utilizadas += 1
        return {"monthlyLimit": 250, "requestsUsed": 250, "remaining": 0}


class OddsSyncTest(unittest.TestCase):
    @patch("services.odds_sync.conectar")
    def test_bloqueia_sincronizacoes_concorrentes(self, conectar):
        conn = MagicMock()
        cursor = Mock()
        cursor.fetchone.return_value = (False,)
        conn.cursor.return_value.__enter__.return_value = cursor
        conectar.return_value = conn

        with self.assertRaises(OddsSyncBusyError):
            sincronizar_odds(ClientFalso())

    @patch("services.odds_sync._liberar_lock")
    @patch("services.odds_sync._validar_cooldown", side_effect=OddsSyncCooldownError("cooldown"))
    @patch("services.odds_sync._adquirir_lock")
    @patch("services.odds_sync.conectar", return_value=MagicMock())
    def test_respeita_cooldown(self, conectar, adquirir, validar, liberar):
        client = ClientFalso()
        with self.assertRaises(OddsSyncCooldownError):
            sincronizar_odds(client)
        self.assertEqual(client.requisicoes_utilizadas, 0)
        liberar.assert_called_once()

    @patch("services.odds_sync.finalizar_sincronizacao")
    @patch("services.odds_sync.salvar_evento", return_value=10)
    @patch("services.odds_sync.salvar_status_quota")
    @patch("services.odds_sync.catalogo_mercados", return_value={"m-points": "pontos"})
    @patch("services.odds_sync.iniciar_sincronizacao", return_value=1)
    @patch("services.odds_sync._validar_cooldown")
    @patch("services.odds_sync._liberar_lock")
    @patch("services.odds_sync._adquirir_lock")
    @patch("services.odds_sync.conectar", return_value=MagicMock())
    def test_dry_run_estima_sem_consultar_odds(
        self, conectar, adquirir, liberar, cooldown, iniciar, catalogo,
        status, evento, finalizar
    ):
        client = ClientFalso()
        mensagens = []
        resumo = sincronizar_odds(
            client,
            dry_run=True,
            agora=datetime(2026, 10, 20, 12, tzinfo=timezone.utc),
            output=mensagens.append,
        )

        self.assertEqual(client.odds_chamadas, 0)
        self.assertEqual(resumo["requisicoes_estimadas"], 3)
        self.assertIn("Estimativa", mensagens[0])
        self.assertIn("fixture-1", mensagens[1])
        self.assertEqual(finalizar.call_args.args[2], "dry_run")

    @patch("services.odds_sync.finalizar_sincronizacao")
    @patch("services.odds_sync.salvar_evento", return_value=10)
    @patch("services.odds_sync.salvar_status_quota")
    @patch("services.odds_sync.catalogo_mercados", return_value={"m-points": "pontos"})
    @patch("services.odds_sync.iniciar_sincronizacao", return_value=1)
    @patch("services.odds_sync._validar_cooldown")
    @patch("services.odds_sync._liberar_lock")
    @patch("services.odds_sync._adquirir_lock")
    @patch("services.odds_sync.conectar", return_value=MagicMock())
    def test_recusa_estimativa_acima_do_limite(
        self, conectar, adquirir, liberar, cooldown, iniciar, catalogo,
        status, evento, finalizar
    ):
        with self.assertRaises(OddsSyncBudgetError):
            sincronizar_odds(
                ClientFalso(),
                max_requisicoes=2,
                agora=datetime(2026, 10, 20, 12, tzinfo=timezone.utc),
            )
        self.assertEqual(finalizar.call_args.args[2], "falhou")

    @patch("services.odds_sync.finalizar_sincronizacao")
    @patch("services.odds_sync.salvar_status_quota")
    @patch("services.odds_sync.iniciar_sincronizacao", return_value=1)
    @patch("services.odds_sync._validar_cooldown")
    @patch("services.odds_sync._liberar_lock")
    @patch("services.odds_sync._adquirir_lock")
    @patch("services.odds_sync.conectar", return_value=MagicMock())
    def test_interrompe_quando_cota_esta_esgotada(
        self, conectar, adquirir, liberar, cooldown, iniciar, status, finalizar
    ):
        from services.oddspapi import OddsPapiQuotaError

        with self.assertRaises(OddsPapiQuotaError):
            sincronizar_odds(ClientSemCota())
        self.assertEqual(finalizar.call_args.args[2], "falhou")


if __name__ == "__main__":
    unittest.main()
