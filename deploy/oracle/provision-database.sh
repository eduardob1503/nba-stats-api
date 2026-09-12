#!/usr/bin/env bash
set -euo pipefail

db_role="nba_api"
db_name="nba"
db_password="$(openssl rand -hex 24)"
secret_key="$(openssl rand -hex 32)"
sync_token="$(openssl rand -hex 32)"

if sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='${db_role}'" | grep -q 1; then
  sudo -u postgres psql -v ON_ERROR_STOP=1 -c "ALTER ROLE ${db_role} WITH LOGIN PASSWORD '${db_password}';"
else
  sudo -u postgres psql -v ON_ERROR_STOP=1 -c "CREATE ROLE ${db_role} WITH LOGIN PASSWORD '${db_password}';"
fi

if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${db_name}'" | grep -q 1; then
  sudo -u postgres createdb --owner="${db_role}" "${db_name}"
fi

env_tmp="$(mktemp)"
chmod 600 "${env_tmp}"
{
  printf 'DATABASE_URL=postgresql://%s:%s@127.0.0.1:5432/%s?sslmode=disable\n' "${db_role}" "${db_password}" "${db_name}"
  printf 'SECRET_KEY=%s\n' "${secret_key}"
  printf 'SYNC_TOKEN=%s\n' "${sync_token}"
  printf '%s\n' 'ENV=production'
  printf '%s\n' 'AUTO_MIGRATE=true'
  printf '%s\n' 'ADMIN_EMAILS=barcelos.eduardo1503@gmail.com'
  printf '%s\n' 'FIRST_USER_ADMIN=false'
  printf '%s\n' 'NBA_API_TIMEOUT=20'
  printf '%s\n' 'NBA_SYNC_SEASON=2025-26'
  printf '%s\n' 'CORS_ORIGINS=https://nba-prop-insights-sfwg.vercel.app,http://localhost:8080,http://127.0.0.1:8080,http://localhost:5173,http://127.0.0.1:5173'
} > "${env_tmp}"

sudo install -o root -g root -m 600 "${env_tmp}" /etc/nba-stats-api.env
rm -f "${env_tmp}"

echo "PostgreSQL database and application environment configured."
