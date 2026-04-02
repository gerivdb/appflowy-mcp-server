#!/bin/bash
# ============================================================
# AppFlowy Cloud — Déploiement LXC via KIVA sur HP Z600
# ============================================================
# Usage: ssh hp-z600 'bash -s' < deploy_appflowy_kiva.sh
# Ou: copier ce script sur le HP Z600 et exécuter
# ============================================================

set -e

echo "=== AppFlowy Cloud LXC Deployment via KIVA ==="
echo "Date: $(date)"
echo "Host: $(hostname)"

# --- Vérifications ---
echo ""
echo "[1/7] Vérification LXD..."
if ! command -v lxc &> /dev/null; then
    echo "ERREUR: LXD non installé. Installation..."
    sudo snap install lxd --channel=5.21/stable
    sudo lxd init --auto
fi
echo "  LXD version: $(lxd --version)"

echo ""
echo "[2/7] Vérification réseau LXD..."
lxc network list | grep -q "lxdbr0" || {
    echo "  Création bridge lxdbr0..."
    lxc network create lxdbr0
    lxc network set lxdbr0 ipv4.address 10.0.0.1/24
    lxc network set lxdbr0 ipv4.nat true
}
echo "  Réseau: lxdbr0 (10.0.0.1/24)"

# --- Création des containers ---
echo ""
echo "[3/7] Création container: appflowy-db (PostgreSQL 16)..."
lxc launch ubuntu:22.04 appflowy-db -c limits.cpu=2 -c limits.memory=4GB
sleep 5
lxc exec appflowy-db -- bash -c "
apt-get update -qq && apt-get install -y -qq postgresql-16 > /dev/null 2>&1
sed -i \"s/#listen_addresses = 'localhost'/listen_addresses = '*'/\" /etc/postgresql/16/main/postgresql.conf
echo 'host all all 10.0.0.0/8 md5' >> /etc/postgresql/16/main/pg_hba.conf
systemctl restart postgresql
sudo -u postgres psql -c \"CREATE USER appflowy WITH PASSWORD 'ECOS_AppFlowy_2026!';\"
sudo -u postgres psql -c \"CREATE DATABASE appflowy OWNER appflowy;\"
sudo -u postgres psql -c \"CREATE SCHEMA IF NOT EXISTS auth AUTHORIZATION appflowy;\"
echo 'PostgreSQL ready'
"
DB_IP=$(lxc list appflowy-db -c 4 --format csv | cut -d' ' -f1)
echo "  appflowy-db: $DB_IP"

echo ""
echo "[4/7] Création container: appflowy-redis (Redis 7)..."
lxc launch ubuntu:22.04 appflowy-redis -c limits.cpu=1 -c limits.memory=1GB
sleep 5
lxc exec appflowy-redis -- bash -c "
apt-get update -qq && apt-get install -y -qq redis-server > /dev/null 2>&1
sed -i 's/bind 127.0.0.1/bind 0.0.0.0/' /etc/redis/redis.conf
sed -i 's/# requirepass/requirepass ECOS_Redis_2026!/' /etc/redis/redis.conf
systemctl restart redis-server
echo 'Redis ready'
"
REDIS_IP=$(lxc list appflowy-redis -c 4 --format csv | cut -d' ' -f1)
echo "  appflowy-redis: $REDIS_IP"

echo ""
echo "[5/7] Création container: appflowy-gotrue (GoTrue auth)..."
lxc launch ubuntu:22.04 appflowy-gotrue -c limits.cpu=1 -c limits.memory=512MB
sleep 5
lxc exec appflowy-gotrue -- bash -c "
apt-get update -qq && apt-get install -y -qq wget > /dev/null 2>&1
wget -q -O /usr/local/bin/gotrue https://github.com/supabase/gotrue/releases/latest/download/gotrue_linux_amd64
chmod +x /usr/local/bin/gotrue
cat > /etc/gotrue.env << ENVEOF
API_HOST=0.0.0.0
API_PORT=9999
DB_DATABASE_URL=postgres://appflowy:ECOS_AppFlowy_2026!@${DB_IP}:5432/appflowy?search_path=auth
JWT_SECRET=ecos-appflowy-jwt-secret-2026-hp-z600-64chars-random-string
JWT_EXP=3600
JWT_AUD=appflowy
DISABLE_SIGNUP=false
GOTRUE_DB_DRIVER=postgres
ENVEOF
cat > /etc/systemd/system/gotrue.service << SVCEOF
[Unit]
Description=GoTrue Auth Service
After=network.target

[Service]
Type=simple
EnvironmentFile=/etc/gotrue.env
ExecStart=/usr/local/bin/gotrue
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SVCEOF
systemctl daemon-reload
systemctl enable gotrue
systemctl start gotrue
echo 'GoTrue ready'
"
GOTRUE_IP=$(lxc list appflowy-gotrue -c 4 --format csv | cut -d' ' -f1)
echo "  appflowy-gotrue: $GOTRUE_IP"

echo ""
echo "[6/7] Création container: appflowy-cloud (AppFlowy API)..."
lxc launch ubuntu:22.04 appflowy-cloud -c limits.cpu=4 -c limits.memory=4GB
sleep 5
lxc exec appflowy-cloud -- bash -c "
apt-get update -qq && apt-get install -y -qq wget > /dev/null 2>&1
ARCH=\$(uname -m)
if [ \"\$ARCH\" = \"x86_64\" ]; then
    wget -q -O /usr/local/bin/appflowy_cloud https://github.com/AppFlowy-IO/AppFlowy-Cloud/releases/latest/download/appflowy_cloud-linux-amd64
else
    wget -q -O /usr/local/bin/appflowy_cloud https://github.com/AppFlowy-IO/AppFlowy-Cloud/releases/latest/download/appflowy_cloud-linux-arm64
fi
chmod +x /usr/local/bin/appflowy_cloud
cat > /etc/appflowy.env << ENVEOF
APPFLOWY_ENVIRONMENT=production
APPFLOWY_DATABASE_URL=postgres://appflowy:ECOS_AppFlowy_2026!@${DB_IP}:5432/appflowy
APPFLOWY_REDIS_URI=redis://:ECOS_Redis_2026!@${REDIS_IP}:6379
APPFLOWY_GOTRUE_URL=http://${GOTRUE_IP}:9999
APPFLOWY_GOTRUE_JWT_SECRET=ecos-appflowy-jwt-secret-2026-hp-z600-64chars-random-string
APPFLOWY_WEBSOCKET_HOST=0.0.0.0
APPFLOWY_WEBSOCKET_PORT=8000
APPFLOWY_MINIO_URL=http://localhost:9000
APPFLOWY_MINIO_ACCESS_KEY=minioadmin
APPFLOWY_MINIO_SECRET_KEY=ECOS_MinIO_2026!
ENVEOF
cat > /etc/systemd/system/appflowy-cloud.service << SVCEOF
[Unit]
Description=AppFlowy Cloud API
After=network.target

[Service]
Type=simple
EnvironmentFile=/etc/appflowy.env
ExecStart=/usr/local/bin/appflowy_cloud
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SVCEOF
systemctl daemon-reload
systemctl enable appflowy-cloud
systemctl start appflowy-cloud
echo 'AppFlowy Cloud ready'
"
CLOUD_IP=$(lxc list appflowy-cloud -c 4 --format csv | cut -d' ' -f1)
echo "  appflowy-cloud: $CLOUD_IP"

echo ""
echo "[7/7] Vérification des services..."
sleep 10
echo ""
echo "=== Status ==="
for c in appflowy-db appflowy-redis appflowy-gotrue appflowy-cloud; do
    STATUS=$(lxc list $c -c s --format csv)
    IP=$(lxc list $c -c 4 --format csv | cut -d' ' -f1)
    echo "  $c: $STATUS ($IP)"
done

echo ""
echo "=== AppFlowy Cloud déployé ==="
echo ""
echo "Containers LXC:"
echo "  appflowy-db       : $DB_IP (PostgreSQL 16)"
echo "  appflowy-redis    : $REDIS_IP (Redis 7)"
echo "  appflowy-gotrue   : $GOTRUE_IP (GoTrue auth :9999)"
echo "  appflowy-cloud    : $CLOUD_IP (AppFlowy API :8000)"
echo ""
echo "URLs internes:"
echo "  API    : http://$CLOUD_IP:8000"
echo "  Auth   : http://$GOTRUE_IP:9999"
echo ""
echo "Pour obtenir le token JWT:"
echo "  curl -s -X POST 'http://$CLOUD_IP:8000/gotrue/token?grant_type=password' \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"email\":\"gerivonderbitsh@gmail.com\",\"password\":\"789fuckyl*GGV\"}'"
echo ""
echo "Pour accéder depuis le réseau:"
echo "  lxc network forward create lxdbr0 0.0.0.0"
echo "  lxc network forward port add lxdbr0 0.0.0.0 tcp 8000 $CLOUD_IP 8000"
echo "  lxc network forward port add lxdbr0 0.0.0.0 tcp 9999 $GOTRUE_IP 9999"
