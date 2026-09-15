from datetime import datetime, timezone

from psycopg2.extras import Json, execute_values

from services.odds_normalizacao import normalizar_nome_jogador


PROVEDOR = "oddspapi"


def salvar_status_quota(conn, quota, status="ok", erro=None):
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO odds_provedor_status
                   (provedor, limite_mensal, requisicoes_utilizadas,
                    requisicoes_restantes, renova_em, verificado_em,
                    status_ultima_verificacao, erro_codigo, erro_mensagem_segura)
               VALUES (%s, %s, %s, %s, %s, NOW(), %s, %s, %s)
               ON CONFLICT (provedor) DO UPDATE SET
                   limite_mensal = EXCLUDED.limite_mensal,
                   requisicoes_utilizadas = EXCLUDED.requisicoes_utilizadas,
                   requisicoes_restantes = EXCLUDED.requisicoes_restantes,
                   renova_em = EXCLUDED.renova_em,
                   verificado_em = EXCLUDED.verificado_em,
                   status_ultima_verificacao = EXCLUDED.status_ultima_verificacao,
                   erro_codigo = EXCLUDED.erro_codigo,
                   erro_mensagem_segura = EXCLUDED.erro_mensagem_segura""",
            (
                PROVEDOR,
                quota.get("limite"),
                quota.get("utilizadas"),
                quota.get("restantes"),
                quota.get("renova_em"),
                status,
                getattr(erro, "codigo", None),
                str(erro) if erro else None,
            ),
        )


def catalogo_mercados(conn, sport_id, validade_horas):
    with conn.cursor() as cur:
        cur.execute(
            """SELECT provedor_market_id, mercado
               FROM odds_mercados_catalogo
               WHERE provedor = %s AND sport_id = %s
                 AND consultado_em >= NOW() - (%s * INTERVAL '1 hour')""",
            (PROVEDOR, sport_id, validade_horas),
        )
        linhas = cur.fetchall()
    return {str(linha[0]): linha[1] for linha in linhas if linha[1]}


def salvar_catalogo_mercados(conn, sport_id, catalogo):
    if not catalogo:
        return
    with conn.cursor() as cur:
        execute_values(
            cur,
            """INSERT INTO odds_mercados_catalogo
                   (provedor, sport_id, provedor_market_id, nome_provedor,
                    mercado, player_prop, payload, consultado_em)
               VALUES %s
               ON CONFLICT (provedor, sport_id, provedor_market_id) DO UPDATE SET
                   nome_provedor = EXCLUDED.nome_provedor,
                   mercado = EXCLUDED.mercado,
                   player_prop = EXCLUDED.player_prop,
                   payload = EXCLUDED.payload,
                   consultado_em = EXCLUDED.consultado_em""",
            [
                (
                    PROVEDOR,
                    sport_id,
                    item["provedor_market_id"],
                    item["nome_provedor"],
                    item["mercado"],
                    item["player_prop"],
                    Json(item["payload"]),
                    datetime.now(timezone.utc),
                )
                for item in catalogo
            ],
        )


def salvar_evento(conn, fixture):
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO odds_eventos
                   (provedor, provedor_fixture_id, sport_id, tournament_id,
                    time_casa, time_fora, inicio_em, status, tem_odds)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (provedor, provedor_fixture_id) DO UPDATE SET
                   sport_id = EXCLUDED.sport_id,
                   tournament_id = EXCLUDED.tournament_id,
                   time_casa = EXCLUDED.time_casa,
                   time_fora = EXCLUDED.time_fora,
                   inicio_em = EXCLUDED.inicio_em,
                   status = EXCLUDED.status,
                   tem_odds = EXCLUDED.tem_odds,
                   atualizado_em = NOW()
               RETURNING id""",
            (
                PROVEDOR,
                fixture["provedor_fixture_id"],
                fixture["sport_id"],
                fixture["tournament_id"],
                fixture["time_casa"],
                fixture["time_fora"],
                fixture["inicio_em"],
                fixture["status"],
                fixture["tem_odds"],
            ),
        )
        return cur.fetchone()[0]


def _mapeamento_existente(cur, provedor_player_id, nome_normalizado):
    if provedor_player_id:
        cur.execute(
            """SELECT jogador_id, confirmado
               FROM odds_jogadores_mapeamento
               WHERE provedor = %s AND provedor_player_id = %s""",
            (PROVEDOR, provedor_player_id),
        )
    else:
        cur.execute(
            """SELECT jogador_id, confirmado
               FROM odds_jogadores_mapeamento
               WHERE provedor = %s AND provedor_player_id IS NULL
                 AND nome_normalizado = %s""",
            (PROVEDOR, nome_normalizado),
        )
    return cur.fetchone()


def mapear_jogador(conn, prop):
    with conn.cursor() as cur:
        existente = _mapeamento_existente(
            cur, prop["provedor_player_id"], prop["nome_normalizado"]
        )
        if existente:
            return existente[0] if existente[1] else None

        cur.execute(
            """SELECT nome, nba_player_id
               FROM jogadores
               WHERE nba_player_id IS NOT NULL"""
        )
        correspondencias = [
            f"nba:{int(nba_player_id)}"
            for nome, nba_player_id in cur.fetchall()
            if normalizar_nome_jogador(nome) == prop["nome_normalizado"]
        ]
        jogador_id = correspondencias[0] if len(correspondencias) == 1 else None
        confirmado = jogador_id is not None
        cur.execute(
            """INSERT INTO odds_jogadores_mapeamento
                   (provedor, provedor_player_id, provedor_player_nome,
                    nome_normalizado, jogador_id, confirmado)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (
                PROVEDOR,
                prop["provedor_player_id"],
                prop["jogador_nome_provedor"],
                prop["nome_normalizado"],
                jogador_id,
                confirmado,
            ),
        )
        return jogador_id


def salvar_props_evento(conn, evento_id, bookmaker, props, capturada_em=None):
    capturada_em = capturada_em or datetime.now(timezone.utc)
    salvas = 0
    sem_jogador = 0
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE odds_cotacoes
               SET ativa = FALSE
               WHERE evento_id = %s AND provedor = %s
                 AND bookmaker = %s AND ativa = TRUE""",
            (evento_id, PROVEDOR, bookmaker),
        )

    for prop in props:
        jogador_id = mapear_jogador(conn, prop)
        if jogador_id is None:
            sem_jogador += 1
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO odds_cotacoes
                       (evento_id, provedor, bookmaker, provedor_market_id,
                        mercado, provedor_player_id, jogador_id,
                        jogador_nome_provedor, linha, lado, odd, ativa,
                        capturada_em, atualizada_em_provedor, payload_hash)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                           %s, TRUE, %s, %s, %s)
                   ON CONFLICT (
                       evento_id, bookmaker, provedor_market_id,
                       (COALESCE(provedor_player_id, '')), mercado, linha, lado,
                       payload_hash
                   ) DO UPDATE SET
                       jogador_id = EXCLUDED.jogador_id,
                       odd = EXCLUDED.odd,
                       ativa = TRUE,
                       capturada_em = EXCLUDED.capturada_em,
                       atualizada_em_provedor = EXCLUDED.atualizada_em_provedor
                   RETURNING id""",
                (
                    evento_id,
                    PROVEDOR,
                    bookmaker,
                    prop["provedor_market_id"],
                    prop["mercado"],
                    prop["provedor_player_id"],
                    jogador_id,
                    prop["jogador_nome_provedor"],
                    prop["linha"],
                    prop["lado"],
                    prop["odd"],
                    capturada_em,
                    prop["atualizada_em_provedor"],
                    prop["payload_hash"],
                ),
            )
            if cur.fetchone():
                salvas += 1
    return salvas, sem_jogador


def iniciar_sincronizacao(conn, bookmaker):
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO odds_sincronizacoes (provedor, bookmaker, status)
               VALUES (%s, %s, 'executando') RETURNING id""",
            (PROVEDOR, bookmaker),
        )
        return cur.fetchone()[0]


def finalizar_sincronizacao(conn, sincronizacao_id, status, resumo, erro=None):
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE odds_sincronizacoes SET
                   finalizada_em = NOW(), status = %s,
                   eventos_encontrados = %s, eventos_consultados = %s,
                   props_recebidas = %s, props_salvas = %s,
                   props_sem_jogador = %s, requisicoes_estimadas = %s,
                   requisicoes_utilizadas = %s, erro_codigo = %s,
                   erro_mensagem_segura = %s
               WHERE id = %s""",
            (
                status,
                resumo.get("eventos_encontrados", 0),
                resumo.get("eventos_consultados", 0),
                resumo.get("props_recebidas", 0),
                resumo.get("props_salvas", 0),
                resumo.get("props_sem_jogador", 0),
                resumo.get("requisicoes_estimadas", 0),
                resumo.get("requisicoes_utilizadas", 0),
                getattr(erro, "codigo", None),
                str(erro) if erro else None,
                sincronizacao_id,
            ),
        )
