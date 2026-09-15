from datetime import datetime, timedelta, timezone

from config import (
    ODDSPAPI_BOOKMAKERS,
    ODDSPAPI_FIXTURE_WINDOW_HOURS,
    ODDSPAPI_MARKETS_CACHE_HOURS,
    ODDSPAPI_SPORT_ID,
    ODDSPAPI_SYNC_COOLDOWN_MINUTES,
    ODDSPAPI_SYNC_MAX_REQUESTS,
    ODDSPAPI_TOURNAMENT_ID,
)
from database import conectar
from services.oddspapi import OddsPapiError, OddsPapiQuotaError, normalizar_quota
from services.odds_normalizacao import (
    MERCADOS_REAIS,
    fixture_elegivel,
    normalizar_catalogo_mercados,
    normalizar_fixtures,
    normalizar_odds,
)
from services.odds_storage import (
    PROVEDOR,
    catalogo_mercados,
    finalizar_sincronizacao,
    iniciar_sincronizacao,
    salvar_catalogo_mercados,
    salvar_evento,
    salvar_props_evento,
    salvar_status_quota,
)


LOCK_ID = 82973104


class OddsSyncError(Exception):
    codigo = "sincronizacao"


class OddsSyncBusyError(OddsSyncError):
    codigo = "sincronizacao_em_andamento"


class OddsSyncCooldownError(OddsSyncError):
    codigo = "cooldown"


class OddsSyncBudgetError(OddsSyncError):
    codigo = "limite_requisicoes"


def _adquirir_lock(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT pg_try_advisory_lock(%s)", (LOCK_ID,))
        if not cur.fetchone()[0]:
            raise OddsSyncBusyError("ja existe uma sincronizacao de odds em andamento")


def _liberar_lock(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_unlock(%s)", (LOCK_ID,))


def _validar_cooldown(conn, bookmaker, minutos):
    with conn.cursor() as cur:
        cur.execute(
            """SELECT iniciada_em
               FROM odds_sincronizacoes
               WHERE provedor = %s AND bookmaker = %s
                 AND status IN ('concluida', 'dry_run')
               ORDER BY iniciada_em DESC LIMIT 1""",
            (PROVEDOR, bookmaker),
        )
        linha = cur.fetchone()
    if linha and linha[0] > datetime.now(timezone.utc) - timedelta(minutes=minutos):
        raise OddsSyncCooldownError("sincronizacao em cooldown")


def sincronizar_odds(
    client,
    bookmaker=None,
    dry_run=False,
    max_eventos=None,
    mercados=None,
    max_requisicoes=ODDSPAPI_SYNC_MAX_REQUESTS,
    cooldown_minutos=ODDSPAPI_SYNC_COOLDOWN_MINUTES,
    janela_horas=ODDSPAPI_FIXTURE_WINDOW_HOURS,
    agora=None,
    output=None,
):
    bookmaker = (bookmaker or (ODDSPAPI_BOOKMAKERS[0] if ODDSPAPI_BOOKMAKERS else "betano")).lower()
    mercados = set(mercados or MERCADOS_REAIS)
    invalidos = mercados - set(MERCADOS_REAIS)
    if invalidos:
        raise OddsSyncError(f"mercados invalidos: {', '.join(sorted(invalidos))}")
    agora = agora or datetime.now(timezone.utc)
    fim_janela = agora + timedelta(hours=janela_horas)
    resumo = {
        "eventos_encontrados": 0,
        "eventos_consultados": 0,
        "props_recebidas": 0,
        "props_salvas": 0,
        "props_sem_jogador": 0,
        "requisicoes_estimadas": 0,
        "requisicoes_utilizadas": 0,
    }
    conn = conectar()
    sincronizacao_id = None
    lock_adquirido = False
    try:
        if hasattr(client, "definir_limite_requisicoes"):
            client.definir_limite_requisicoes(max_requisicoes)
        _adquirir_lock(conn)
        lock_adquirido = True
        _validar_cooldown(conn, bookmaker, cooldown_minutos)
        sincronizacao_id = iniciar_sincronizacao(conn, bookmaker)
        conn.commit()

        try:
            quota = normalizar_quota(client.account())
        except OddsPapiError as erro_conta:
            salvar_status_quota(conn, {}, status="falhou", erro=erro_conta)
            conn.commit()
            raise
        salvar_status_quota(conn, quota)
        conn.commit()
        if quota["restantes"] == 0:
            raise OddsPapiQuotaError("cota do provedor de odds esgotada")
        if (
            quota["restantes"] is not None
            and hasattr(client, "definir_limite_requisicoes")
        ):
            client.definir_limite_requisicoes(
                client.requisicoes_utilizadas + quota["restantes"]
            )

        catalogo = catalogo_mercados(
            conn, ODDSPAPI_SPORT_ID, ODDSPAPI_MARKETS_CACHE_HOURS
        )
        if not catalogo:
            catalogo_completo = normalizar_catalogo_mercados(
                client.markets(ODDSPAPI_SPORT_ID), ODDSPAPI_SPORT_ID
            )
            salvar_catalogo_mercados(conn, ODDSPAPI_SPORT_ID, catalogo_completo)
            conn.commit()
            catalogo = {
                item["provedor_market_id"]: item["mercado"]
                for item in catalogo_completo
                if item["mercado"]
            }

        fixtures = normalizar_fixtures(
            client.fixtures(agora.date(), fim_janela.date(), ODDSPAPI_TOURNAMENT_ID),
            ODDSPAPI_SPORT_ID,
            ODDSPAPI_TOURNAMENT_ID,
        )
        fixtures = [
            fixture
            for fixture in fixtures
            if fixture_elegivel(fixture, agora, fim_janela)
        ]
        resumo["eventos_encontrados"] = len(fixtures)
        for fixture in fixtures:
            fixture["evento_id"] = salvar_evento(conn, fixture)
        conn.commit()

        elegiveis = [fixture for fixture in fixtures if fixture["tem_odds"]]
        if max_eventos is not None:
            elegiveis = elegiveis[:max_eventos]
        resumo["requisicoes_estimadas"] = client.requisicoes_utilizadas + len(elegiveis)
        if output:
            output(
                f"Estimativa: {resumo['requisicoes_estimadas']} requisicoes; "
                f"{len(elegiveis)} eventos com odds."
            )
            for fixture in elegiveis:
                output(
                    "Evento previsto: "
                    f"{fixture['provedor_fixture_id']} | "
                    f"{fixture.get('time_casa') or '?'} x "
                    f"{fixture.get('time_fora') or '?'} | "
                    f"{fixture['inicio_em'].isoformat()}"
                )
        if resumo["requisicoes_estimadas"] > max_requisicoes:
            raise OddsSyncBudgetError("estimativa excede o limite de requisicoes")
        if (
            quota["restantes"] is not None
            and resumo["requisicoes_estimadas"] > quota["restantes"]
        ):
            raise OddsPapiQuotaError("cota restante insuficiente para a sincronizacao")

        if dry_run:
            resumo["requisicoes_utilizadas"] = client.requisicoes_utilizadas
            finalizar_sincronizacao(conn, sincronizacao_id, "dry_run", resumo)
            conn.commit()
            return resumo

        for fixture in elegiveis:
            payload = client.odds(fixture["provedor_fixture_id"], bookmaker)
            props = normalizar_odds(payload, bookmaker, catalogo, mercados)
            salvas, sem_jogador = salvar_props_evento(
                conn, fixture["evento_id"], bookmaker, props, agora
            )
            conn.commit()
            resumo["eventos_consultados"] += 1
            resumo["props_recebidas"] += len(props)
            resumo["props_salvas"] += salvas
            resumo["props_sem_jogador"] += sem_jogador

        resumo["requisicoes_utilizadas"] = client.requisicoes_utilizadas
        finalizar_sincronizacao(conn, sincronizacao_id, "concluida", resumo)
        conn.commit()
        return resumo
    except Exception as erro:
        conn.rollback()
        if sincronizacao_id is not None:
            resumo["requisicoes_utilizadas"] = client.requisicoes_utilizadas
            finalizar_sincronizacao(conn, sincronizacao_id, "falhou", resumo, erro)
            conn.commit()
        raise
    finally:
        if lock_adquirido:
            _liberar_lock(conn)
        conn.close()
