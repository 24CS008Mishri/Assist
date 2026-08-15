import os
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_mongodb import MongoDBAtlasVectorSearch
from langchain_groq import ChatGroq

from backend.data.database import get_collection

load_dotenv()

def get_llm() -> ChatGroq:
    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key:
        raise RuntimeError("GROQ_API_KEY must be set in .env")

    return ChatGroq(
        groq_api_key=groq_key,
        model_name="llama-3.1-8b-instant"
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


def process_and_store_pdf(text: str) -> int:
    """Chunks the text and stores vectors in MongoDB Atlas."""
    document = Document(page_content=text)
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
    chunks = text_splitter.split_documents([document])

    vectorstore = get_vectorstore()
    vectorstore.add_documents(chunks)
    return len(chunks)


def answer_question(query: str) -> str:
    """Retrieves relevant contexts and generates an answer using Groq LLaMA 3.1."""
    vectorstore = get_vectorstore()
    retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
    docs = retriever.invoke(query)

    if not docs:
        return "I could not find relevant information in the indexed documents."

    context = "\n\n".join(doc.page_content for doc in docs if getattr(doc, "page_content", ""))
    prompt = (
        "You are a helpful assistant. Answer the user's question using the provided context.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {query}\n\n"
        "Answer:"
    )

    response = get_llm().invoke(prompt)
    return getattr(response, "content", str(response))


