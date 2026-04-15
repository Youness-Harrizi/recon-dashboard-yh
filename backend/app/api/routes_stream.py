"""Server-Sent Events endpoint for live scan updates.

The client opens an EventSource to `/api/v1/scans/{id}/stream`. We:
  1. Fetch the current scan snapshot (so the UI has a base state immediately).
  2. Subscribe to the per-scan Redis pub/sub channel.
  3. Forward each published event as an SSE message.
  4. Close the stream when the `end` event arrives (or the client disconnects).

Workers publish events in app.workers.tasks via app.services.events.publish_event.
"""

from __future__ import annotations

import asyncio
import json
import uuid

import redis.asyncio as redis
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_session
from app.models.scan import Scan
from app.schemas.scan import ScanDetail
from app.services.events import channel_for

router = APIRouter(prefix="/api/v1/scans", tags=["scans"])

# Heartbeat every N seconds keeps proxies from timing out idle connections.
HEARTBEAT_SECONDS = 15


def _sse(event: str, data: str) -> bytes:
    """Format one SSE frame. `data` must already be JSON-encoded."""
    return f"event: {event}\ndata: {data}\n\n".encode()


@router.get("/{scan_id}/stream")
async def stream_scan(
    scan_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    # Validate the scan exists before opening the stream.
    result = await session.execute(
        select(Scan)
        .where(Scan.id == scan_id)
        .options(
            selectinload(Scan.findings),
            selectinload(Scan.module_runs),
        )
    )
    scan = result.scalar_one_or_none()
    if not scan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="scan not found"
        )

    snapshot = ScanDetail.model_validate(scan).model_dump(mode="json")
    # Reuse the app-wide Redis connection pool but create a fresh pubsub so
    # subscription state is isolated per request.
    pubsub_client: redis.Redis = redis.Redis(
        connection_pool=request.app.state.redis.connection_pool
    )
    pubsub = pubsub_client.pubsub()
    await pubsub.subscribe(channel_for(scan_id))

    async def event_stream():
        try:
            # 1. Send the current state so the UI is up-to-date immediately,
            # even if it connects after the scan finished.
            yield _sse("snapshot", json.dumps(snapshot, default=str))

            # If the scan is already terminal, close right away.
            if snapshot["status"] in ("done", "failed"):
                yield _sse("end", "{}")
                return

            # 2. Forward pub/sub messages + heartbeats until end / disconnect.
            while True:
                if await request.is_disconnected():
                    return

                msg = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=HEARTBEAT_SECONDS
                )
                if msg is None:
                    # Idle — send a comment line as a keep-alive.
                    yield b": ping\n\n"
                    continue

                raw = msg.get("data")
                if not isinstance(raw, str):
                    continue
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                event_name = parsed.get("event", "message")
                data = json.dumps(parsed.get("data", {}), default=str)
                yield _sse(event_name, data)
                if event_name == "end":
                    return
        except asyncio.CancelledError:
            raise
        finally:
            try:
                await pubsub.unsubscribe(channel_for(scan_id))
                await pubsub.close()
            except Exception:
                pass

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # disable nginx buffering if fronted
        },
    )
