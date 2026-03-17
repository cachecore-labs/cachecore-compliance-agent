"""Agent C configuration — JWT generation, gateway URL, model settings."""

from __future__ import annotations

import os
import time

import jwt as pyjwt  # PyJWT

# ── Gateway ───────────────────────────────────────────────────────────────
CACHECORE_GATEWAY_URL: str = os.environ.get(
    "CACHECORE_GATEWAY_URL", "http://localhost:8080"
)

# ── Auth ──────────────────────────────────────────────────────────────────
JWT_SECRET: str = os.environ.get(
    "CACHECORE_JWT_SECRET", "dev-secret-change-me-32bytes-ok!"
)
TENANT_ID: str = os.environ.get("CACHECORE_TENANT_ID", "agent_c_demo")

# ── Model ─────────────────────────────────────────────────────────────────
MODEL: str = os.environ.get("CACHECORE_MODEL", "gpt-4o-mini")

# ── Timing ────────────────────────────────────────────────────────────────
SEED_DELAY_MS: int = 200  # ms to wait after seeding before concurrent phase


def generate_tenant_jwt(
    tenant_id: str = TENANT_ID,
    roles: list[str] | None = None,
    scope: str = "contracts:read",
    ttl_seconds: int = 7200,
) -> str:
    """Generate an HS256 JWT matching the CacheCore gateway's auth config."""
    if roles is None:
        roles = ["compliance_analyst"]
    return pyjwt.encode(
        {
            "tenant_id": tenant_id,
            "roles": roles,
            "scope": scope,
            "exp": int(time.time()) + ttl_seconds,
        },
        JWT_SECRET,
        algorithm="HS256",
    )
