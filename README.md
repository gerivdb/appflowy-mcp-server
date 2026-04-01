# AppFlowy MCP Server

Serveur MCP pour interagir avec AppFlowy Cloud — remplacement de Notion.

## Outils MCP

| Outil | Description | Read-only |
|-------|-------------|-----------|
| `appflowy_auth_login` | Authentification GoTrue JWT | ❌ |
| `appflowy_list_workspaces` | Liste les workspaces | ✅ |
| `appflowy_create_workspace` | Crée un workspace | ❌ |
| `appflowy_create_page` | Crée une page/database | ❌ |
| `appflowy_get_page` | Récupère le contenu d'une page | ✅ |
| `appflowy_get_folder` | Structure hiérarchique du workspace | ✅ |
| `appflowy_search` | Recherche full-text | ✅ |
| `appflowy_get_collab` | Objet collaboratif | ✅ |
| `appflowy_list_members` | Membres du workspace | ✅ |
| `appflowy_invite_member` | Invite un membre | ❌ |
| `appflowy_health_check` | Vérifie la connectivité | ✅ |

## Configuration

```bash
export APPFLOWY_BASE_URL="https://api.appflowy.io"  # ou votre instance self-hosted
export APPFLOWY_TOKEN="votre_jwt_token"
```

## Migration Notion → AppFlowy

```bash
python src/migrate_notion_to_appflowy.py <workspace_id>
```

## Fichiers

- `src/appflowy_mcp.py` — Serveur MCP (11 outils)
- `src/migrate_notion_to_appflowy.py` — Script de migration
- `NOTION-TO-APPFLOWY-MAPPING.md` — Mapping des concepts
- `requirements.txt` — Dépendances Python
- `mcp.json` — Configuration MCP
