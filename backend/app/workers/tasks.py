"""Celery tasks that execute recon modules.

One task per (scan, module). The orchestrator enqueues a group of these plus a
finalize callback; each task updates its ModuleRun row and persists findings
as the module emits them. The finalize task flips the Scan row to `done`.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from celery import chord, group
from sqlalchemy import select

from app.db import SyncSessionLocal
from app.models.finding import Finding
from app.models.module_run import ModuleRun, ModuleStatus
from app.models.scan import Scan, ScanStatus
from app.recon.base import Context, FindingDraft
from app.recon.registry import MODULES, get_module
from app.workers.celery_app import celery_app

log = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


@celery_app.task(name="recon.run_module")
def run_module(scan_id: str, module_name: str) -> dict:
    """Execute a single recon module for a scan."""
    scan_uuid = uuid.UUID(scan_id)

    with SyncSessionLocal() as session:
        run = session.execute(
            select(ModuleRun).where(
                ModuleRun.scan_id == scan_uuid, ModuleRun.module == module_name
            )
        ).scalar_one()

        # Also flip the parent scan to running on the first module start.
        scan = session.get(Scan, scan_uuid)
        if scan and scan.status == ScanStatus.pending:
            scan.status = ScanStatus.running

        run.status = ModuleStatus.running
        run.started_at = _now()
        session.commit()

    try:
        module = get_module(module_name)
    except KeyError as e:
        with SyncSessionLocal() as session:
            run = session.execute(
                select(ModuleRun).where(
                    ModuleRun.scan_id == scan_uuid, ModuleRun.module == module_name
                )
            ).scalar_one()
            run.status = ModuleStatus.failed
            run.error = str(e)
            run.finished_at = _now()
            session.commit()
        return {"module": module_name, "status": "failed", "error": str(e)}

    # Need the domain — re-read from the scan row.
    with SyncSessionLocal() as session:
        scan = session.get(Scan, scan_uuid)
        if scan is None:
            raise RuntimeError(f"scan {scan_id} disappeared")
        domain = scan.domain

    def emit(draft: FindingDraft) -> None:
        """Persist one finding immediately so the UI can see it right away."""
        with SyncSessionLocal() as session:
            finding = Finding(
                scan_id=scan_uuid,
                module=draft.module,
                severity=draft.severity,
                title=draft.title,
                data=draft.data,
            )
            session.add(finding)
            session.commit()

    ctx = Context(domain=domain, scan_id=scan_uuid, emit=emit)

    try:
        module.run(ctx)
        status = ModuleStatus.done
        error = None
    except Exception as exc:  # noqa: BLE001 — we want to record any failure
        log.exception("module %s failed for scan %s", module_name, scan_id)
        status = ModuleStatus.failed
        error = f"{type(exc).__name__}: {exc}"

    with SyncSessionLocal() as session:
        run = session.execute(
            select(ModuleRun).where(
                ModuleRun.scan_id == scan_uuid, ModuleRun.module == module_name
            )
        ).scalar_one()
        run.status = status
        run.error = error
        run.finished_at = _now()
        session.commit()

    return {"module": module_name, "status": status.value}


@celery_app.task(name="recon.finalize_scan")
def finalize_scan(results: list[dict], scan_id: str) -> dict:
    """Called once all module tasks in the chord have completed."""
    scan_uuid = uuid.UUID(scan_id)

    any_failed = any(r.get("status") == "failed" for r in results)

    with SyncSessionLocal() as session:
        scan = session.get(Scan, scan_uuid)
        if scan is None:
            return {"scan_id": scan_id, "status": "missing"}
        scan.status = ScanStatus.failed if any_failed else ScanStatus.done
        scan.finished_at = _now()
        session.commit()

    return {"scan_id": scan_id, "status": scan.status.value}


def dispatch_scan(scan_id: uuid.UUID) -> None:
    """Dispatch a chord of per-module tasks. ModuleRun rows must exist already."""
    header = group(run_module.s(str(scan_id), m.name) for m in MODULES)
    callback = finalize_scan.s(str(scan_id))
    chord(header)(callback)
