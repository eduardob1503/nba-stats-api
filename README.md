# 🏀 NBA Stats API

> Para publicar o backend e conectar um PostgreSQL hospedado, consulte
> [DEPLOY_VERCEL.md](DEPLOY_VERCEL.md).

API RESTful para consulta e gerenciamento de estatísticas de jogadores da NBA, com autenticação JWT, controle de acesso por roles e deploy em produção.

🌐 **Produção:** [https://138-2-244-252.sslip.io](https://138-2-244-252.sslip.io)

---

## 🚀 Tecnologias

| Tecnologia | Uso |
|-----------|-----|
| Python 3 + Flask | Framework web e roteamento |
| PostgreSQL + psycopg2 | Banco de dados relacional |
| nba_api | Pontuações reais, obtidas automaticamente da NBA |
| PyJWT | Autenticação stateless com tokens |
| bcrypt | Hash seguro de senhas |
| gunicorn | Servidor WSGI para produção |
| python-dotenv | Gerenciamento de variáveis de ambiente |

---

## 📁 Estrutura do Projeto

```
nba-stats-api/
├── app.py                  # Inicialização do app e registro dos blueprints
├── config.py               # DATABASE_URL e SECRET_KEY via variáveis de ambiente
├── database.py             # Função conectar() com suporte a SSL em produção
├── migrations/
│   ├── 000_base_schema.sql # Criação idempotente das tabelas base
│   ├── 001_nba_sync.sql    # Campos e índice para sincronização sem duplicatas
│   ├── 002_seed_players.sql # Jogadores iniciais exibidos no frontend
│   ├── 003_player_game_stats.sql # Jogos e estatísticas completas por jogador
│   └── 004_remove_legacy_seed_duplicates.sql # Remove os antigos seeds duplicados
├── Procfile                # Comando de start para o Render (gunicorn)
├── requirements.txt        # Dependências do projeto
├── .env.example            # Modelo de variáveis de ambiente
├── auths/
│   ├── __init__.py
│   └── routes.py           # POST /login  |  POST /cadastro
├── jogadores/
│   ├── __init__.py
│   └── routes.py           # CRUD /jogadores
├── services/
│   └── nba.py              # Consulta e normalização dos dados da NBA
├── tests/
│   └── test_nba_service.py # Testes da integração, sem depender da rede
├── middlewares/
│   ├── __init__.py
│   └── auth.py             # @login_required  |  @admin_required
└── README.md
```

---

## ⚙️ Como rodar localmente

### Pré-requisitos

- Python 3.10+
- PostgreSQL rodando localmente
- pip

### 1. Clone o repositório

```bash
git clone https://github.com/eduardob1503/nba-stats-api.git
cd nba-stats-api
```

### 2. Instale as dependências

```bash
pip install -r requirements.txt
```

### 3. Configure o `.env`

Copie o modelo e preencha com suas credenciais:

```bash
cp .env.example .env
```

```env
DATABASE_URL=postgresql://postgres:sua_senha@localhost:5432/nba
SECRET_KEY=sua_chave_secreta_aqui
ENV=development
FIRST_USER_ADMIN=false
NBA_API_TIMEOUT=20
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080,http://127.0.0.1:8080
```

Gere uma SECRET_KEY segura com:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 4. Configure o banco de dados

```sql
CREATE DATABASE nba;

CREATE TABLE usuarios (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(100),
    email VARCHAR(100) UNIQUE,
    senha TEXT,
    is_admin BOOLEAN DEFAULT FALSE
);

CREATE TABLE jogadores (
    id SERIAL PRIMARY KEY,
    code_jogador VARCHAR(20) UNIQUE,
    nome VARCHAR(100),
    nba_player_id BIGINT
);

CREATE TABLE ppg (
    id SERIAL PRIMARY KEY,
    id_jogador VARCHAR(20) REFERENCES jogadores(code_jogador),
    pontos NUMERIC,
    game_id VARCHAR(20),
    temporada VARCHAR(7),
    data_partida DATE,
    adversario VARCHAR(30),
    UNIQUE (id_jogador, game_id)
);
```

As migrações são idempotentes e podem ser executadas em sequência:

```bash
psql "$DATABASE_URL" -f migrations/000_base_schema.sql
psql "$DATABASE_URL" -f migrations/001_nba_sync.sql
psql "$DATABASE_URL" -f migrations/002_seed_players.sql
psql "$DATABASE_URL" -f migrations/003_player_game_stats.sql
psql "$DATABASE_URL" -f migrations/004_remove_legacy_seed_duplicates.sql
psql "$DATABASE_URL" -f migrations/005_name_login.sql
psql "$DATABASE_URL" -f migrations/006_analises.sql
psql "$DATABASE_URL" -f migrations/007_odds_reais.sql
```

`CORS_ORIGINS` recebe uma lista separada por vírgulas. Ao publicar o frontend,
adicione também a URL HTTPS dele nessa variável.

Em desenvolvimento local, defina `FIRST_USER_ADMIN=true` para que o primeiro
cadastro receba acesso ao painel administrativo. Mantenha essa opção como
`false` em produção.

Para promover um usuário a admin:
```sql
UPDATE usuarios SET is_admin = TRUE WHERE email = 'seu@email.com';
```

### 5. Suba a API

```bash
python app.py
```

Disponível em `http://localhost:5000`.

---

## 🔐 Autenticação

A API usa **JWT Bearer Token**. Inclua o token no header de todas as rotas protegidas:

```
Authorization: Bearer <seu_token>
```

| Role | Rotas disponíveis |
|------|------------------|
| 🔓 Público | `POST /cadastro`, `POST /login` |
| 🔒 Usuário logado | Jogadores, estatísticas e as próprias análises |
| 👑 Admin legado | Rotas antigas de escrita de jogadores; fora do fluxo normal |

---

## 📌 Endpoints

### Autenticação

#### `POST /cadastro`
Rota legada de cadastro por e-mail e senha. O fluxo normal usa somente `/login`.

```json
// Body
{ "nome": "Eduardo Viana", "email": "eduardo@email.com", "senha": "minhasenha123" }

// Resposta 201
{ "mensagem": "usuario criado com sucesso" }
```

#### `POST /login`
Cria ou recupera o usuário pelo nome normalizado e retorna um JWT válido por
**1 hora**. Capitalização e espaços extras não criam usuários duplicados.

```json
// Body
{ "nome": "Eduardo" }

// Resposta 200
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "usuario": { "id": 1, "nome": "Eduardo" }
}
```

---

### Jogadores

#### `GET /jogadores` — 🔒 Login
Lista todos os jogadores cadastrados.

```json
// Resposta 200
[
  { "id": "jamesle01", "nome": "LeBron James" },
  { "id": "curryst01", "nome": "Stephen Curry" }
]
```

Com o parâmetro `busca`, pesquisa o catálogo completo de jogadores ativos e
históricos da NBA. A busca aceita partes do nome, múltiplos termos e ignora
acentos. Os jogadores ativos e as correspondências mais próximas aparecem
primeiro.

```http
GET /jogadores?busca=jokic
Authorization: Bearer <token>
```

```json
[
  {
    "id": "nba:203999",
    "nome": "Nikola Jokić",
    "nba_player_id": 203999,
    "ativo": true
  }
]
```

#### `GET /jogadores/<code>` — 🔒 Login
Retorna estatísticas de um jogador. Se não houver pontos, retorna dados básicos do cadastro.

```json
// Resposta 200 — com pontos registrados
{
  "id": "jamesle01",
  "pontos": [28, 31, 19, 24],
  "id_partida": [1, 2, 3, 4],
  "media": 25.5,
  "jogos": 4
}

// Resposta 200 — sem pontos ainda
{ "code": "jamesle01", "nome": "LeBron James" }
```

#### `POST /jogadores` — 👑 Admin
Cadastra um novo jogador. O `code` é gerado automaticamente a partir do nome.

```json
// Body
{ "nome": "LeBron James" }

// Resposta 201
{ "nome": "LeBron James", "code": "jamesle01" }
```

#### `POST /jogadores/<code>` — 👑 Admin
Adiciona registros de pontuação para um jogador.

```json
// Body
{ "pontos": [28, 31, 19] }

// Resposta 201
{ "pontos": [28, 31, 19] }
```

#### `GET /jogadores/<code>/nba` — 🔒 Login
Consulta automaticamente as partidas reais na NBA, sem alterar o banco. Aceita
tanto os códigos cadastrados quanto IDs retornados pela busca (`nba:203999`). A
temporada é opcional e usa o formato `AAAA-AA`; quando omitida, a API escolhe a
temporada mais recente.

```http
GET /jogadores/jamesle01/nba?temporada=2025-26&tipo=Regular%20Season
Authorization: Bearer <token>
```

```json
{
  "code": "jamesle01",
  "nome": "LeBron James",
  "nba_player_id": 2544,
  "temporada": "2025-26",
  "jogos": 3,
  "pontos": [21, 29, 33],
  "media": 27.67,
  "partidas": [
    {
      "game_id": "0022500001",
      "data": "2025-10-21",
      "adversario": "LAL vs. GSW",
      "pontos": 21
    }
  ]
}
```

#### `POST /jogadores/<code>/sincronizar` — 👑 Admin
Busca os jogos reais e grava/atualiza os pontos no PostgreSQL. O `game_id` oficial
impede que uma nova sincronização duplique partidas.

```json
// Body opcional
{ "temporada": "2025-26", "tipo": "Regular Season" }

// Resposta 200
{
  "mensagem": "dados da NBA sincronizados",
  "code": "jamesle01",
  "nba_player_id": 2544,
  "temporada": "2025-26",
  "tipo_temporada": "Regular Season",
  "jogos_sincronizados": 82
}
```

#### `DELETE /jogadores/<code>` — 👑 Admin
Remove o jogador e todos os seus registros de pontuação.

```json
// Resposta 200
{ "mensagem": "jogador deletado" }
```

---

## Contrato para o frontend

### Login e JWT

`POST /login`

```json
{ "nome": "Eduardo" }
```

O frontend deve guardar o campo `token` da resposta e enviá-lo nas rotas
protegidas:

```http
Authorization: Bearer <token>
```

### Estatísticas e mercados

`GET /jogadores/<id>/nba?temporada=2025-26&tipo=Todos`

As temporadas aceitas são `2025-26` e `2026-27`. O filtro `tipo` aceita
`Todos`, `Regular Season` ou `Playoffs`. Cada partida mantém os campos
anteriores e também expõe, quando os componentes existem:

```json
{
  "pontos": 28,
  "assistencias": 9,
  "rebotes": 11,
  "cestas_3": 4,
  "tentativas_3": 8,
  "pa": 37,
  "ar": 20,
  "par": 48
}
```

Os mercados aceitos são `pontos`, `assistencias`, `rebotes`, `cestas_3`,
`tentativas_3`, `pa`, `ar` e `par`. Se um componente estiver ausente,
o mercado composto não é calculado para aquela partida e ela é contabilizada
em `jogos_sem_dado` na análise.

### Análises salvas

- `POST /analises`: calcula e salva um snapshot.
- `GET /analises`: lista somente as análises do usuário do JWT.
- `GET /analises/<id>`: abre uma análise do próprio usuário.
- `DELETE /analises/<id>`: apaga uma análise do próprio usuário.

Exemplo para salvar:

```json
{
  "jogador_id": "nba:2544",
  "temporada": "2025-26",
  "tipo_temporada": "Todos",
  "mercado": "par",
  "quantidade_jogos": 10,
  "linha": 39.5,
  "odd": 1.9,
  "lado": "over"
}
```

`quantidade_jogos` aceita `5`, `10`, `15`, `20` ou `"todos"`.
Pushes não entram como acerto nem erro, e o percentual usa somente decisões.
A resposta salva inclui média, mediana, maior e menor valor, acertos, erros,
pushes, percentual, sequência, partidas do snapshot, `created_at` e
`updated_at`.

Erros de autenticação retornam `401`, recursos não encontrados retornam
`404` e configurações semanticamente inválidas retornam `422`, sempre com
um objeto JSON contendo `erro`.

---

## Scanner de oportunidades EV+

`GET /oportunidades/ev` é uma rota protegida que compara a mesma configuração
de aposta com o histórico de todos os jogadores sincronizados. Ela retorna
somente resultados com EV positivo, do maior para o menor, sem criar uma
análise salva e sem consultar a NBA API externa.

```http
GET /oportunidades/ev?temporada=2025-26&tipo_temporada=Regular%20Season&mercado=cestas_3&linha=1.5&odd=1.90&lado=over&quantidade_jogos=10&minimo_jogos=5&limite=20
Authorization: Bearer <token>
```

Parâmetros obrigatórios:

- `temporada`: `2025-26` ou `2026-27`;
- `mercado`: `pontos`, `assistencias`, `rebotes`, `cestas_3`,
  `tentativas_3`, `pa`, `ar` ou `par`;
- `linha`: decimal maior ou igual a zero;
- `odd`: odd decimal maior que 1;
- `lado`: `over` ou `under`;
- `quantidade_jogos`: `5`, `10`, `15`, `20` ou `todos`.

Parâmetros opcionais:

- `tipo_temporada`: `Todos` (padrão), `Regular Season` ou `Playoffs`;
- `minimo_jogos`: inteiro positivo, padrão `5`, e não pode superar uma
  quantidade de jogos numérica selecionada;
- `limite`: inteiro de `1` a `100`, padrão `20`;
- `linhas_plausiveis`: `true` ou `false`, padrão `false`;
- `percentil_inferior`: decimal entre `0` e `50`, padrão `25`;
- `percentil_superior`: decimal entre `50` e `100`, padrão `75`;
- `edge_minimo_percentual`: decimal maior ou igual a zero, padrão `3`;
- `edge_maximo_percentual`: decimal maior que o mínimo e no máximo `100`,
  padrão `20`.

O modo de linhas plausíveis é ativado explicitamente com
`linhas_plausiveis=true`. Uma linha é estatisticamente plausível quando fica
dentro da faixa de percentis do próprio jogador e o edge fica dentro dos
limites configurados. Isso não significa que a odd esteja realmente disponível
em uma casa de apostas.

```http
GET /oportunidades/ev?temporada=2025-26&tipo_temporada=Regular%20Season&mercado=pontos&linha=20&odd=2.00&lado=over&quantidade_jogos=10&minimo_jogos=10&limite=20&linhas_plausiveis=true&percentil_inferior=25&percentil_superior=75&edge_minimo_percentual=3&edge_maximo_percentual=20
Authorization: Bearer <token>
```

O backend não recebe nomes de presets. O frontend pode oferecer:

- Abrangente: P15–P85;
- Equilibrado: P25–P75;
- Rigoroso: P35–P65;
- Personalizado: percentis escolhidos pelo usuário.

Quando `linhas_plausiveis=false`, todos os parâmetros avançados são validados
e retornados em `filtros`, mas não excluem oportunidades. Esse é o padrão para
preservar clientes anteriores.

`cestas_3` representa bolas de três convertidas e `tentativas_3`, as
tentativas. Os compostos são `pa = pontos + assistencias`,
`ar = assistencias + rebotes` e `par = pontos + assistencias + rebotes`.
Se qualquer componente estiver ausente, a partida é ignorada para aquele
mercado e contabilizada em `jogos_sem_dado`.

Para `over`, um valor acima da linha é acerto; para `under`, um valor abaixo
da linha é acerto. Valor igual à linha é `push`: ele é informado separadamente
e não entra como acerto, erro ou no denominador da probabilidade histórica.
Pushes entram normalmente na distribuição usada pelos percentis. Não existe
exigência de quantidade mínima de erros: continuam obrigatórios apenas o mínimo
de jogos válidos, uma decisão válida e EV positivo.

Os percentis usam somente valores válidos do mercado dentro da amostra e o
método linear R-7, equivalente ao padrão linear do NumPy, sem dependência de
NumPy. Depois de ordenar os valores, o índice é
`(n - 1) × (percentil / 100)`; índices fracionários são interpolados entre os
dois valores vizinhos. A linha é aceita de forma inclusiva:
`valor_inferior <= linha <= valor_superior`. Todos os cálculos e comparações
são feitos com `Decimal` antes do arredondamento da resposta.

As fórmulas, calculadas com `Decimal`, são:

```text
probabilidade_historica = acertos / (acertos + erros)
probabilidade_implicita = 1 / odd
edge = probabilidade_historica - probabilidade_implicita
ev = (probabilidade_historica * odd) - 1
ev_percentual = ev * 100
```

Edge é a vantagem da probabilidade histórica sobre a probabilidade implícita.
EV é o retorno esperado por unidade apostada; portanto, são medidas diferentes.
A ordenação usa os valores integrais, antes do arredondamento: EV,
probabilidade histórica e número de decisões em ordem decrescente, seguidos
pelo nome em ordem crescente.

Exemplo resumido de resposta `200`:

```json
{
  "filtros": {
    "temporada": "2025-26",
    "tipo_temporada": "Regular Season",
    "mercado": "cestas_3",
    "linha": 1.5,
    "odd": 1.9,
    "lado": "over",
    "quantidade_jogos": 10,
    "minimo_jogos": 5,
    "limite": 20,
    "linhas_plausiveis": true,
    "percentil_inferior": 25,
    "percentil_superior": 75,
    "edge_minimo_percentual": 3,
    "edge_maximo_percentual": 20
  },
  "total_jogadores_avaliados": 582,
  "total_elegiveis": 560,
  "total_ev_positivo": 27,
  "total_ev_positivo_bruto": 230,
  "total_linhas_plausiveis": 27,
  "total_retornado": 20,
  "exclusoes": {
    "jogos_insuficientes": 20,
    "sem_decisoes": 2,
    "ev_nao_positivo": 330,
    "linha_fora_percentis": 160,
    "edge_abaixo_minimo": 10,
    "edge_acima_maximo": 33
  },
  "oportunidades": [
    {
      "posicao": 1,
      "jogador": {
        "id": "nba:2544",
        "nba_player_id": 2544,
        "nome": "LeBron James",
        "ativo": null
      },
      "jogos_selecionados": 10,
      "jogos_validos": 10,
      "jogos_sem_dado": 0,
      "acertos": 7,
      "erros": 3,
      "pushes": 0,
      "probabilidade_historica": 0.7,
      "percentual_acerto": 70,
      "probabilidade_implicita": 0.526316,
      "percentual_implicito": 52.63,
      "edge": 0.173684,
      "edge_percentual": 17.37,
      "ev": 0.33,
      "ev_percentual": 33,
      "media": 2.7,
      "mediana": 3,
      "maior_valor": 5,
      "menor_valor": 1,
      "ultimo_valor": 3,
      "valores_recentes": [3, 2, 4, 1, 5, 3, 1, 3, 1, 4],
      "ultima_partida": "2026-04-10",
      "faixa_percentil": {
        "percentil_inferior": 25,
        "valor_inferior": 1.25,
        "percentil_superior": 75,
        "valor_superior": 3.75
      },
      "linha_dentro_faixa": true,
      "edge_dentro_faixa": true
    }
  ]
}
```

As exclusões são mutuamente exclusivas. Cada jogador é contado somente no
primeiro motivo aplicável, nesta ordem: `jogos_insuficientes`, `sem_decisoes`,
`ev_nao_positivo`, `linha_fora_percentis`, `edge_abaixo_minimo` e
`edge_acima_maximo`. `total_ev_positivo_bruto` é contado antes da plausibilidade;
`total_ev_positivo` e `total_linhas_plausiveis` são contados depois dela e antes
do limite; `total_retornado` é o tamanho final de `oportunidades`.

No modo desativado, as três exclusões avançadas são zero e
`total_ev_positivo == total_ev_positivo_bruto == total_linhas_plausiveis`.

Se nenhum jogador tiver EV positivo, a API retorna `200` com
`"oportunidades": []`. Parâmetros inválidos retornam `422`; JWT ausente,
inválido ou expirado retorna `401`; uma temporada ainda sem estatísticas
sincronizadas retorna `404` com a temporada solicitada.

O scanner usa desempenho histórico como estimativa. Ele não garante resultados
futuros, não substitui avaliação de risco e não confirma a disponibilidade da
linha ou da odd em casas de apostas.

---

## Odds reais da Betano via OddsPapi

A integração com a OddsPapi é executada exclusivamente pelo backend. Nenhum
endpoint comum do frontend chama a API externa. A chave nunca é retornada,
registrada ou salva no PostgreSQL, e URLs contendo `apiKey` também não são
persistidas.

Configuração:

```env
ODDSPAPI_API_KEY=
ODDSPAPI_BASE_URL=https://api.oddspapi.io/v4
ODDSPAPI_BOOKMAKERS=betano
ODDSPAPI_SPORT_ID=11
ODDSPAPI_TOURNAMENT_ID=132
ODDSPAPI_TIMEOUT=20
ODDSPAPI_SYNC_MAX_REQUESTS=15
ODDSPAPI_SYNC_COOLDOWN_MINUTES=30
ODDSPAPI_FIXTURE_WINDOW_HOURS=48
ODDSPAPI_ODDS_MAX_AGE_MINUTES=60
ODDSPAPI_MARKETS_CACHE_HOURS=168
```

A ausência de `ODDSPAPI_API_KEY` não impede a API de iniciar. Nesse caso,
`GET /odds/status` informa `configurado: false`. Nunca coloque a chave real no
`.env.example`, README, logs ou respostas HTTP.

### Migration

A migration progressiva [007_odds_reais.sql](migrations/007_odds_reais.sql)
cria tabelas independentes para status/quota, catálogo de mercados, eventos,
mapeamentos de jogadores, snapshots de cotações e execuções da sincronização.
Ela não remove nem altera dados existentes.

```bash
python migrate.py
```

Em produção, aplique essa migration somente durante um deploy autorizado.

### Sincronização manual e proteção da cota

```bash
# Mostra a estimativa e não consulta /odds
python -m scripts.sincronizar_odds_nba --bookmaker betano --dry-run

# Limita eventos e mercados
python -m scripts.sincronizar_odds_nba \
  --bookmaker betano \
  --max-eventos 5 \
  --mercados pontos,assistencias,rebotes,cestas_3,pa,ar,par
```

O comando consulta conta, catálogo quando o cache longo expira e fixtures da
janela futura. Antes de consultar odds por partida, mostra a estimativa e recusa
execuções acima de `ODDSPAPI_SYNC_MAX_REQUESTS` ou da cota restante. Um advisory
lock do PostgreSQL impede concorrência e o cooldown evita execuções repetidas.
HTTP 429 nunca é repetido automaticamente; timeouts e 5xx possuem tentativas
curtas e limitadas. Toda execução é registrada sem chave ou URL sensível.

O `--dry-run` ainda pode usar chamadas de conta, catálogo e fixtures, mas não
chama `/odds`. Como o plano gratuito é limitado, não há job frequente habilitado.

### Catálogo e mapeamento

O catálogo não usa IDs numéricos fixos. Ele considera `sportId`, nome, tipo e
flag de player prop, reconhecendo:

- pontos;
- assistências;
- rebotes;
- cestas de três convertidas;
- pontos + assistências (`pa`);
- assistências + rebotes (`ar`);
- pontos + rebotes + assistências (`par`).

`tentativas_3` permanece no histórico, mas não é criada como prop real sem um
mercado correspondente do provedor. Nomes ambíguos como Points + Rebounds não
são interpretados como pontos.

Jogadores são comparados sem diferenças de caixa, acentos ou espaços e o
formato `Sobrenome, Nome` é suportado. O identificador do provedor tem prioridade.
Somente uma correspondência exata e única é confirmada automaticamente; casos
desconhecidos ou ambíguos ficam em `/odds/mapeamentos/pendentes`.

### Endpoints de leitura

Todos exigem `Authorization: Bearer <token>` e consultam somente o PostgreSQL:

- `GET /odds/status`: configuração segura, quota armazenada e última execução;
- `GET /odds/mapeamentos/pendentes`: jogadores ainda não associados;
- `GET /odds/props`: cotações armazenadas, com filtros `mercado`, `jogador_id`,
  `evento_id`, `lado`, `bookmaker` e `somente_ativas`.

Exemplo:

```http
GET /odds/props?mercado=pontos&lado=over&bookmaker=betano&somente_ativas=true
Authorization: Bearer <token>
```

Cotações ativas mais antigas que `ODDSPAPI_ODDS_MAX_AGE_MINUTES` e eventos que
já começaram não são retornados como props ativas. Linhas alternativas são
preservadas. Uma resposta completa nova marca como inativas as cotações que
desapareceram, enquanto snapshots históricos continuam no banco. Payloads
idênticos são deduplicados por hash.

### Scanner com linhas e odds reais

`GET /oportunidades/ev-reais` usa cada linha e odd ativa da Betano e cruza com
o histórico local. Ele nunca chama a OddsPapi durante a requisição.

```http
GET /oportunidades/ev-reais?temporada=2025-26&tipo_temporada=Regular%20Season&mercado=pontos&lado=over&quantidade_jogos=10&minimo_jogos=5&linhas_plausiveis=true&percentil_inferior=25&percentil_superior=75&edge_minimo_percentual=3&edge_maximo_percentual=20&bookmaker=betano&limite=20
Authorization: Bearer <token>
```

Não são enviados `linha` ou `odd`: esses campos vêm da cotação armazenada. O
cálculo usa `Decimal`, exclui pushes das decisões e ordena por EV, edge,
decisões e nome. A resposta inclui evento, bookmaker, linha, odd, probabilidades,
edge, EV, acertos, erros, pushes, faixa de percentis e horário da captura.

Quando ainda não existem odds:

```json
{
  "status": "sem_odds",
  "mensagem": "Ainda nao existem odds da NBA disponiveis na Betano.",
  "bookmaker": "betano",
  "oportunidades": [],
  "total": 0
}
```

### Limitações antes da primeira resposta real

Os parsers aceitam aliases comuns e estruturas aninhadas, mas os nomes exatos
dos campos, IDs de mercados e possíveis formatos de `bookmakerOutcomeId` ainda
precisam ser confirmados com uma resposta real da NBA/Betano. Faça primeiro um
`--dry-run`; depois autorize uma sincronização com `--max-eventos 1`. Se o
payload real divergir, salve apenas uma amostra sanitizada, sem chave, para criar
um novo fixture automatizado antes de ampliar a sincronização.

---

## Sincronizar as temporadas pelo PC

O servidor de produção lê os dados salvos no PostgreSQL e não consulta a NBA
diretamente. O coletor aceita somente `2025-26` e `2026-27`, inclui temporada
regular e playoffs e guarda uma cópia compactada separada para cada temporada.

O token pode ficar no arquivo privado `.sync-token` ou ser configurado no `.env`
local com o mesmo valor instalado na Oracle:

```env
SYNC_API_URL=https://138-2-244-252.sslip.io
SYNC_TOKEN=seu_token_privado
NBA_SYNC_SEASON=2025-26
```

Para baixar e enviar em um único comando:

```powershell
# Temporada anterior
.\.venv\Scripts\python.exe scripts\sync_last_season.py

# Nova temporada
.\.venv\Scripts\python.exe scripts\sync_last_season.py --season 2026-27
```

Também é possível separar as etapas:

```powershell
# Baixa da NBA e salva no PC
.\.venv\Scripts\python.exe scripts\sync_last_season.py --fetch-only

# Envia o arquivo já salvo sem consultar novamente a NBA
.\.venv\Scripts\python.exe scripts\sync_last_season.py --upload-only
```

Por padrão, o coletor consulta o último dia já salvo e envia somente as atuações
recentes. Assim, o comando pode ser executado depois de cada noite de jogos. Use
`--full` apenas quando precisar reenviar toda a temporada. O `upsert` impede
duplicação de partidas em ambos os modos.

A porta do PostgreSQL permanece fechada; somente o endpoint HTTPS protegido pelo
token recebe os dados.

---

## 🛡️ Segurança

- Senhas do cadastro legado com **bcrypt** (hash + salt automático)
- Tokens JWT com **expiração de 1 hora** e usuário estável em `sub`
- Credenciais em **variáveis de ambiente** — nunca no código
- Conexão com banco via **SSL em produção** (`sslmode=require`)
- Decorators reutilizáveis `@login_required` e `@admin_required`
- Erros de autenticação retornados em JSON sem detalhes internos

---

## 📊 Roadmap

- [ ] Context manager para conexões automáticas com o banco
- [ ] Rate limiting no `/login` com Flask-Limiter
- [x] Testes automatizados da integração com a NBA
- [x] Stats avançadas: `max`, `min`, desvio padrão por jogador
- [ ] Endpoint `/jogadores/:code/tendencia` — média dos últimos 5/10/15 jogos
- [x] Integração com dados reais via `nba_api` (PyPI)
- [ ] Documentação interativa com Swagger (Flask-RESTX)
- [ ] Docker Compose para ambiente de desenvolvimento

---

## 👨‍💻 Autor

**Eduardo Barcelos Viana**

[![LinkedIn](https://img.shields.io/badge/LinkedIn-eduardo--viana1503-blue?style=flat&logo=linkedin)](https://linkedin.com/in/eduardo-viana1503)
[![GitHub](https://img.shields.io/badge/GitHub-eduardob1503-black?style=flat&logo=github)](https://github.com/eduardob1503)
