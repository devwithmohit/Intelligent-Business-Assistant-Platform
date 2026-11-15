from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class DocumentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class DocumentRead(BaseModel):
    id: int
    user_id: int
    title: str
    filename: Optional[str] = None
    content_type: Optional[str] = None
    file_size: Optional[int] = None
    chunk_count: int = 0
    doc_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class KnowledgeQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    top_k: int = Field(default=5, ge=1, le=50)
    document_id: Optional[int] = None


class KnowledgeQueryResult(BaseModel):
    id: Optional[str] = None
    content: str
    score: float
    document_id: Optional[int] = None
    title: str
    chunk_index: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)
