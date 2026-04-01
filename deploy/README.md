# AppFlowy Cloud — Déploiement LXC via KIVA

**Date** : 2026-04-02 | **Piste 7**
**Infrastructure** : HP Z600 (24 threads, 48GB RAM, 4TB ZFS)

---

## Architecture LXC

```
KIVA orchestrateur
    │
    ├─ appflowy-db       (LXC)  PostgreSQL 16 — données AppFlowy
    ├─ appflowy-redis    (LXC)  Redis 7 — cache + sessions
    ├─ appflowy-gotrue   (LXC)  GoTrue — authentification JWT
    ├─ appflowy-cloud    (LXC)  AppFlowy Cloud API (port 8000)
    └─ appflowy-nginx    (LXC)  Nginx reverse proxy (port 443)
```

## Ressources allouées

| Container | CPU | RAM | Storage | Port host |
|-----------|-----|-----|---------|-----------|
| appflowy-db | 2 | 4GB | 50GB ZFS | 5432 |
| appflowy-redis | 1 | 1GB | 5GB ZFS | 6379 |
| appflowy-gotrue | 1 | 512MB | 1GB | 9999 |
| appflowy-cloud | 4 | 4GB | 10GB | 8000 |
| appflowy-nginx | 1 | 512MB | 1GB | 443 |
| **Total** | **9** | **10GB** | **67GB** | — |

## Déploiement

```bash
# Via KIVA CLI
cd D:/DO/WEB/TOOLS/KIVA
python -m kiva.cli deploy --config ../appflowy-mcp-server/deploy/appflowy-lxc.yaml

# Ou via script Python
python D:/DO/WEB/TOOLS/appflowy-mcp-server/deploy/deploy_appflowy_lxc.py
```

## Variables d'environnement

```bash
APPFLOWY_BASE_URL=http://appflowy-cloud.lxd:8000
APPFLOWY_GOTRUE_URL=http://appflowy-gotrue.lxd:9999
APPFLOWY_WS_URL=ws://appflowy-cloud.lxd:8000/ws
```
