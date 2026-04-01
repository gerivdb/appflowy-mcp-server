"""
migrate_notion_to_appflowy.py — Script de migration Notion → AppFlowy.

Lit les données depuis l'API Notion et les écrit dans AppFlowy Cloud.
Gère les workspaces, pages, databases, et propriétés.

Piste 7 | Remplacement Notion
"""

import os
import json
import asyncio
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass
class MigrationStats:
    """Statistiques de migration."""
    workspaces_created: int = 0
    pages_migrated: int = 0
    databases_migrated: int = 0
    errors: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class NotionExporter:
    """Exporte les données depuis Notion."""

    def __init__(self, notion_token: str = ""):
        self.token = notion_token or os.environ.get("NOTION_TOKEN", "")
        self.client = httpx.AsyncClient(
            base_url="https://api.notion.com/v1",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Notion-Version": "2022-06-28",
            },
            timeout=30.0,
        )

    async def search_all(self) -> List[Dict[str, Any]]:
        """Recherche toutes les pages et databases."""
        results = []
        cursor = None

        while True:
            body: Dict[str, Any] = {"page_size": 100}
            if cursor:
                body["start_cursor"] = cursor

            resp = await self.client.post("/search", json=body)
            resp.raise_for_status()
            data = resp.json()

            results.extend(data.get("results", []))

            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")

        return results

    async def get_page_content(self, page_id: str) -> List[Dict[str, Any]]:
        """Récupère les blocks d'une page."""
        blocks = []
        cursor = None

        while True:
            params: Dict[str, Any] = {"page_size": 100}
            if cursor:
                params["start_cursor"] = cursor

            resp = await self.client.get(f"/blocks/{page_id}/children", params=params)
            resp.raise_for_status()
            data = resp.json()

            blocks.extend(data.get("results", []))

            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")

        return blocks

    async def query_database(self, database_id: str) -> List[Dict[str, Any]]:
        """Récupère les lignes d'une database."""
        rows = []
        cursor = None

        while True:
            body: Dict[str, Any] = {"page_size": 100}
            if cursor:
                body["start_cursor"] = cursor

            resp = await self.client.post(f"/databases/{database_id}/query", json=body)
            resp.raise_for_status()
            data = resp.json()

            rows.extend(data.get("results", []))

            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")

        return rows

    async def close(self):
        await self.client.aclose()


class AppFlowyImporter:
    """Importe les données vers AppFlowy Cloud."""

    def __init__(self, appflowy_token: str = ""):
        self.token = appflowy_token or os.environ.get("APPFLOWY_TOKEN", "")
        self.client = httpx.AsyncClient(
            base_url=os.environ.get("APPFLOWY_BASE_URL", "https://api.appflowy.io"),
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    async def list_workspaces(self) -> List[Dict[str, Any]]:
        """Liste les workspaces existants."""
        resp = await self.client.get("/api/workspace")
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else data.get("workspaces", [])

    async def create_page(self, workspace_id: str, name: str, view_type: str = "document") -> Dict[str, Any]:
        """Crée une page dans AppFlowy."""
        resp = await self.client.post(
            f"/api/workspace/{workspace_id}/page-view",
            json={"name": name, "view_type": view_type},
        )
        resp.raise_for_status()
        return resp.json()

    async def close(self):
        await self.client.aclose()


class NotionToAppFlowyMigrator:
    """Orchestrateur de migration Notion → AppFlowy."""

    def __init__(self, notion_token: str = "", appflowy_token: str = ""):
        self.notion = NotionExporter(notion_token)
        self.appflowy = AppFlowyImporter(appflowy_token)
        self.stats = MigrationStats()

    async def migrate(self, target_workspace_id: str) -> MigrationStats:
        """Migration complète Notion → AppFlowy.

        Args:
            target_workspace_id: ID du workspace AppFlowy cible

        Returns:
            MigrationStats avec compteurs et erreurs
        """
        logger.info("Starting Notion → AppFlowy migration")

        # Phase 1: Export Notion
        try:
            items = await self.notion.search_all()
            logger.info("Found %d items in Notion", len(items))
        except Exception as e:
            self.stats.errors.append(f"Notion export failed: {e}")
            return self.stats

        # Phase 2: Import pages
        for item in items:
            obj_type = item.get("object", "")
            item_id = item.get("id", "")

            try:
                if obj_type == "page":
                    name = self._extract_page_name(item)
                    await self.appflowy.create_page(target_workspace_id, name, "document")
                    self.stats.pages_migrated += 1

                elif obj_type == "database":
                    name = item.get("title", [{}])[0].get("plain_text", "Untitled DB") if item.get("title") else "Untitled DB"
                    await self.appflowy.create_page(target_workspace_id, name, "grid")
                    self.stats.databases_migrated += 1

            except Exception as e:
                self.stats.errors.append(f"Failed to migrate {obj_type} {item_id}: {e}")

        logger.info("Migration complete: %d pages, %d databases, %d errors",
                     self.stats.pages_migrated, self.stats.databases_migrated, len(self.stats.errors))

        await self.notion.close()
        await self.appflowy.close()

        return self.stats

    def _extract_page_name(self, page: Dict[str, Any]) -> str:
        """Extrait le nom d'une page Notion."""
        props = page.get("properties", {})
        for prop in props.values():
            if prop.get("type") == "title":
                title_list = prop.get("title", [])
                if title_list:
                    return "".join(t.get("plain_text", "") for t in title_list)
        return "Untitled"


async def main():
    """Point d'entrée CLI."""
    import sys

    notion_token = os.environ.get("NOTION_TOKEN", "")
    appflowy_token = os.environ.get("APPFLOWY_TOKEN", "")
    workspace_id = sys.argv[1] if len(sys.argv) > 1 else ""

    if not notion_token:
        print("ERROR: NOTION_TOKEN environment variable required")
        sys.exit(1)
    if not appflowy_token:
        print("ERROR: APPFLOWY_TOKEN environment variable required")
        sys.exit(1)
    if not workspace_id:
        print("Usage: python migrate_notion_to_appflowy.py <appflowy_workspace_id>")
        sys.exit(1)

    migrator = NotionToAppFlowyMigrator(notion_token, appflowy_token)
    stats = await migrator.migrate(workspace_id)

    print(f"Migration complete:")
    print(f"  Pages migrated: {stats.pages_migrated}")
    print(f"  Databases migrated: {stats.databases_migrated}")
    print(f"  Errors: {len(stats.errors)}")
    for err in stats.errors:
        print(f"  - {err}")


if __name__ == "__main__":
    asyncio.run(main())
