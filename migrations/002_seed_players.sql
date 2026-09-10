INSERT INTO jogadores (code_jogador, nome)
VALUES
    ('jamesle01', 'LeBron James'),
    ('curryst01', 'Stephen Curry'),
    ('doncilu01', 'Luka Doncic'),
    ('antetgi01', 'Giannis Antetokounmpo'),
    ('edwaran01', 'Anthony Edwards'),
    ('tatumja01', 'Jayson Tatum'),
    ('gilgesh01', 'Shai Gilgeous-Alexander'),
    ('jokicni01', 'Nikola Jokic'),
    ('wembavi01', 'Victor Wembanyama'),
    ('bookede01', 'Devin Booker')
ON CONFLICT (code_jogador) DO UPDATE
SET nome = EXCLUDED.nome;
