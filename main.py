from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.core.config import get_settings
from backend.routers import analyzer, demo, rag


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="FastAPI backend powered by MongoDB Atlas Vector Search, Hugging Face embeddings, and Groq.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(rag.router)
app.include_router(demo.router)
app.include_router(analyzer.router)

@app.get("/")
def read_root():
    return {"message": "RAG Backend is running smoothly"}

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8002, reload=True)
