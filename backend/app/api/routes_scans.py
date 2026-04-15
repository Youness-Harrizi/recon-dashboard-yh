import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_session
from app.models.scan import Scan
from app.ratelimit import limiter
from app.schemas.scan import ScanCreate, ScanDetail, ScanOut
from app.services.domain_validator import InvalidDomainError, normalize_domain
from app.services.orchestrator import start_scan

router = APIRouter(prefix="/api/v1/scans", tags=["scans"])


@router.post("", response_model=ScanOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def create_scan(
    request: Request,
    payload: ScanCreate,
    session: AsyncSession = Depends(get_session),
) -> Scan:
    try:
        domain = normalize_domain(payload.domain)
    except InvalidDomainError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e

    scan = Scan(domain=domain)
    session.add(scan)
    await session.commit()
    await session.refresh(scan)

    await start_scan(session, scan.id)
    return scan


@router.get("/{scan_id}", response_model=ScanDetail)
async def get_scan(
    scan_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> Scan:
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="scan not found")
    return scan


@router.get("", response_model=list[ScanOut])
async def list_scans(
    limit: int = 20, session: AsyncSession = Depends(get_session)
) -> list[Scan]:
    limit = max(1, min(limit, 100))
    result = await session.execute(
        select(Scan).order_by(Scan.created_at.desc()).limit(limit)
    )
    return list(result.scalars().all())


@router.get("/{scan_id}/export.json")
async def export_scan(
    scan_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> JSONResponse:
    """Full scan + findings + module runs as a download."""
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="scan not found")

    body = ScanDetail.model_validate(scan).model_dump(mode="json")
    filename = f"recon-{scan.domain}-{scan.id}.json"
    return JSONResponse(
        content=body,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
