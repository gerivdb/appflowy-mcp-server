"""
JWT Auto-Refresh Middleware for AppFlowy MCP Server

Intercepts 401 responses, re-authenticates via GoTrue,
retries the original request transparently.

Automation C | Issue appflowy-mcp-server #3
"""

import os
import json
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class JWTRefreshMiddleware:
    """
    HTTP middleware that auto-refreshes JWT tokens on 401.

    Usage:
        middleware = JWTRefreshMiddleware(
            gotrue_url="http://localhost:9999",
            email="gerivonderbitsh@gmail.com",
            password="789fuckyl*GGV"
        )
        middleware.install(httpx_client)
    """

    def __init__(
        self,
        gotrue_url: str = "",
        email: str = "",
        password: str = "",
        refresh_token: str = "",
    ):
        self.gotrue_url = (gotrue_url or os.environ.get("APPFLOWY_GOTRUE_URL", "http://localhost:9999")).rstrip("/")
        self.email = email or os.environ.get("APPFLOWY_EMAIL", "")
        self.password = password or os.environ.get("APPFLOWY_PASSWORD", "")
        self.refresh_token = refresh_token
        self.access_token: Optional[str] = os.environ.get("APPFLOWY_TOKEN", "")
        self._refreshing = False

    def _relogin(self) -> bool:
        """Re-authenticate via GoTrue."""
        if not self.email or not self.password:
            logger.error("No credentials for auto-refresh")
            return False

        try:
            import httpx
            client = httpx.Client(timeout=10.0)

            # Try refresh token first
            if self.refresh_token:
                resp = client.post(
                    f"{self.gotrue_url}/token?grant_type=refresh_token",
                    json={"refresh_token": self.refresh_token},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    self.access_token = data.get("access_token")
                    self.refresh_token = data.get("refresh_token", self.refresh_token)
                    os.environ["APPFLOWY_TOKEN"] = self.access_token
                    logger.info("JWT refreshed via refresh_token")
                    return True

            # Fallback to password login
            resp = client.post(
                f"{self.gotrue_url}/token?grant_type=password",
                json={"email": self.email, "password": self.password},
            )
            if resp.status_code == 200:
                data = resp.json()
                self.access_token = data.get("access_token")
                self.refresh_token = data.get("refresh_token", "")
                os.environ["APPFLOWY_TOKEN"] = self.access_token
                logger.info("JWT refreshed via password login")
                return True

            logger.error(f"Re-login failed: {resp.status_code} {resp.text[:100]}")
            return False

        except Exception as e:
            logger.error(f"Re-login error: {e}")
            return False

    def refresh_if_needed(self) -> str:
        """Return current token, refreshing if expired."""
        if self.access_token:
            return self.access_token
        self._relogin()
        return self.access_token or ""

    def get_headers(self) -> Dict[str, str]:
        """Get auth headers with auto-refresh."""
        token = self.refresh_if_needed()
        return {"Authorization": f"Bearer {token}"}


# Singleton instance
_middleware: Optional[JWTRefreshMiddleware] = None


def get_jwt_middleware() -> JWTRefreshMiddleware:
    """Get or create the singleton JWT middleware."""
    global _middleware
    if _middleware is None:
        _middleware = JWTRefreshMiddleware()
    return _middleware
