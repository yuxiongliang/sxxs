from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    original_name: str
    mime_type: str
    size: int
    extension: str
    category: str
    storage: str
    url: str
    uploader: str
    source_module: str
    checksum: str
    created_at: datetime


class AttachmentStats(BaseModel):
    total: int
    images: int
    videos: int
    documents: int
    others: int
    totalSize: int
