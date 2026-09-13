ALTER TABLE usuarios
    ADD COLUMN IF NOT EXISTS nome_normalizado VARCHAR(100);

WITH nomes_limpos AS (
    SELECT id,
           COALESCE(
               NULLIF(regexp_replace(BTRIM(nome), '[[:space:]]+', ' ', 'g'), ''),
               'Usuario ' || id
           ) AS nome_limpo
    FROM usuarios
)
UPDATE usuarios AS u
SET nome = n.nome_limpo,
    nome_normalizado = LOWER(n.nome_limpo)
FROM nomes_limpos AS n
WHERE u.id = n.id
  AND (u.nome_normalizado IS NULL OR u.nome IS DISTINCT FROM n.nome_limpo);

WITH nomes_repetidos AS (
    SELECT id,
           nome_normalizado,
           ROW_NUMBER() OVER (PARTITION BY nome_normalizado ORDER BY id) AS posicao
    FROM usuarios
)
UPDATE usuarios AS u
SET nome_normalizado = u.nome_normalizado || '-' || u.id
FROM nomes_repetidos AS r
WHERE u.id = r.id
  AND r.posicao > 1;

ALTER TABLE usuarios
    ALTER COLUMN nome SET NOT NULL,
    ALTER COLUMN nome_normalizado SET NOT NULL,
    ALTER COLUMN email DROP NOT NULL,
    ALTER COLUMN senha DROP NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_usuarios_nome_normalizado
    ON usuarios (nome_normalizado);
