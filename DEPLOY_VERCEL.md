# Publicar o backend no Vercel

O backend Flask é detectado automaticamente pelo Vercel através do `app.py`.
A versão do Python, o tempo máximo da função e os arquivos excluídos do pacote
estão configurados no repositório.

## 1. Criar o projeto do backend

1. No Vercel, importe o repositório `eduardob1503/nba-stats-api`.
2. Em **Production Branch**, selecione `codex` enquanto o trabalho não estiver
   mesclado na `main`.
3. Não informe Build Command nem Output Directory; o Vercel detecta Flask.

## 2. Criar o PostgreSQL hospedado

Em **Storage**, instale o Neon Postgres e conecte-o a este projeto. A integração
cria a variável `DATABASE_URL`. O PostgreSQL que roda no computador local não é
acessível pelas funções do Vercel.

## 3. Configurar variáveis

Adicione em **Settings > Environment Variables**:

```env
ENV=production
SECRET_KEY=gere-uma-chave-aleatoria-de-64-caracteres
DATABASE_URL=fornecida-automaticamente-pelo-neon
CORS_ORIGINS=https://SEU-FRONTEND.vercel.app
ADMIN_EMAILS=seu-email@exemplo.com
AUTO_MIGRATE=true
FIRST_USER_ADMIN=false
NBA_API_TIMEOUT=25
```

`ADMIN_EMAILS` pode conter mais de um e-mail separado por vírgula. Somente os
cadastros feitos com esses e-mails recebem acesso administrativo.

`AUTO_MIGRATE=true` aplica as migrações idempotentes e inclui os jogadores
iniciais quando a função for inicializada. Após confirmar o primeiro deploy,
ela pode permanecer ativa ou ser alterada para `false`.

## 4. Ordem da publicação

1. Publique o backend.
2. Teste `https://SEU-BACKEND.vercel.app/health`.
3. Copie a URL do backend para a variável `VITE_API_BASE_URL` do frontend.
4. Publique o frontend.
5. Volte ao backend, preencha `CORS_ORIGINS` com a URL exata do frontend e faça
   um redeploy.

Não coloque `SECRET_KEY` ou `DATABASE_URL` em arquivos versionados.
