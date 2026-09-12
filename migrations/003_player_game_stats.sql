CREATE UNIQUE INDEX IF NOT EXISTS uq_jogadores_nba_player_id
    ON jogadores (nba_player_id)
    WHERE nba_player_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS jogos (
    game_id VARCHAR(20) PRIMARY KEY,
    temporada VARCHAR(7) NOT NULL,
    tipo_temporada VARCHAR(20) NOT NULL,
    data_partida DATE NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_jogos_temporada_data
    ON jogos (temporada, tipo_temporada, data_partida DESC);

CREATE TABLE IF NOT EXISTS estatisticas_jogador (
    id BIGSERIAL PRIMARY KEY,
    game_id VARCHAR(20) NOT NULL REFERENCES jogos(game_id) ON DELETE CASCADE,
    nba_player_id BIGINT NOT NULL,
    nome_jogador VARCHAR(120) NOT NULL,
    team_id BIGINT,
    time_sigla VARCHAR(5),
    adversario VARCHAR(30),
    resultado CHAR(1),
    minutos NUMERIC(6, 2),
    pontos INTEGER,
    rebotes INTEGER,
    assistencias INTEGER,
    roubos INTEGER,
    tocos INTEGER,
    turnovers INTEGER,
    cestas INTEGER,
    tentativas INTEGER,
    cestas_3 INTEGER,
    tentativas_3 INTEGER,
    lances_livres INTEGER,
    tentativas_livres INTEGER,
    plus_minus NUMERIC(7, 2),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (game_id, nba_player_id)
);

CREATE INDEX IF NOT EXISTS idx_estatisticas_jogador_consulta
    ON estatisticas_jogador (nba_player_id, game_id);
