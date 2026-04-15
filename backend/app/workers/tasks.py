"""Celery tasks that execute recon modules.

One task per (scan, module). The orchestrator enqueues a group of these plus a
finalize callback; each task updates its ModuleRun row and persists findings
as the module emits them. The finalize task flips the Scan row to `done`.

Every state change also publishes an event on the scan's Redis pub/sub channel
so the SSE endpoint can forward it to connected browsers in real time.
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
from app.models.finding import Severity
from app.recon.base import Context, FindingDraft
from app.recon.registry import MODULES, get_module
from app.services import cache
from app.services.events import publish_event
from app.workers.celery_app import celery_app

log = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _module_run_payload(run: ModuleRun) -> dict:
    return {
        "id": str(run.id),
        "module": run.module,
        "status": run.status.value,
        "error": run.error,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
    }


def _finding_payload(f: Finding) -> dict:
    return {
        "id": str(f.id),
        "scan_id": str(f.scan_id),
        "module": f.module,
        "severity": f.severity.value,
        "title": f.title,
        "data": f.data,
        "created_at": f.created_at.isoformat() if f.created_at else None,
    }


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
        scan_flipped = False
        if scan and scan.status == ScanStatus.pending:
            scan.status = ScanStatus.running
            scan_flipped = True

        run.status = ModuleStatus.running
        run.started_at = _now()
        session.commit()
        session.refresh(run)
        run_payload = _module_run_payload(run)

    publish_event(scan_uuid, "module_run", run_payload)
    if scan_flipped:
        publish_event(scan_uuid, "scan", {"status": ScanStatus.running.value})

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
            session.refresh(run)
            publish_event(scan_uuid, "module_run", _module_run_payload(run))
        return {"module": module_name, "status": "failed", "error": str(e)}

    # Need the domain — re-read from the scan row.
    with SyncSessionLocal() as session:
        scan = session.get(Scan, scan_uuid)
        if scan is None:
            raise RuntimeError(f"scan {scan_id} disappeared")
        domain = scan.domain

    # Collected raw drafts so we can populate the cache after a clean run.
    emitted: list[dict] = []

    def emit(draft: FindingDraft) -> None:
        """Persist one finding immediately so the UI can see it right away."""
        emitted.append(
            {
                "module": draft.module,
                "title": draft.title,
                "severity": draft.severity.value,
                "data": draft.data,
            }
        )
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
            session.refresh(finding)
            publish_event(scan_uuid, "finding", _finding_payload(finding))

    ctx = Context(domain=domain, scan_id=scan_uuid, emit=emit)

    # Cache read-through: replay stored findings instead of re-running the module.
    cached = cache.load(domain, module_name)
    if cached is not None:
        log.info("cache hit for %s/%s (%d findings)", domain, module_name, len(cached))
        for item in cached:
            try:
                severity = Severity(item.get("severity", "info"))
            except ValueError:
                severity = Severity.info
            emit(
                FindingDraft(
                    module=item.get("module", module_name),
                    title=item.get("title", ""),
                    severity=severity,
                    data=item.get("data") or {},
                )
            )
        status = ModuleStatus.done
        error = None
    else:
        try:
            module.run(ctx)
            status = ModuleStatus.done
            error = None
            # Only cache successful runs. Don't cache the cached-replay path —
            # that row is already fresh in the DB.
            if emitted:
                try:
                    cache.store(domain, module_name, emitted)
                except Exception:
                    log.exception("cache store failed for %s/%s", domain, module_name)
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
        session.refresh(run)
        publish_event(scan_uuid, "module_run", _module_run_payload(run))

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
        final_status = scan.status.value
        finished_at = scan.finished_at.isoformat() if scan.finished_at else None

    publish_event(
        scan_uuid,
        "scan",
        {"status": final_status, "finished_at": finished_at},
    )
    # Sentinel so the SSE endpoint knows it can close the stream.
    publish_event(scan_uuid, "end", {})

    return {"scan_id": scan_id, "status": final_status}


def dispatch_scan(scan_id: uuid.UUID) -> None:
    """Dispatch a chord of per-module tasks. ModuleRun rows must exist already."""
    header = group(run_module.s(str(scan_id), m.name) for m in MODULES)
    callback = finalize_scan.s(str(scan_id))
    chord(header)(callback)
