"""Redis pub/sub helpers for streaming scan events to the UI.

Workers (sync) call `publish_event` after persisting a change. The SSE endpoint
(async) subscribes to the per-scan channel and forwards events to the browser.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import redis as sync_redis

from app.config import settings

# One shared sync client for workers. Redis-py clients are thread-safe and
# connection-pooled, so a module-level instance is fine.
_sync_client: sync_redis.Redis | None = None


def _client() -> sync_redis.Redis:
    global _sync_client
    if _sync_client is None:
        _sync_client = sync_redis.Redis.from_url(
            settings.redis_url, decode_responses=True
        )
    return _sync_client


def channel_for(scan_id: uuid.UUID | str) -> str:
    return f"scan:{scan_id}"


def publish_event(scan_id: uuid.UUID | str, event: str, payload: dict[str, Any]) -> None:
    """Publish one event on the scan's channel. Best-effort — never raises."""
    try:
        msg = json.dumps({"event": event, "data": payload}, default=str)
        _client().publish(channel_for(scan_id), msg)
    except Exception:
        # Streaming is a convenience; polling fallback / GET endpoint still works.
        pass
