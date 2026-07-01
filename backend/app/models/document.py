from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class DocumentBase(BaseModel):
    filename: str
    owner_email: str


class DocumentInDB(DocumentBase):
    id: Optional[str] = None
    num_chunks: int = 0
    file_size_bytes: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = "indexed"  # indexed | processing | failed


class DocumentPublic(BaseModel):
    id: str
    filename: str
    num_chunks: int
    file_size_bytes: int
    created_at: datetime
    status: str


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=3, description="Minimum 3 characters")
    document_ids: Optional[List[str]] = None  # Filter to specific docs, or None = all


class QueryLog(BaseModel):
    user_email: str
    query: str
    answer: str
    sources: List[str] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    latency_ms: Optional[float] = None
