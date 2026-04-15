import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.scan import ScanStatus
from app.schemas.finding import FindingOut
from app.schemas.module_run import ModuleRunOut


class ScanCreate(BaseModel):
    domain: str = Field(..., min_length=1, max_length=253)


class ScanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    domain: str
    status: ScanStatus
    created_at: datetime
    finished_at: datetime | None


class ScanDetail(ScanOut):
    findings: list[FindingOut] = []
    module_runs: list[ModuleRunOut] = []
