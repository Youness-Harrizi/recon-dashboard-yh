import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_session
from app.models.scan import Scan
from app.ratelimit import limiter
from app.schemas.scan import ScanCreate, ScanDetail, ScanOut
from app.services import exporters
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


async def _load_scan_dict(scan_id: uuid.UUID, session: AsyncSession) -> tuple[Scan, dict]:
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
    return scan, ScanDetail.model_validate(scan).model_dump(mode="json")


def _attach(scan: Scan, ext: str) -> dict[str, str]:
    filename = f"recon-{scan.domain}-{scan.id}.{ext}"
    return {"Content-Disposition": f'attachment; filename="{filename}"'}


@router.get("/{scan_id}/export.json")
async def export_scan_json(
    scan_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> JSONResponse:
    scan, body = await _load_scan_dict(scan_id, session)
    return JSONResponse(content=body, headers=_attach(scan, "json"))


@router.get("/{scan_id}/export.csv")
async def export_scan_csv(
    scan_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> Response:
    scan, body = await _load_scan_dict(scan_id, session)
    return Response(
        content=exporters.to_csv(body),
        media_type="text/csv; charset=utf-8",
        headers=_attach(scan, "csv"),
    )


@router.get("/{scan_id}/export.xlsx")
async def export_scan_xlsx(
    scan_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> Response:
    scan, body = await _load_scan_dict(scan_id, session)
    return Response(
        content=exporters.to_xlsx(body),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=_attach(scan, "xlsx"),
    )


@router.get("/{scan_id}/export.md")
async def export_scan_markdown(
    scan_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> Response:
    scan, body = await _load_scan_dict(scan_id, session)
    return Response(
        content=exporters.to_markdown(body),
        media_type="text/markdown; charset=utf-8",
        headers=_attach(scan, "md"),
    )


@router.get("/{scan_id}/export.html", response_class=Response)
async def export_scan_html(
    scan_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    download: bool = False,
) -> Response:
    """HTML report. Opens inline by default; ?download=1 forces a save dialog."""
    scan, body = await _load_scan_dict(scan_id, session)
    headers = _attach(scan, "html") if download else {}
    return Response(
        content=exporters.to_html(body),
        media_type="text/html; charset=utf-8",
        headers=headers,
    )
