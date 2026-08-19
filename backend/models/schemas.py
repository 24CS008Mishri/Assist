from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class QuestionRequest(BaseModel):
    query: str = Field(..., min_length=1)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=4000)


class AssistantRequest(BaseModel):
    question: str = Field(..., min_length=1)
    history: List[ChatMessage] = Field(default_factory=list, max_length=12)


class Source(BaseModel):
    title: str
    section: str = "Retrieved excerpt"
    type: str = "Indexed PDF"
    detail: str
    score: Optional[float] = None


class QAResponse(BaseModel):
    query: str
    answer: str
    sources: List[Source] = Field(default_factory=list)


class AssistantResponse(BaseModel):
    question: str
    answer: str
    sources: List[Source] = Field(default_factory=list)


class UploadResponse(BaseModel):
    filename: str
    message: str
    total_chunks: int
    already_indexed: bool = False


class DocumentRecord(BaseModel):
    filename: str
    total_chunks: int
    uploaded_at: Optional[datetime] = None
    status: str = "Active"


class LoginRequest(BaseModel):
    email: str
    password: str
