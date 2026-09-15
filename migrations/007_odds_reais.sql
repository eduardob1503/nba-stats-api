CREATE TABLE IF NOT EXISTS odds_provedor_status (
    provedor VARCHAR(30) PRIMARY KEY,
    limite_mensal INTEGER,
    requisicoes_utilizadas INTEGER,
    requisicoes_restantes INTEGER,
    renova_em TIMESTAMPTZ,
    verificado_em TIMESTAMPTZ,
    status_ultima_verificacao VARCHAR(30) NOT NULL DEFAULT 'nunca_verificada',
    erro_codigo VARCHAR(50),
    erro_mensagem_segura TEXT
);

CREATE TABLE IF NOT EXISTS odds_mercados_catalogo (
    id BIGSERIAL PRIMARY KEY,
    provedor VARCHAR(30) NOT NULL,
    sport_id INTEGER NOT NULL,
    provedor_market_id VARCHAR(120) NOT NULL,
    nome_provedor VARCHAR(255),
    mercado VARCHAR(30),
    player_prop BOOLEAN,
    payload JSONB NOT NULL,
    consultado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (provedor, sport_id, provedor_market_id)
);

CREATE INDEX IF NOT EXISTS idx_odds_mercados_catalogo_consulta
    ON odds_mercados_catalogo (provedor, sport_id, consultado_em DESC);

CREATE TABLE IF NOT EXISTS odds_eventos (
    id BIGSERIAL PRIMARY KEY,
    provedor VARCHAR(30) NOT NULL,
    provedor_fixture_id VARCHAR(120) NOT NULL,
    sport_id INTEGER NOT NULL,
    tournament_id INTEGER NOT NULL,
    time_casa VARCHAR(150),
    time_fora VARCHAR(150),
    inicio_em TIMESTAMPTZ NOT NULL,
    status VARCHAR(50),
    tem_odds BOOLEAN NOT NULL DEFAULT FALSE,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (provedor, provedor_fixture_id)
);

CREATE INDEX IF NOT EXISTS idx_odds_eventos_futuros
    ON odds_eventos (inicio_em, tem_odds);

CREATE TABLE IF NOT EXISTS odds_jogadores_mapeamento (
    id BIGSERIAL PRIMARY KEY,
    provedor VARCHAR(30) NOT NULL,
    provedor_player_id VARCHAR(120),
    provedor_player_nome VARCHAR(150) NOT NULL,
    nome_normalizado VARCHAR(150) NOT NULL,
    jogador_id VARCHAR(30),
    confirmado BOOLEAN NOT NULL DEFAULT FALSE,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_odds_mapeamento_player_id
    ON odds_jogadores_mapeamento (provedor, provedor_player_id)
    WHERE provedor_player_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_odds_mapeamento_nome_sem_id
    ON odds_jogadores_mapeamento (provedor, nome_normalizado)
    WHERE provedor_player_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_odds_mapeamentos_pendentes
    ON odds_jogadores_mapeamento (confirmado, provedor, criado_em DESC);

CREATE TABLE IF NOT EXISTS odds_cotacoes (
    id BIGSERIAL PRIMARY KEY,
    evento_id BIGINT NOT NULL REFERENCES odds_eventos(id) ON DELETE CASCADE,
    provedor VARCHAR(30) NOT NULL,
    bookmaker VARCHAR(50) NOT NULL,
    provedor_market_id VARCHAR(120) NOT NULL,
    mercado VARCHAR(30) NOT NULL CHECK (mercado IN (
        'pontos', 'assistencias', 'rebotes', 'cestas_3', 'pa', 'ar', 'par'
    )),
    provedor_player_id VARCHAR(120),
    jogador_id VARCHAR(30),
    jogador_nome_provedor VARCHAR(150) NOT NULL,
    linha NUMERIC(10, 3) NOT NULL CHECK (linha >= 0),
    lado VARCHAR(5) NOT NULL CHECK (lado IN ('over', 'under', 'yes', 'no')),
    odd NUMERIC(10, 4) NOT NULL CHECK (odd > 1),
    ativa BOOLEAN NOT NULL DEFAULT TRUE,
    capturada_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizada_em_provedor TIMESTAMPTZ,
    payload_hash CHAR(64) NOT NULL,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_odds_cotacoes_snapshot
    ON odds_cotacoes (
        evento_id, bookmaker, provedor_market_id,
        (COALESCE(provedor_player_id, '')), mercado, linha, lado, payload_hash
    );

CREATE INDEX IF NOT EXISTS idx_odds_cotacoes_ativas
    ON odds_cotacoes (bookmaker, mercado, lado, capturada_em DESC)
    WHERE ativa = TRUE;

CREATE INDEX IF NOT EXISTS idx_odds_cotacoes_jogador
    ON odds_cotacoes (jogador_id, ativa, capturada_em DESC);

CREATE TABLE IF NOT EXISTS odds_sincronizacoes (
    id BIGSERIAL PRIMARY KEY,
    provedor VARCHAR(30) NOT NULL,
    bookmaker VARCHAR(50) NOT NULL,
    iniciada_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finalizada_em TIMESTAMPTZ,
    status VARCHAR(30) NOT NULL,
    eventos_encontrados INTEGER NOT NULL DEFAULT 0,
    eventos_consultados INTEGER NOT NULL DEFAULT 0,
    props_recebidas INTEGER NOT NULL DEFAULT 0,
    props_salvas INTEGER NOT NULL DEFAULT 0,
    props_sem_jogador INTEGER NOT NULL DEFAULT 0,
    requisicoes_estimadas INTEGER NOT NULL DEFAULT 0,
    requisicoes_utilizadas INTEGER NOT NULL DEFAULT 0,
    erro_codigo VARCHAR(50),
    erro_mensagem_segura TEXT
);

CREATE INDEX IF NOT EXISTS idx_odds_sincronizacoes_cooldown
    ON odds_sincronizacoes (provedor, bookmaker, iniciada_em DESC);
