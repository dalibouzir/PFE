from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.schemas.base import ORMModel


class UploadedFileRead(ORMModel):
    id: UUID
    cooperative_id: UUID
    entity_type: str
    entity_id: UUID
    filename: str
    mime_type: str
    size_bytes: int
    storage_path: str
    file_url: str
    uploaded_at: datetime
    created_at: datetime
    updated_at: datetime
