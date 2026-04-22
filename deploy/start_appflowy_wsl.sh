#!/bin/bash
# AppFlowy Cloud — Startup script for WSL
# PostgreSQL + GoTrue (AppFlowy Cloud needs Rust to build, using GoTrue only for now)

# Start PostgreSQL
service postgresql start 2>/dev/null
sleep 3

# Start Redis
service redis-server start 2>/dev/null
sleep 2

# Start GoTrue
pkill gotrue 2>/dev/null
sleep 2

DATABASE_URL='postgres://appflowy:ECOS_AppFlowy_2026!@localhost:5432/appflowy?search_path=auth' \
API_EXTERNAL_URL='http://localhost:9999' \
GOTRUE_SITE_URL='http://localhost' \
GOTRUE_API_HOST='0.0.0.0' \
GOTRUE_API_PORT='9999' \
GOTRUE_DB_DRIVER='postgres' \
GOTRUE_JWT_SECRET='ecos-appflowy-jwt-secret-2026-hp-z600-64chars-random-string-abc123' \
GOTRUE_JWT_EXP='3600' \
GOTRUE_JWT_AUD='appflowy' \
GOTRUE_DISABLE_SIGNUP='false' \
GOTRUE_MAILER_AUTOCONFIRM='true' \
GOTRUE_EXTERNAL_GOOGLE_ENABLED='false' \
GOTRUE_EXTERNAL_GITHUB_ENABLED='false' \
GOTRUE_EXTERNAL_DISCORD_ENABLED='false' \
GOTRUE_SAML_ENABLED='false' \
GOTRUE_RATE_LIMIT_EMAIL_SENT='100' \
nohup /usr/local/bin/gotrue > /var/log/gotrue.log 2>&1 &

sleep 8

# Create user and get token
curl -s -X POST http://localhost:9999/signup \
  -H 'Content-Type: application/json' \
  -d '{"email":"gerivonderbitsh@gmail.com","password":"789fuckyl*GGV"}' > /dev/null 2>&1

curl -s -X POST 'http://localhost:9999/token?grant_type=password' \
  -H 'Content-Type: application/json' \
  -d '{"email":"gerivonderbitsh@gmail.com","password":"789fuckyl*GGV"}' > /tmp/appflowy_token.json 2>&1

echo "TOKEN_FILE=/tmp/appflowy_token.json"
cat /tmp/appflowy_token.json | python3 -c "import json,sys; print(json.load(sys.stdin).get('access_token','ERROR'))" 2>/dev/null
