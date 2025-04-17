from pydantic import BaseModel
from typing import List, Optional
from pydantic import BaseModel, Field
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

class ChatRequest(BaseModel):
    question: str
    use_graph: bool = False
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0) # Add temp with validation
    max_tokens: Optional[int] = Field(None, gt=0) # Add max_tokens with validation
    # Add other parameters like top_p, system_prompt if needed

class ChatResponse(BaseModel):
    answer: str
    sources: List[str] = []