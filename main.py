from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.routers import rag

app = FastAPI(
    title="RAG Backend API",
    description="FastAPI Backend powered by MongoDB Atlas Vector Search and Groq LLaMA 3.1",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5500", "http://localhost:5500"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Routers
app.include_router(rag.router)

@app.get("/")
def read_root():
    return {"message": "RAG Backend is running running smoothly!"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8001, reload=True)