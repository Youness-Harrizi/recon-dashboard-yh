"""Per-(domain, module) result cache.

Different modules go stale at very different rates — DNS changes weekly, WHOIS
monthly, CT logs are append-only. The worker checks the cache before running a
module; on a hit it replays the cached findings through the normal emit path so
the UI still gets streamed events and the scan still accumulates Finding rows.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.dialects.postgresql import insert

from app.db import SyncSessionLocal
from app.models.cache import DomainCache

# How long a module's result stays valid. Tuned to the rate the underlying
# source actually changes — fast for HTTP/TLS (they can break daily), slow for
# RDAP (registrations change monthly at best).
MODULE_TTL: dict[str, timedelta] = {
    "dns": timedelta(hours=1),
    "whois": timedelta(days=1),
    "crtsh": timedelta(hours=6),
    "tls": timedelta(hours=6),
    "http": timedelta(hours=1),
    "wayback": timedelta(hours=12),
    "github": timedelta(hours=6),
    "shodan": timedelta(hours=6),
}

DEFAULT_TTL = timedelta(hours=1)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def load(domain: str, module: str) -> list[dict[str, Any]] | None:
    """Return cached findings list for (domain, module) or None if miss/expired."""
    with SyncSessionLocal() as session:
        row = session.get(DomainCache, (domain, module))
        if row is None:
            return None
        if row.expires_at <= _now():
            return None
        payload = row.payload or {}
        findings = payload.get("findings")
        if not isinstance(findings, list):
            return None
        return findings


def store(domain: str, module: str, findings: list[dict[str, Any]]) -> None:
    """Upsert a fresh cache entry. TTL picked per-module."""
    ttl = MODULE_TTL.get(module, DEFAULT_TTL)
    expires = _now() + ttl
    with SyncSessionLocal() as session:
        stmt = (
            insert(DomainCache)
            .values(
                domain=domain,
                module=module,
                payload={"findings": findings},
                expires_at=expires,
            )
            .on_conflict_do_update(
                index_elements=[DomainCache.domain, DomainCache.module],
                set_={"payload": {"findings": findings}, "expires_at": expires},
            )
        )
        session.execute(stmt)
        session.commit()
