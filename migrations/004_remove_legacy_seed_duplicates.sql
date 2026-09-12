DELETE FROM ppg
WHERE id_jogador IN (
    'jamesle01',
    'curryst01',
    'doncilu01',
    'antetgi01',
    'edwaran01',
    'tatumja01',
    'gilgesh01',
    'jokicni01',
    'wembavi01',
    'bookede01'
);

DELETE FROM jogadores
WHERE code_jogador IN (
    'jamesle01',
    'curryst01',
    'doncilu01',
    'antetgi01',
    'edwaran01',
    'tatumja01',
    'gilgesh01',
    'jokicni01',
    'wembavi01',
    'bookede01'
)
AND nba_player_id IS NULL;
