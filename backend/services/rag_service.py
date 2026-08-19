from functools import lru_cache
from typing import List, Optional, Tuple

from langchain_core.documents import Document
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_mongodb import MongoDBAtlasVectorSearch
from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.core.config import get_settings
from backend.data.database import get_aicte_collection, get_designer_collection
from backend.models.schemas import Source
from backend.services.document_service import (
    generate_document_id,
    is_document_indexed,
    register_document,
)
from backend.services.pdf_service import PdfPage


@lru_cache(maxsize=1)
def get_embeddings() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(model_name=get_settings().embedding_model)


@lru_cache(maxsize=1)
def get_llm() -> ChatGroq:
    settings = get_settings()
    if not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY must be set before asking the assistant")

    return ChatGroq(
        groq_api_key=settings.groq_api_key,
        model_name=settings.groq_model,
        temperature=0.1,
    )


def get_text_splitter() -> RecursiveCharacterTextSplitter:
    settings = get_settings()
    return RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )


def _make_vectorstore(
    collection,
    index_name: str,
) -> MongoDBAtlasVectorSearch:
    return MongoDBAtlasVectorSearch(
        collection=collection,
        embedding=get_embeddings(),
        index_name=index_name,
        text_key="text",
        embedding_key="embedding",
    )


def get_aicte_vectorstore() -> MongoDBAtlasVectorSearch:
    settings = get_settings()
    return _make_vectorstore(
        get_aicte_collection(), settings.aicte_mongodb_vector_index
    )


def get_designer_vectorstore() -> MongoDBAtlasVectorSearch:
    settings = get_settings()
    return _make_vectorstore(
        get_designer_collection(), settings.curriculum_mongodb_vector_index
    )


def get_vectorstore(source_type: str = "aicte_reference") -> MongoDBAtlasVectorSearch:
    if source_type == "aicte_reference":
        return get_aicte_vectorstore()
    if source_type == "submitted_curriculum":
        return get_designer_vectorstore()
    raise ValueError(f"Unsupported source_type: {source_type}")


def process_and_store_pdf(
    text: str,
    filename: str,
    *,
    pages: Optional[List[PdfPage]] = None,
    document_id: Optional[str] = None,
    source_type: str = "aicte_reference",
    programme: str = "B.Tech",
    branch: str = "CSE",
    curriculum_id: Optional[str] = None,
    year: Optional[int] = None,
    version: Optional[str] = None,
    owner_id: Optional[str] = None,
) -> Tuple[int, bool]:
    if source_type == "submitted_curriculum" and not owner_id:
        raise ValueError("Authenticated owner_id is required for submitted curricula")
    existing_chunks = is_document_indexed(
        filename,
        source_type=source_type,
        owner_id=owner_id,
    )
    if existing_chunks is not None:
        return existing_chunks, True

    resolved_document_id = document_id or generate_document_id(text.encode("utf-8"))
    base_metadata = {
        "source": filename,
        "document_id": resolved_document_id,
        "source_type": source_type,
        "programme": programme,
        "branch": branch,
        "curriculum_id": curriculum_id,
        "year": year,
        "version": version,
        "heading": None,
        "section_path": None,
    }
    if source_type == "submitted_curriculum":
        base_metadata["owner_id"] = owner_id
    if pages:
        documents = [
            Document(
                page_content=f"Page {page.page_number}\n{page.text}",
                metadata={**base_metadata, "page_number": page.page_number},
            )
            for page in pages
        ]
    else:
        # Retains compatibility for direct callers that provide flattened text.
        documents = [
            Document(
                page_content=text,
                metadata={**base_metadata, "page_number": None},
            )
        ]

    chunks = get_text_splitter().split_documents(documents)
    if not chunks:
        raise RuntimeError("The PDF did not produce any indexable chunks")

    for index, chunk in enumerate(chunks):
        chunk.metadata.update({"source": filename, "chunk_index": index})

    get_vectorstore(source_type).add_documents(chunks)
    register_document(
        filename,
        len(chunks),
        document_id=resolved_document_id,
        source_type=source_type,
        programme=programme,
        branch=branch,
        curriculum_id=curriculum_id,
        year=year,
        version=version,
        owner_id=owner_id,
    )
    return len(chunks), False


def retrieve_context(query: str) -> List[Document]:
    # The assistant is an official-reference assistant and must never search
    # private Designer vectors.
    vectorstore = get_aicte_vectorstore()
    retriever = vectorstore.as_retriever(search_kwargs={"k": get_settings().retrieval_k})
    return retriever.invoke(query)


def build_sources(documents: List[Document]) -> List[Source]:
    sources: List[Source] = []
    seen = set()

    for doc in documents:
        source_name = doc.metadata.get("source", "Indexed PDF")
        chunk_index = doc.metadata.get("chunk_index")
        key = (source_name, chunk_index, doc.page_content[:80])
        if key in seen:
            continue
        seen.add(key)

        excerpt = " ".join(doc.page_content.split())
        sources.append(
            Source(
                title=source_name,
                section=f"Chunk {chunk_index + 1}" if isinstance(chunk_index, int) else "Retrieved excerpt",
                detail=excerpt[:280] + ("..." if len(excerpt) > 280 else ""),
            )
        )

    return sources


def answer_question(query: str) -> Tuple[str, List[Source]]:
    documents = retrieve_context(query)
    if not documents:
        return (
            "I could not find relevant information in the indexed PDF documents.",
            [],
        )

    context_blocks = []
    for doc in documents:
        source_name = doc.metadata.get("source", "Indexed PDF")
        chunk_index = doc.metadata.get("chunk_index", "unknown")
        content = doc.page_content.strip()
        if content:
            context_blocks.append(f"[Source: {source_name}, chunk: {chunk_index}]\n{content}")

    prompt = (
        "You are an AI assistant for curriculum designers. Answer only from the "
        "provided indexed PDF context. If the context is insufficient, say what is "
        "missing instead of inventing policy. Keep the answer practical and cite "
        "the source document names in prose.\n\n"
        f"Context:\n{chr(10).join(context_blocks)}\n\n"
        f"Question: {query}\n\n"
        "Answer:"
    )

    response = get_llm().invoke(prompt)
    return getattr(response, "content", str(response)), build_sources(documents)
