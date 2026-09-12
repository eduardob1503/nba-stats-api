INSERT INTO jogadores (code_jogador, nome, nba_player_id)
VALUES
    ('nba:2544', 'LeBron James', 2544),
    ('nba:201939', 'Stephen Curry', 201939),
    ('nba:1629029', 'Luka Dončić', 1629029),
    ('nba:203507', 'Giannis Antetokounmpo', 203507),
    ('nba:1630162', 'Anthony Edwards', 1630162),
    ('nba:1628369', 'Jayson Tatum', 1628369),
    ('nba:1628983', 'Shai Gilgeous-Alexander', 1628983),
    ('nba:203999', 'Nikola Jokić', 203999),
    ('nba:1641705', 'Victor Wembanyama', 1641705),
    ('nba:1626164', 'Devin Booker', 1626164)
ON CONFLICT (code_jogador) DO UPDATE
SET nome = EXCLUDED.nome,
    nba_player_id = EXCLUDED.nba_player_id;
