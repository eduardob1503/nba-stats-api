CREATE TABLE IF NOT EXISTS usuarios (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(100),
    email VARCHAR(100) UNIQUE,
    senha TEXT,
    is_admin BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS jogadores (
    id SERIAL PRIMARY KEY,
    code_jogador VARCHAR(20) UNIQUE,
    nome VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS ppg (
    id SERIAL PRIMARY KEY,
    id_jogador VARCHAR(20) REFERENCES jogadores(code_jogador),
    pontos NUMERIC
);
