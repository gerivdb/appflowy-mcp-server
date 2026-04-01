# Mapping Notion → AppFlowy

**Date** : 2026-04-02 | **Piste 7**

---

## Concepts

| Notion | AppFlowy | Notes |
|--------|----------|-------|
| Workspace | Workspace | Équivalent direct |
| Database | Database (Grid/Board/Calendar) | AppFlowy = "view" de type database |
| Page | Document | AppFlowy = "view" de type document |
| Block | Block (CRDT) | AppFlowy utilise CRDT (Yjs) pour le temps réel |
| Property | Column (database) | Propriétés de colonne dans les databases |
| Relation | Relation column | ⚠️ API REST incomplète (issue #8145) |
| Rollup | — | ⚠️ Non supporté dans l'API REST |
| Formula | — | ⚠️ Non supporté dans l'API REST |
| Template | — | ⚠️ Pas d'API template |
| Comment | — | ⚠️ Pas d'API commentaire |
| User | User | Équivalent via GoTrue auth |
| Permission | Role (Owner/Member/Guest) | Moins granulaire que Notion |
| Webhook | — | ⚠️ En développement |
| Search | Search API | Full-text disponible |

---

## Endpoints

| Notion API | AppFlowy API | Méthode |
|------------|-------------|---------|
| `GET /v1/databases/{id}` | `GET /api/workspace/{ws}/collab/{id}` | GET |
| `POST /v1/databases` | `POST /api/workspace/{ws}/page-view` (view_type=grid) | POST |
| `GET /v1/pages/{id}` | `GET /api/workspace/{ws}/page-view/{id}` | GET |
| `POST /v1/pages` | `POST /api/workspace/{ws}/page-view` | POST |
| `PATCH /v1/pages/{id}` | `PATCH /api/workspace/{ws}/page-view/{id}` | PATCH |
| `GET /v1/search` | `POST /api/search` | POST |
| `POST /v1/blocks/{id}/children` | Via CRDT WebSocket | WS |
| `GET /v1/users` | `GET /api/workspace/{ws}/member` | GET |
| `POST /v1/databases/{id}/query` | Via CRDT WebSocket | WS |

---

## Limitations connues

| Feature Notion | Status AppFlowy | Workaround |
|----------------|----------------|------------|
| Relations | API partielle | Utiliser les CRDT directement |
| Rollup | Non supporté | Calculer côté client |
| Formula | Non supporté | Calculer côté client |
| Webhooks | En développement | Polling sur search API |
| Permissions granulaires | Owner/Member/Guest uniquement | Gérer via workspaces séparés |
| Templates | Pas d'API | Créer manuellement puis dupliquer |
| Comments | Pas d'API | Stocker dans un document séparé |

---

## Authentification

| Notion | AppFlowy |
|--------|----------|
| OAuth2 (internal integration) | GoTrue JWT |
| `Authorization: Bearer {notion_token}` | `Authorization: Bearer {appflowy_token}` |
| Token statique | Token + refresh_token (auto) |

---

## Stratégie de migration

1. **Phase 1** : Créer les workspaces AppFlowy équivalents
2. **Phase 2** : Migrer les pages/documents (contenu texte)
3. **Phase 3** : Migrer les databases (structure + données)
4. **Phase 4** : Reconstruire les relations manuellement
5. **Phase 5** : Valider la recherche et les permissions

---

*Mapping v1.0 | 2026-04-02*
