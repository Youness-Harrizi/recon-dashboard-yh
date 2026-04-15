import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_session
from app.models.scan import Scan
from app.schemas.scan import ScanCreate, ScanDetail, ScanOut
from app.services.domain_validator import InvalidDomainError, normalize_domain

router = APIRouter(prefix="/api/v1/scans", tags=["scans"])


@router.post("", response_model=ScanOut, status_code=status.HTTP_201_CREATED)
async def create_scan(
    payload: ScanCreate, session: AsyncSession = Depends(get_session)
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
    # NOTE: orchestrator wiring comes in step 3; for now scans stay 'pending'.
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
