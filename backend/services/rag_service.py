import os
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_mongodb import MongoDBAtlasVectorSearch
from langchain_groq import ChatGroq

from backend.data.database import get_collection
from backend.services.document_service import is_document_indexed, register_document


load_dotenv()

def get_llm() -> ChatGroq:
    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key:
        raise RuntimeError("GROQ_API_KEY must be set in .env")

    return ChatGroq(
        groq_api_key=groq_key,
        model_name="llama-3.1-8b-instant",
        temperature=0.2
    )


def get_embeddings() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )


def get_vectorstore() -> MongoDBAtlasVectorSearch:
    return MongoDBAtlasVectorSearch(
        collection=get_collection(),
        embedding=get_embeddings(),
        index_name="vector_index"
    )


def process_and_store_pdf(text: str, filename: str) -> int:
    # 1. Deduplication check via document_service
    existing_chunks = is_document_indexed(filename)
    if existing_chunks is not None:
        return existing_chunks
    
    """Chunks the text and stores vectors in MongoDB Atlas."""

    document = Document(page_content=text, metadata={"source": filename})

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
    chunks = text_splitter.split_documents([document])

    vectorstore = get_vectorstore()
    vectorstore.add_documents(chunks)
    register_document(filename, len(chunks))
    return len(chunks)


def answer_question(query: str) -> str:
    """Retrieves relevant contexts and generates an answer using Groq LLaMA 3.1."""
    vectorstore = get_vectorstore()
    retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
    docs = retriever.invoke(query)

    if not docs:
        return "I could not find relevant information in the indexed documents."

    # Format context blocks with source document names
    context_blocks = []
    for doc in docs:
        source_name = doc.metadata.get("source", "Unknown Document")
        content = getattr(doc, "page_content", "").strip()
        if content:
            context_blocks.append(f"[Source: {source_name}]\n{content}")

    formatted_context = "\n\n---\n\n".join(context_blocks)

    prompt = (
        "You are a helpful assistant. Answer the user's question using the provided context.\n\n"
        f"Context:\n{formatted_context}\n\n"
        f"Question: {query}\n\n"
        "Answer:"
    )

    response = get_llm().invoke(prompt)
    return getattr(response, "content", str(response))


