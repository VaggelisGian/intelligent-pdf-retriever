from pydantic import BaseModel
from typing import List, Optional

class Document(BaseModel):
    id: str
    title: str
    content: str
    metadata: Optional[dict] = None

class QueryRequest(BaseModel):
    query: str
    top_k: Optional[int] = 5

class QueryResponse(BaseModel):
    results: List[Document]

class UploadResponse(BaseModel):
    message: str
    document_id: str

class ErrorResponse(BaseModel):
    error: str
    details: Optional[str] = None