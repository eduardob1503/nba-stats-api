CREATE TABLE IF NOT EXISTS analises (
    id BIGSERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    jogador_id VARCHAR(30) NOT NULL,
    nba_player_id BIGINT NOT NULL,
    jogador_nome VARCHAR(120) NOT NULL,
    temporada VARCHAR(7) NOT NULL
        CHECK (temporada IN ('2025-26', '2026-27')),
    tipo_temporada VARCHAR(20) NOT NULL DEFAULT 'Todos'
        CHECK (tipo_temporada IN ('Todos', 'Regular Season', 'Playoffs')),
    mercado VARCHAR(20) NOT NULL
        CHECK (mercado IN (
            'pontos', 'assistencias', 'rebotes', 'cestas_3',
            'tentativas_3', 'pa', 'ar', 'par'
        )),
    quantidade_jogos VARCHAR(5) NOT NULL
        CHECK (quantidade_jogos IN ('5', '10', '15', '20', 'todos')),
    linha NUMERIC(10, 2) NOT NULL CHECK (linha >= 0),
    odd NUMERIC(10, 3) NOT NULL CHECK (odd > 1),
    lado VARCHAR(5) NOT NULL CHECK (lado IN ('over', 'under')),
    snapshot JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_analises_usuario_criacao
    ON analises (usuario_id, created_at DESC);
