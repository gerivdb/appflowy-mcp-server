"""
deploy_appflowy_lxc.py — Déploiement AppFlowy Cloud via KIVA LXC.

Crée 5 containers LXC pour self-host AppFlowy :
- appflowy-db (PostgreSQL 16)
- appflowy-redis (Redis 7)
- appflowy-gotrue (GoTrue auth)
- appflowy-cloud (AppFlowy API)
- appflowy-nginx (reverse proxy)

Piste 7 | Remplacement Notion | KIVA orchestration
"""

import logging
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'KIVA'))

logger = logging.getLogger(__name__)

# --- Configuration ---

CONTAINERS = [
    {
        "name": "appflowy-db",
        "image": "ubuntu/22.04",
        "cpu": 2,
        "memory": "4GB",
        "storage": "50GB",
        "profiles": ["default"],
        "config": {
            "user.post-init": """#!/bin/bash
apt-get update && apt-get install -y postgresql-16
sed -i "s/#listen_addresses = 'localhost'/listen_addresses = '*'/" /etc/postgresql/16/main/postgresql.conf
echo "host all all 10.0.0.0/8 md5" >> /etc/postgresql/16/main/pg_hba.conf
systemctl restart postgresql
sudo -u postgres psql -c "CREATE USER appflowy WITH PASSWORD 'appflowy_secret';"
sudo -u postgres psql -c "CREATE DATABASE appflowy OWNER appflowy;"
""",
        },
    },
    {
        "name": "appflowy-redis",
        "image": "ubuntu/22.04",
        "cpu": 1,
        "memory": "1GB",
        "storage": "5GB",
        "profiles": ["default"],
        "config": {
            "user.post-init": """#!/bin/bash
apt-get update && apt-get install -y redis-server
sed -i "s/bind 127.0.0.1/bind 0.0.0.0/" /etc/redis/redis.conf
systemctl restart redis-server
""",
        },
    },
    {
        "name": "appflowy-gotrue",
        "image": "ubuntu/22.04",
        "cpu": 1,
        "memory": "512MB",
        "storage": "1GB",
        "profiles": ["default"],
        "config": {
            "user.post-init": """#!/bin/bash
apt-get update && apt-get install -y wget
wget -O /usr/local/bin/gotrue https://github.com/supabase/gotrue/releases/latest/download/gotrue
chmod +x /usr/local/bin/gotrue
cat > /etc/gotrue.env << 'EOF'
GOTRUE_API_HOST=0.0.0.0
GOTRUE_API_PORT=9999
DATABASE_URL=postgres://appflowy:appflowy_secret@appflowy-db.lxd:5432/appflowy?search_path=auth
GOTRUE_JWT_SECRET=your-jwt-secret-change-me
GOTRUE_JWT_EXP=3600
GOTRUE_JWT_AUD=appflowy
GOTRUE_DISABLE_SIGNUP=false
EOF
""",
        },
    },
    {
        "name": "appflowy-cloud",
        "image": "ubuntu/22.04",
        "cpu": 4,
        "memory": "4GB",
        "storage": "10GB",
        "profiles": ["default"],
        "config": {
            "user.post-init": """#!/bin/bash
apt-get update && apt-get install -y wget
wget -O /usr/local/bin/appflowy_cloud https://github.com/AppFlowy-IO/AppFlowy-Cloud/releases/latest/download/appflowy_cloud
chmod +x /usr/local/bin/appflowy_cloud
cat > /etc/appflowy.env << 'EOF'
APPFLOWY_ENVIRONMENT=production
APPFLOWY_DATABASE_URL=postgres://appflowy:appflowy_secret@appflowy-db.lxd:5432/appflowy
APPFLOWY_REDIS_URI=redis://appflowy-redis.lxd:6379
APPFLOWY_GOTRUE_URL=http://appflowy-gotrue.lxd:9999
APPFLOWY_GOTRUE_JWT_SECRET=your-jwt-secret-change-me
APPFLOWY_WEBSOCKET_HOST=0.0.0.0
APPFLOWY_WEBSOCKET_PORT=8000
APPFLOWY_AI_SERVER_URL=http://localhost:5001
EOF
""",
        },
    },
    {
        "name": "appflowy-nginx",
        "image": "ubuntu/22.04",
        "cpu": 1,
        "memory": "512MB",
        "storage": "1GB",
        "profiles": ["default"],
        "config": {
            "user.post-init": """#!/bin/bash
apt-get update && apt-get install -y nginx
cat > /etc/nginx/sites-available/appflowy << 'NGINX'
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://appflowy-cloud.lxd:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    location /gotrue/ {
        proxy_pass http://appflowy-gotrue.lxd:9999/;
        proxy_set_header Host $host;
    }
}
NGINX
ln -sf /etc/nginx/sites-available/appflowy /etc/nginx/sites-enabled/
systemctl restart nginx
""",
        },
    },
]


def deploy():
    """Déploie AppFlowy Cloud via KIVA LXC."""
    try:
        from kiva.core.lxc_manager import LXCManager
    except ImportError:
        logger.error("KIVA non disponible. Installer pylxd: pip install pylxd")
        return False

    manager = LXCManager()

    if not manager.connect():
        logger.error("Impossible de se connecter à LXD")
        return False

    logger.info("Déploiement AppFlowy Cloud via KIVA LXC")

    for spec in CONTAINERS:
        name = spec["name"]
        logger.info("Creating container: %s", name)

        try:
            container = manager.create_container(
                name=name,
                image=spec["image"],
                cpu_limit=spec["cpu"],
                memory_limit=spec["memory"],
                profiles=spec.get("profiles", ["default"]),
            )

            if container:
                manager.start_container(name)
                logger.info("Container %s started", name)
            else:
                logger.error("Failed to create %s", name)

        except Exception as e:
            logger.error("Error deploying %s: %s", name, e)

    logger.info("Déploiement terminé. URLs:")
    logger.info("  AppFlowy Cloud: http://appflowy-cloud.lxd:8000")
    logger.info("  GoTrue Auth:    http://appflowy-gotrue.lxd:9999")
    logger.info("  Nginx Proxy:    http://appflowy-nginx.lxd")

    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    deploy()
