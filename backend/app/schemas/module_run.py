import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.module_run import ModuleStatus


class ModuleRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    module: str
    status: ModuleStatus
    error: str | None
    started_at: datetime | None
    finished_at: datetime | None
