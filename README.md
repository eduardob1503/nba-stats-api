# 🏀 NBA Stats API

> Para publicar o backend e conectar um PostgreSQL hospedado, consulte
> [DEPLOY_VERCEL.md](DEPLOY_VERCEL.md).

API RESTful para consulta e gerenciamento de estatísticas de jogadores da NBA, com autenticação JWT, controle de acesso por roles e deploy em produção.

🌐 **Demo ao vivo:** [https://nba-stats-api-kfwn.onrender.com](https://nba-stats-api-kfwn.onrender.com)
> Serviço no plano gratuito do Render — pode levar ~30s na primeira requisição após inatividade.

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
| 🔒 Usuário logado | `GET /jogadores`, busca no catálogo da NBA e consultas de partidas |
| 👑 Admin | Todas as rotas + `POST /jogadores`, `POST /jogadores/:code`, `DELETE /jogadores/:code` |

---

## 📌 Endpoints

### Autenticação

#### `POST /cadastro`
Cria um novo usuário.

```json
// Body
{ "nome": "Eduardo Viana", "email": "eduardo@email.com", "senha": "minhasenha123" }

// Resposta 201
{ "mensagem": "usuario criado com sucesso" }
```

#### `POST /login`
Retorna um token JWT válido por **1 hora**.

```json
// Body
{ "email": "eduardo@email.com", "senha": "minhasenha123" }

// Resposta 200
{ "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." }
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

## Sincronizar a temporada 2025-26 pelo PC

O servidor de produção lê os dados salvos no PostgreSQL e não consulta a NBA
diretamente. O coletor local baixa somente a última temporada concluída
(`2025-26`), incluindo temporada regular e playoffs, e guarda uma cópia
compactada em `data/nba-2025-26.json.gz`.

O token pode ficar no arquivo privado `.sync-token` ou ser configurado no `.env`
local com o mesmo valor instalado na Oracle:

```env
SYNC_API_URL=https://138-2-244-252.sslip.io
SYNC_TOKEN=seu_token_privado
NBA_SYNC_SEASON=2025-26
```

Para baixar e enviar em um único comando:

```powershell
.\.venv\Scripts\python.exe scripts\sync_last_season.py
```

Também é possível separar as etapas:

```powershell
# Baixa da NBA e salva no PC
.\.venv\Scripts\python.exe scripts\sync_last_season.py --fetch-only

# Envia o arquivo já salvo sem consultar novamente a NBA
.\.venv\Scripts\python.exe scripts\sync_last_season.py --upload-only
```

O envio usa lotes e `upsert`, portanto repetir o comando não duplica partidas.
A porta do PostgreSQL permanece fechada; somente o endpoint HTTPS protegido pelo
token recebe os dados.

---

## 🛡️ Segurança

- Senhas com **bcrypt** (hash + salt automático)
- Tokens JWT com **expiração de 1 hora** (`exp` + `iat` no payload)
- Credenciais em **variáveis de ambiente** — nunca no código
- Conexão com banco via **SSL em produção** (`sslmode=require`)
- Decorators reutilizáveis `@login_required` e `@admin_required`
- Erros JWT diferenciados: token expirado vs. token inválido vs. erro interno

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
