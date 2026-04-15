"""Scan orchestration: turn a persisted Scan into per-module work items."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.module_run import ModuleRun, ModuleStatus
from app.recon.registry import MODULES
from app.workers.tasks import dispatch_scan


async def start_scan(session: AsyncSession, scan_id: uuid.UUID) -> None:
    """Create a ModuleRun row per enabled module and enqueue the work."""
    for m in MODULES:
        session.add(
            ModuleRun(
                scan_id=scan_id,
                module=m.name,
                status=ModuleStatus.pending,
            )
        )
    await session.commit()

    # Celery's apply_async is a sync Redis write; fast enough to call inline.
    dispatch_scan(scan_id)
