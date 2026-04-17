# 🏀 NBA Stats API

API RESTful construída com **Flask** e **PostgreSQL** para consulta e gerenciamento de estatísticas de jogadores da NBA, com autenticação JWT e controle de acesso por roles.

---

## 🚀 Tecnologias

- **Python 3** + **Flask** — framework web
- **PostgreSQL** — banco de dados relacional
- **psycopg2** — driver PostgreSQL para Python
- **JWT (PyJWT)** — autenticação stateless
- **bcrypt** — hash seguro de senhas
- **python-dotenv** — gerenciamento de variáveis de ambiente

---

## 📁 Estrutura do Projeto

```
nba-stats-api/
├── app.py          # Rotas principais e decorators de autenticação
├── auth.py         # Lógica de cadastro, login e conexão com o banco
├── .env            # Variáveis de ambiente (não versionar)
├── .gitignore
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
git clone https://github.com/seu-usuario/nba-stats-api.git
cd nba-stats-api
```

### 2. Instale as dependências

```bash
pip install flask psycopg2-binary pyjwt bcrypt python-dotenv email-validator
```

### 3. Configure o `.env`

Crie um arquivo `.env` na raiz do projeto:

```env
host=localhost
port=5432
user=postgres
password=sua_senha
database=nba
SECRET_KEY=sua_chave_secreta_aqui
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
    nome VARCHAR(100)
);

CREATE TABLE ppg (
    id SERIAL PRIMARY KEY,
    id_jogador VARCHAR(20) REFERENCES jogadores(code_jogador),
    pontos NUMERIC
);
```

### 5. Suba a API

```bash
python app.py
```

A API estará disponível em `http://localhost:5000`.

---

## 🔐 Autenticação

A API usa **JWT Bearer Token**. Para acessar rotas protegidas, inclua o token no header:

```
Authorization: Bearer <seu_token>
```

Existem dois níveis de acesso:

| Role | Permissões |
| Usuário logado | Consultar jogadores e estatísticas |
| Admin | Criar, editar e deletar jogadores e pontuações |

---

## 📌 Endpoints

### Autenticação

#### `POST /cadastro`
Cria um novo usuário.

**Body:**
```json
{
  "nome": "João Silva",
  "email": "joao@email.com",
  "senha": "minhasenha123"
}
```

**Resposta 200:**
```json
"usuario criado com sucesso"
```

---

#### `POST /login`
Autentica o usuário e retorna um token JWT válido por 1 hora.

**Body:**
```json
{
  "email": "joao@email.com",
  "senha": "minhasenha123"
}
```

**Resposta 200:**
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

---

### Jogadores

#### `GET /jogadores` 🔒 Login
Lista todos os jogadores cadastrados.

**Resposta 200:**
```json
[
  { "id": "jamesle01", "nome": "LeBron James" },
  { "id": "curryst01", "nome": "Stephen Curry" }
]
```

---

#### `GET /jogadores/<code>` 🔒 Login
Retorna as estatísticas de pontuação de um jogador.

**Exemplo:** `GET /jogadores/jamesle01`

**Resposta 200 (com pontos registrados):**
```json
{
  "id": "jamesle01",
  "pontos": [28, 31, 19, 24],
  "id_partida": [1, 2, 3, 4],
  "media": 25.5,
  "jogos": 4
}
```

**Resposta 200 (sem pontos ainda):**
```json
{
  "code": "jamesle01",
  "nome": "LeBron James"
}
```

---

#### `POST /jogadores` 🔒 Admin
Cadastra um novo jogador. O `code` é gerado automaticamente a partir do nome.

**Body:**
```json
{
  "nome": "LeBron James"
}
```

**Resposta 201:**
```json
{
  "nome": "LeBron James",
  "code": "jamesle01"
}
```

---

#### `POST /jogadores/<code>` 🔒 Admin
Adiciona registros de pontuação para um jogador.

**Exemplo:** `POST /jogadores/jamesle01`

**Body:**
```json
{
  "pontos": [28, 31, 19]
}
```

**Resposta 201:**
```json
{
  "pontos": [28, 31, 19]
}
```

---

#### `DELETE /jogadores/<code>` 🔒 Admin
Remove um jogador e todos os seus registros de pontuação.

**Exemplo:** `DELETE /jogadores/jamesle01`

**Resposta 200:**
```json
{
  "mensagem": "jogador deletado"
}
```

---

## 🛡️ Segurança

- Senhas armazenadas com **bcrypt** (hash + salt)
- Tokens JWT com **expiração de 1 hora**
- Credenciais do banco isoladas em **variáveis de ambiente**
- Rotas protegidas por **decorators** reutilizáveis (`@login_required`, `@admin_required`)
- Tratamento granular de erros JWT: token expirado vs. token inválido

---

## 📊 Próximos passos

- [ ] Context manager para gerenciamento automático de conexões
- [ ] Rate limiting no `/login` contra brute force
- [ ] Endpoints de tendência e consistência para análise de apostas
- [ ] Integração com dados reais via `nba_api`
- [ ] Documentação automática com Swagger (Flask-RESTX)
- [ ] Docker Compose para deploy simplificado

---

## 👨‍💻 Autor

Feito por **Eduardo Barcelos Viana** · [LinkedIn](https://linkedin.com/in/eduardo-viana1503) · [GitHub](https://github.com/eduardob1503)
