from pydantic import BaseModel

class QuestionRequest(BaseModel):
    query: str

class QAResponse(BaseModel):
    query: str
    answer: str

class UploadResponse(BaseModel):
    filename: str
    message: str
    total_chunks: int