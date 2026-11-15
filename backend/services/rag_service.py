from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from ..models.knowledge_models import KnowledgeChunk, KnowledgeDocument
from . import embeddings
from .vector_db import chroma_client

logger = logging.getLogger(__name__)


def extract_text_from_file(
    content_bytes: bytes, filename: Optional[str] = None, content_type: Optional[str] = None
) -> str:
    """
    Extract readable text from uploaded file bytes (txt, md, json, csv, etc.).
    """
    ext = (filename or "").split(".")[-1].lower() if filename else ""
    ctype = (content_type or "").lower()

    if ext == "json" or "json" in ctype:
        try:
            parsed = json.loads(content_bytes.decode("utf-8", errors="replace"))
            return json.dumps(parsed, indent=2, ensure_ascii=False)
        except Exception:
            return content_bytes.decode("utf-8", errors="replace")

    # Try utf-8 first, fallback to latin-1
    try:
        return content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return content_bytes.decode("latin-1", errors="replace")


def chunk_text(
    text: str, chunk_size: int = 500, chunk_overlap: int = 50
) -> List[str]:
    """
    Recursively split text into overlapping chunks.
    Preserves paragraph and sentence boundaries wherever possible.
    """
    clean_text = text.strip()
    if not clean_text:
        return []

    if len(clean_text) <= chunk_size:
        return [clean_text]

    # Split by double newlines first (paragraphs)
    paragraphs = re.split(r"\n\s*\n", clean_text)
    chunks: List[str] = []
    current_chunk = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # If a single paragraph exceeds chunk_size, split by lines or sentences
        if len(para) > chunk_size:
            sentences = re.split(r"(?<=[.!?])\s+", para)
            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue
                if len(current_chunk) + len(sentence) + 1 <= chunk_size:
                    current_chunk = f"{current_chunk} {sentence}".strip()
                else:
                    if current_chunk:
                        chunks.append(current_chunk)
                        # Carry over overlap
                        overlap_text = current_chunk[-chunk_overlap:] if len(current_chunk) > chunk_overlap else current_chunk
                        current_chunk = f"{overlap_text} {sentence}".strip()
                    else:
                        # Single sentence is huge: split by words
                        words = sentence.split()
                        sub_chunk = ""
                        for word in words:
                            if len(sub_chunk) + len(word) + 1 <= chunk_size:
                                sub_chunk = f"{sub_chunk} {word}".strip()
                            else:
                                if sub_chunk:
                                    chunks.append(sub_chunk)
                                sub_chunk = word
                        if sub_chunk:
                            current_chunk = sub_chunk
        else:
            if len(current_chunk) + len(para) + 2 <= chunk_size:
                current_chunk = f"{current_chunk}\n\n{para}".strip()
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                    overlap_text = current_chunk[-chunk_overlap:] if len(current_chunk) > chunk_overlap else current_chunk
                    current_chunk = f"{overlap_text}\n\n{para}".strip()
                else:
                    current_chunk = para

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def get_tenant_collection_name(user_id: int) -> str:
    """Format canonical Chroma collection name for a given tenant."""
    return f"iba_knowledge_{user_id}"


async def ingest_document(
    db: Session,
    user_id: int,
    title: str,
    content: str,
    filename: Optional[str] = None,
    content_type: Optional[str] = None,
    doc_metadata: Optional[Dict[str, Any]] = None,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> KnowledgeDocument:
    """
    Ingest a document into PostgreSQL and upsert embedded chunks into tenant vector storage.
    """
    clean_content = content.strip()
    if not clean_content:
        raise ValueError("Document content cannot be empty")

    doc = KnowledgeDocument(
        user_id=user_id,
        title=title.strip() or "Untitled Document",
        filename=filename,
        content_type=content_type or "text/plain",
        file_size=len(content.encode("utf-8")),
        raw_content=clean_content,
        doc_metadata=doc_metadata or {},
        chunk_count=0,
    )
    db.add(doc)
    db.flush()

    # Split into overlapping chunks
    text_chunks = chunk_text(clean_content, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    if not text_chunks:
        text_chunks = [clean_content]

    # Generate embeddings for all chunks in batch
    emb_result = await embeddings.embed(text_chunks)
    vectors = emb_result.embeddings

    client = chroma_client.get_chroma_client()
    collection_name = get_tenant_collection_name(user_id)

    vector_ids: List[str] = []
    chunk_records: List[KnowledgeChunk] = []
    chroma_metadatas: List[Dict[str, Any]] = []

    for idx, (chunk_str, vec) in enumerate(zip(text_chunks, vectors)):
        v_id = f"doc_{doc.id}_chunk_{idx}"
        vector_ids.append(v_id)

        chunk_record = KnowledgeChunk(
            document_id=doc.id,
            user_id=user_id,
            chunk_index=idx,
            content=chunk_str,
            token_count=len(chunk_str.split()),
            vector_id=v_id,
        )
        db.add(chunk_record)
        chunk_records.append(chunk_record)

        chroma_metadatas.append({
            "document_id": doc.id,
            "chunk_index": idx,
            "user_id": user_id,
            "title": doc.title,
        })

    # Upsert to Chroma with tenant-scoping
    await client.upsert(
        collection_name=collection_name,
        ids=vector_ids,
        embeddings=vectors,
        metadatas=chroma_metadatas,
        documents=text_chunks,
    )

    doc.chunk_count = len(text_chunks)
    db.commit()
    db.refresh(doc)
    logger.info("Ingested document %d ('%s') with %d chunks for tenant %d", doc.id, doc.title, doc.chunk_count, user_id)
    return doc


async def retrieve_knowledge(
    user_id: int,
    query: str,
    top_k: int = 5,
    document_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Semantic similarity search over the tenant's knowledge base.
    Guarantees cross-tenant isolation by querying the tenant's collection
    and filtering by where={'user_id': user_id}.
    """
    clean_query = query.strip()
    if not clean_query:
        return []

    emb_result = await embeddings.embed([clean_query])
    if not emb_result.embeddings:
        return []

    query_vector = emb_result.embeddings[0]
    client = chroma_client.get_chroma_client()
    collection_name = get_tenant_collection_name(user_id)

    if document_id is not None:
        where: Dict[str, Any] = {
            "$and": [
                {"user_id": user_id},
                {"document_id": document_id},
            ]
        }
    else:
        where = {"user_id": user_id}

    try:
        raw_hits = await client.query(
            collection_name=collection_name,
            query_embedding=query_vector,
            n_results=top_k,
            where=where,
        )
    except Exception as e:
        logger.debug("Knowledge retrieval query returned empty or collection not found: %s", e)
        return []

    results: List[Dict[str, Any]] = []
    for hit in raw_hits:
        doc_text = hit.get("document") or ""
        meta = hit.get("metadata") or {}
        # Convert distance to similarity score where distance near 0 means score near 1
        dist = hit.get("distance")
        score = 1.0 / (1.0 + float(dist)) if dist is not None else 1.0

        results.append({
            "id": hit.get("id"),
            "content": doc_text,
            "score": round(score, 4),
            "document_id": meta.get("document_id"),
            "title": meta.get("title", "Untitled Document"),
            "chunk_index": meta.get("chunk_index", 0),
            "metadata": meta,
        })

    return results


async def delete_document(
    db: Session,
    user_id: int,
    document_id: int,
) -> bool:
    """
    Delete a document and purge its vectors from Chroma, ensuring user ownership.
    """
    doc = (
        db.query(KnowledgeDocument)
        .filter(KnowledgeDocument.id == document_id, KnowledgeDocument.user_id == user_id)
        .first()
    )
    if doc is None:
        return False

    client = chroma_client.get_chroma_client()
    collection_name = get_tenant_collection_name(user_id)

    try:
        await client.delete(collection_name=collection_name, where={"document_id": document_id})
    except Exception as e:
        logger.debug("Chroma vector cleanup for document %d: %s", document_id, e)

    db.delete(doc)
    db.commit()
    logger.info("Deleted document %d for tenant %d", document_id, user_id)
    return True
