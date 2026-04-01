"""
AppFlowy MCP Server — Équivalent Notion MCP pour l'écosystème ECOS.

Fournit des outils MCP pour interagir avec AppFlowy Cloud :
- Gestion des workspaces, pages, espaces
- CRUD collaboratif (documents, bases de données)
- Recherche et indexation
- Publishing

API: https://github.com/AppFlowy-IO/AppFlowy-Cloud
Piste 7 | Remplacement Notion
"""

import os
import json
import logging
from typing import Optional, List, Dict, Any
from enum import Enum

import httpx
from pydantic import BaseModel, Field, ConfigDict
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

# --- Configuration ---

APPFLOWY_BASE_URL = os.environ.get("APPFLOWY_BASE_URL", "https://api.appflowy.io")
APPFLOWY_GOTRUE_URL = os.environ.get("APPFLOWY_GOTRUE_URL", f"{APPFLOWY_BASE_URL}/gotrue")
APPFLOWY_WS_URL = os.environ.get("APPFLOWY_WS_URL", f"wss://api.appflowy.io/ws")
CHARACTER_LIMIT = 25000

mcp = FastMCP("appflowy_mcp")


# --- Models ---

class AFRole(str, Enum):
    OWNER = "Owner"
    MEMBER = "Member"
    GUEST = "Guest"


class AFViewType(str, Enum):
    DOCUMENT = "document"
    GRID = "grid"
    BOARD = "board"
    CALENDAR = "calendar"
    SPACE = "space"


# --- HTTP Client ---

class AppFlowyClient:
    """Client HTTP pour AppFlowy Cloud API."""

    def __init__(self, base_url: str = "", token: str = ""):
        self.base_url = (base_url or APPFLOWY_BASE_URL).rstrip("/")
        self.token = token or os.environ.get("APPFLOWY_TOKEN", "")
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    async def request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        resp = await self.client.request(method, path, **kwargs)
        resp.raise_for_status()
        return resp.json()

    async def close(self):
        await self.client.aclose()


_client: Optional[AppFlowyClient] = None


def get_client() -> AppFlowyClient:
    global _client
    if _client is None:
        _client = AppFlowyClient()
    return _client


# --- Auth Tools ---

class AuthLoginInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(..., description="Email utilisateur")
    password: str = Field(..., description="Mot de passe")


@mcp.tool(name="appflowy_auth_login", annotations={"readOnlyHint": False, "destructiveHint": False})
async def appflowy_auth_login(params: AuthLoginInput) -> str:
    """Authentification avec AppFlowy Cloud via GoTrue.

    Retourne un access_token JWT pour les appels suivants.
    À utiliser une fois au début de session.
    """
    async with httpx.AsyncClient() as hc:
        resp = await hc.post(
            f"{APPFLOWY_GOTRUE_URL}/token?grant_type=password",
            json={"email": params.email, "password": params.password},
        )
        resp.raise_for_status()
        data = resp.json()
        token = data.get("access_token", "")
        os.environ["APPFLOWY_TOKEN"] = token
        global _client
        _client = AppFlowyClient(token=token)
        return json.dumps({"access_token": token[:20] + "...", "expires_in": data.get("expires_in")})


# --- Workspace Tools ---

class CreateWorkspaceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., description="Nom du workspace")


@mcp.tool(name="appflowy_list_workspaces", annotations={"readOnlyHint": True})
async def appflowy_list_workspaces() -> str:
    """Liste tous les workspaces de l'utilisateur authentifié.

    Retourne les IDs, noms, et rôles de chaque workspace.
    """
    client = get_client()
    data = await client.request("GET", "/api/workspace")
    workspaces = data if isinstance(data, list) else data.get("workspaces", [])
    result = []
    for ws in workspaces[:20]:
        result.append({
            "workspace_id": ws.get("workspace_id", ""),
            "name": ws.get("workspace_name", ""),
            "role": ws.get("role", ""),
        })
    return json.dumps(result, indent=2)


@mcp.tool(name="appflowy_create_workspace", annotations={"readOnlyHint": False, "destructiveHint": False})
async def appflowy_create_workspace(params: CreateWorkspaceInput) -> str:
    """Crée un nouveau workspace dans AppFlowy.

    Le workspace est vide par défaut. Utiliser appflowy_create_page pour ajouter du contenu.
    """
    client = get_client()
    data = await client.request("POST", "/api/workspace", json={"workspace_name": params.name})
    return json.dumps(data, indent=2)


# --- Page/View Tools ---

class CreatePageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workspace_id: str = Field(..., description="ID du workspace")
    name: str = Field(..., description="Nom de la page")
    view_type: AFViewType = Field(AFViewType.DOCUMENT, description="Type de vue")
    parent_view_id: Optional[str] = Field(None, description="ID du parent (None = racine)")


class GetPageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workspace_id: str = Field(..., description="ID du workspace")
    view_id: str = Field(..., description="ID de la page")


@mcp.tool(name="appflowy_create_page", annotations={"readOnlyHint": False, "destructiveHint": False})
async def appflowy_create_page(params: CreatePageInput) -> str:
    """Crée une nouvelle page dans un workspace AppFlowy.

    Types supportés : document, grid, board, calendar, space.
    Pour les databases, utiliser grid/board/calendar.
    """
    client = get_client()
    body: Dict[str, Any] = {
        "name": params.name,
        "view_type": params.view_type.value,
    }
    if params.parent_view_id:
        body["parent_view_id"] = params.parent_view_id

    data = await client.request(
        "POST",
        f"/api/workspace/{params.workspace_id}/page-view",
        json=body,
    )
    return json.dumps(data, indent=2)


@mcp.tool(name="appflowy_get_page", annotations={"readOnlyHint": True})
async def appflowy_get_page(params: GetPageInput) -> str:
    """Récupère le contenu d'une page AppFlowy.

    Retourne les blocks de contenu, métadonnées, et structure hiérarchique.
    """
    client = get_client()
    data = await client.request(
        "GET",
        f"/api/workspace/{params.workspace_id}/page-view/{params.view_id}",
    )
    result = json.dumps(data, indent=2)
    return result[:CHARACTER_LIMIT] if len(result) > CHARACTER_LIMIT else result


@mcp.tool(name="appflowy_get_folder", annotations={"readOnlyHint": True})
async def appflowy_get_folder(workspace_id: str) -> str:
    """Récupère la structure hiérarchique complète d'un workspace.

    Retourne l'arbre des views (pages, databases, espaces).
    Limite : 25000 caractères.
    """
    client = get_client()
    data = await client.request("GET", f"/api/workspace/{workspace_id}/folder")
    result = json.dumps(data, indent=2)
    return result[:CHARACTER_LIMIT] if len(result) > CHARACTER_LIMIT else result


# --- Search Tools ---

class SearchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(..., description="Requête de recherche")
    workspace_id: Optional[str] = Field(None, description="Filtrer par workspace")
    limit: int = Field(10, description="Nombre max de résultats", ge=1, le=50)


@mcp.tool(name="appflowy_search", annotations={"readOnlyHint": True})
async def appflowy_search(params: SearchInput) -> str:
    """Recherche full-text dans AppFlowy Cloud.

    Cherche dans tous les documents, pages et databases.
    Retourne les résultats avec score de pertinence.
    """
    client = get_client()
    body: Dict[str, Any] = {"query": params.query, "limit": params.limit}
    if params.workspace_id:
        body["workspace_id"] = params.workspace_id

    data = await client.request("POST", "/api/search", json=body)
    results = data.get("items", data) if isinstance(data, dict) else data
    return json.dumps(results[:params.limit], indent=2)


# --- Collab Tools ---

class CollabGetInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workspace_id: str = Field(..., description="ID du workspace")
    object_id: str = Field(..., description="ID de l'objet collaboratif")


@mcp.tool(name="appflowy_get_collab", annotations={"readOnlyHint": True})
async def appflowy_get_collab(params: CollabGetInput) -> str:
    """Récupère un objet collaboratif (document, database).

    Retourne le contenu binaire/JSON de l'objet.
    """
    client = get_client()
    data = await client.request(
        "GET",
        f"/api/workspace/{params.workspace_id}/collab/{params.object_id}",
    )
    return json.dumps(data, indent=2)[:CHARACTER_LIMIT]


# --- Member Tools ---

class InviteMemberInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workspace_id: str = Field(..., description="ID du workspace")
    email: str = Field(..., description="Email du membre à inviter")
    role: AFRole = Field(AFRole.MEMBER, description="Rôle du membre")


@mcp.tool(name="appflowy_list_members", annotations={"readOnlyHint": True})
async def appflowy_list_members(workspace_id: str) -> str:
    """Liste les membres d'un workspace avec leurs rôles.

    Retourne email, rôle, et date d'adhésion.
    """
    client = get_client()
    data = await client.request("GET", f"/api/workspace/{workspace_id}/member")
    return json.dumps(data, indent=2)


@mcp.tool(name="appflowy_invite_member", annotations={"readOnlyHint": False, "destructiveHint": False})
async def appflowy_invite_member(params: InviteMemberInput) -> str:
    """Invite un membre dans un workspace AppFlowy.

    Envoie une invitation par email avec le rôle spécifié.
    """
    client = get_client()
    data = await client.request(
        "POST",
        f"/api/workspace/{params.workspace_id}/invite",
        json={"email": params.email, "role": params.role.value},
    )
    return json.dumps(data, indent=2)


# --- Health ---

@mcp.tool(name="appflowy_health_check", annotations={"readOnlyHint": True})
async def appflowy_health_check() -> str:
    """Vérifie la connectivité avec AppFlowy Cloud.

    Utile pour diagnostiquer les problèmes de connexion.
    """
    try:
        async with httpx.AsyncClient() as hc:
            resp = await hc.get(f"{APPFLOWY_BASE_URL}/health", timeout=5.0)
            return json.dumps({"status": "ok" if resp.status_code == 200 else "error", "code": resp.status_code})
    except Exception as e:
        return json.dumps({"status": "unreachable", "error": str(e)})


# --- Entry Point ---

if __name__ == "__main__":
    mcp.run()
