from functools import lru_cache
from typing import List, Optional, Sequence, Tuple

from langchain_core.documents import Document
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_mongodb import MongoDBAtlasVectorSearch
from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.core.config import get_settings
from backend.data.database import get_aicte_collection, get_designer_collection
from backend.models.schemas import ChatMessage, Source
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
        temperature=0.15,
        max_tokens=settings.rag_answer_max_tokens,
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
    settings = get_settings()
    # Keep the highest-scoring chunks (precision) *and* merge in MMR results
    # (coverage). MMR alone can occasionally remove the exact answer while
    # seeking diversity, especially for a precise semester/course query.
    direct_matches = vectorstore.similarity_search_with_score(
        query, k=settings.retrieval_direct_k
    )
    for rank, (document, score) in enumerate(direct_matches, start=1):
        document.metadata["retrieval_rank"] = rank
        document.metadata["retrieval_score"] = score

    diverse_matches = vectorstore.max_marginal_relevance_search(
        query,
        k=settings.retrieval_k,
        fetch_k=max(settings.retrieval_fetch_k, settings.retrieval_k),
        lambda_mult=settings.retrieval_diversity,
    )
    combined: List[Document] = []
    seen_content = set()
    for document in [doc for doc, _ in direct_matches] + diverse_matches:
        fingerprint = " ".join(document.page_content.split())
        if not fingerprint or fingerprint in seen_content:
            continue
        seen_content.add(fingerprint)
        combined.append(document)

    return combined


def build_sources(documents: List[Document]) -> List[Source]:
    sources: List[Source] = []
    seen = set()

    for doc in documents:
        source_name = doc.metadata.get("source", "Indexed PDF")
        chunk_index = doc.metadata.get("chunk_index")
        retrieval_rank = doc.metadata.get("retrieval_rank")
        key = (source_name, chunk_index, doc.page_content[:80])
        if key in seen:
            continue
        seen.add(key)

        excerpt = " ".join(doc.page_content.split())
        sources.append(
            Source(
                title=source_name,
                section=(
                    f"Chunk {chunk_index + 1}"
                    if isinstance(chunk_index, int)
                    else f"Retrieved result {retrieval_rank}"
                    if isinstance(retrieval_rank, int)
                    else "Retrieved excerpt"
                ),
                detail=excerpt[:500] + ("..." if len(excerpt) > 500 else ""),
            )
        )

    return sources


def _format_history(history: Sequence[ChatMessage]) -> str:
    if not history:
        return "No previous conversation."

    # The current turn is retrieved independently; history provides only the
    # conversational reference needed to resolve follow-up questions.
    return "\n".join(
        f"{message.role.title()}: {message.content.strip()}"
        for message in history[-6:]
        if message.content.strip()
    )


def answer_question(query: str, history: Sequence[ChatMessage] = ()) -> Tuple[str, List[Source]]:
    documents = retrieve_context(query)
    if not documents:
        return (
            "I could not find relevant information in the indexed PDF documents.",
            [],
        )

    context_blocks = []
    context_length = 0
    context_limit = get_settings().rag_context_char_limit
    for doc in documents:
        source_name = doc.metadata.get("source", "Indexed PDF")
        raw_chunk_index = doc.metadata.get("chunk_index")
        chunk_index = raw_chunk_index + 1 if isinstance(raw_chunk_index, int) else None
        retrieval_rank = doc.metadata.get("retrieval_rank")
        citation = (
            f"chunk: {chunk_index}"
            if chunk_index is not None
            else f"retrieved result: {retrieval_rank}"
            if isinstance(retrieval_rank, int)
            else "retrieved excerpt"
        )
        content = doc.page_content.strip()
        if content:
            block = f"[Source: {source_name}, {citation}]\n{content}"
            remaining = context_limit - context_length
            if remaining <= 0:
                break
            context_blocks.append(block[:remaining])
            context_length += len(block)

    prompt = (
        "You are a careful AI assistant for curriculum designers. Answer only from "
        "the retrieved indexed-PDF context. Conversation history is for resolving "
        "references only; it is not evidence. Do not invent policy, requirements, "
        "numbers, or citations.\n\n"
        "Answer every distinct part of the question that is supported by the "
        "context. Write a complete, useful answer; do not stop at a brief summary "
        "when the context supports detail. Use this plain-text format exactly where "
        "relevant:\n"
        "SUMMARY\n"
        "2–4 sentences that directly answer the question.\n\n"
        "DETAILED GUIDANCE\n"
        "Use clear numbered steps or bullets. Explain implications for curriculum "
        "design, not just the rule.\n\n"
        "EVIDENCE\n"
        "For each important claim, cite the supplied source tag exactly as shown, for "
        "example [Source: Guidelines.pdf, chunk: 2].\n\n"
        "When the question asks for a comparison, mapping, allocation, or a list with "
        "three or more repeated fields, use a Markdown table with a header row.\n\n"
        "GAPS OR NEXT STEPS\n"
        "State missing evidence or practical next actions. Include this section only "
        "when applicable. If the retrieved context is insufficient, say so clearly "
        "and do not fill gaps with general knowledge.\n\n"
        f"Conversation history:\n{_format_history(history)}\n\n"
        f"Retrieved PDF context:\n{chr(10).join(context_blocks)}\n\n"
        f"Question: {query}\n\n"
        "Answer:"
    )

    response = get_llm().invoke(prompt)
    return getattr(response, "content", str(response)), build_sources(documents)
