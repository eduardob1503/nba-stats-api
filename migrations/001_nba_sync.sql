ALTER TABLE jogadores
    ADD COLUMN IF NOT EXISTS nba_player_id BIGINT;

ALTER TABLE ppg
    ADD COLUMN IF NOT EXISTS game_id VARCHAR(20),
    ADD COLUMN IF NOT EXISTS temporada VARCHAR(7),
    ADD COLUMN IF NOT EXISTS data_partida DATE,
    ADD COLUMN IF NOT EXISTS adversario VARCHAR(30);

CREATE UNIQUE INDEX IF NOT EXISTS uq_ppg_jogador_game
    ON ppg (id_jogador, game_id);
