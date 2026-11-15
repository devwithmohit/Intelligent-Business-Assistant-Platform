from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# storage location (can be overridden via env or core config)
_DEFAULT_DB_PATH = os.getenv("MEMORY_STORE_PATH")
if not _DEFAULT_DB_PATH:
    cand_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "data", "traditional_db", "memory.json"
    )
    try:
        os.makedirs(os.path.dirname(cand_path), exist_ok=True)
        # Test write access
        test_file = f"{cand_path}.test"
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
        _DEFAULT_DB_PATH = cand_path
    except Exception:
        _DEFAULT_DB_PATH = "/tmp/memory.json"
        os.makedirs(os.path.dirname(_DEFAULT_DB_PATH), exist_ok=True)

_file_lock = threading.Lock()


def _read_store(path: str) -> Dict[str, List[Dict[str, Any]]]:
    if not os.path.exists(path):
        return {"records": []}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        logger.exception("Failed to read memory store, returning empty")
        return {"records": []}


def _write_store(path: str, data: Dict[str, Any]) -> None:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = f"{path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except (OSError, PermissionError) as e:
        logger.warning("Could not write to persistent memory path %s (%s), writing to /tmp/memory.json", path, e)
        fallback = "/tmp/memory.json"
        tmp = f"{fallback}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, fallback)


async def _io_read(path: str) -> Dict[str, Any]:
    return await asyncio.to_thread(lambda: _read_store(path))


async def _io_write(path: str, data: Dict[str, Any]) -> None:
    return await asyncio.to_thread(lambda: _write_store(path, data))


# Basic in-file JSON memory with simple text-match query. Non-blocking callers via asyncio.
async def store_memory(
    agent_id: str,
    key: str,
    value: Any,
    metadata: Optional[Dict[str, Any]] = None,
    user_id: Optional[int] = None,
) -> str:
    """
    Store a memory record. Returns generated record id.
    Records are optionally partitioned by user_id for multi-tenancy.
    """
    path = _DEFAULT_DB_PATH
    record_id = str(uuid.uuid4())
    meta = dict(metadata or {})
    if user_id is not None:
        meta["user_id"] = user_id

    rec = {
        "id": record_id,
        "agent_id": agent_id,
        "user_id": user_id,
        "key": key,
        "value": value,
        "metadata": meta,
        "ts": int(time.time()),
    }

    def _write():
        with _file_lock:
            data = _read_store(path)
            records = data.get("records", [])
            records.append(rec)
            data["records"] = records
            _write_store(path, data)

    await asyncio.to_thread(_write)
    return record_id


async def get_memory(
    agent_id: Optional[str] = None,
    key: Optional[str] = None,
    user_id: Optional[int] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """
    Retrieve recent memory records.
    Filters by agent_id, key, and user_id when provided.
    Returns up to `limit` most-recent records (newest first).
    """
    path = _DEFAULT_DB_PATH

    def _read_filtered():
        with _file_lock:
            data = _read_store(path)
        records = data.get("records", [])
        out = []
        for r in reversed(records):  # newest first
            if user_id is not None and r.get("user_id") is not None and r.get("user_id") != user_id:
                continue
            if agent_id and r.get("agent_id") != agent_id:
                continue
            if key and r.get("key") != key:
                continue
            out.append(r)
            if len(out) >= limit:
                break
        return out

    return await asyncio.to_thread(_read_filtered)


async def query_memory_by_text(
    query: str,
    agent_id: Optional[str] = None,
    user_id: Optional[int] = None,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """
    Keyword text search over stored memory values scoped by user_id.
    """
    if not query:
        return []

    q = query.lower().strip().split()
    all_recs = await get_memory(agent_id=agent_id, key=None, user_id=user_id, limit=1000)
    scored: List[Dict[str, Any]] = []
    for r in all_recs:
        text = json.dumps(r.get("value", ""), ensure_ascii=False).lower()
        score = 0
        for token in q:
            if token and token in text:
                score += text.count(token)
        if score > 0:
            scored.append({"record": r, "score": score})
    scored.sort(key=lambda x: x["score"], reverse=True)
    return [s["record"] for s in scored[:top_k]]


async def clear_memory(
    agent_id: Optional[str] = None,
    key: Optional[str] = None,
    user_id: Optional[int] = None,
) -> int:
    """
    Remove matching memory records. Returns number of removed records.
    """
    path = _DEFAULT_DB_PATH

    def _clear():
        with _file_lock:
            data = _read_store(path)
            records = data.get("records", [])
            new_records = []
            removed = 0
            for r in records:
                if user_id is not None and r.get("user_id") is not None and r.get("user_id") != user_id:
                    new_records.append(r)
                    continue
                if agent_id and r.get("agent_id") != agent_id:
                    new_records.append(r)
                    continue
                if key and r.get("key") != key:
                    new_records.append(r)
                    continue
                removed += 1
            data["records"] = new_records
            _write_store(path, data)
        return removed

    return await asyncio.to_thread(_clear)


# ---------------------------------------------------------------------------
# Vector Memory Implementation (Chroma + Embeddings)
# ---------------------------------------------------------------------------

async def upsert_vector(
    id: str,
    vector: List[float],
    metadata: Optional[Dict[str, Any]] = None,
    user_id: Optional[int] = None,
    collection_name: Optional[str] = None,
    document: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Upsert a vector to Chroma with tenant-scoping (user_id).
    Replaces earlier NotImplementedError placeholder.
    """
    from .vector_db import chroma_client

    meta = dict(metadata or {})
    if user_id is not None:
        meta["user_id"] = user_id

    coll = collection_name or (f"user_{user_id}_memories" if user_id else "general_memories")
    client = chroma_client.get_chroma_client()
    return await client.upsert(
        collection_name=coll,
        ids=[id],
        embeddings=[vector],
        metadatas=[meta],
        documents=[document] if document else None,
    )


async def query_vector(
    vector: List[float],
    top_k: int = 5,
    namespace: Optional[str] = None,
    user_id: Optional[int] = None,
    collection_name: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Query vector similarity in Chroma with strict tenant filtering.
    Replaces earlier NotImplementedError placeholder.
    """
    from .vector_db import chroma_client

    coll = collection_name or namespace or (f"user_{user_id}_memories" if user_id else "general_memories")
    client = chroma_client.get_chroma_client()
    where = {"user_id": user_id} if user_id is not None else None

    return await client.query(
        collection_name=coll,
        query_embedding=vector,
        n_results=top_k,
        where=where,
    )


async def store_vector_memory(
    key: str,
    text: str,
    user_id: int,
    agent_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Generate embedding for text and persist to tenant-scoped Chroma collection.
    """
    from . import embeddings

    emb_res = await embeddings.embed([text])
    if not emb_res.embeddings:
        raise RuntimeError("Embedding generation returned empty vector")

    vec = emb_res.embeddings[0]
    rec_id = str(uuid.uuid4())
    meta = dict(metadata or {})
    meta.update({
        "user_id": user_id,
        "key": key,
        "agent_id": agent_id or "",
        "created_at": int(time.time()),
    })

    await upsert_vector(
        id=rec_id,
        vector=vec,
        metadata=meta,
        user_id=user_id,
        document=text,
    )

    # Hybrid store: also save to traditional JSON memory
    await store_memory(
        agent_id=agent_id or "default",
        key=key,
        value=text,
        metadata=meta,
        user_id=user_id,
    )
    return rec_id


async def query_vector_memory(
    query: str,
    user_id: int,
    agent_id: Optional[str] = None,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """
    Query vector memories by natural language semantic search, scoped to tenant user_id.
    """
    from . import embeddings

    emb_res = await embeddings.embed([query])
    if not emb_res.embeddings:
        return []

    vec = emb_res.embeddings[0]
    hits = await query_vector(
        vector=vec,
        top_k=top_k,
        user_id=user_id,
    )

    if agent_id:
        hits = [h for h in hits if (h.get("metadata") or {}).get("agent_id") in (agent_id, "", None)]
    return hits


def get_memory_service():
    """
    Return module-level service mapping for callers expecting a dict/service object.
    """
    return {
        "store_memory": store_memory,
        "get_memory": get_memory,
        "query_memory_by_text": query_memory_by_text,
        "clear_memory": clear_memory,
        "upsert_vector": upsert_vector,
        "query_vector": query_vector,
        "store_vector_memory": store_vector_memory,
        "query_vector_memory": query_vector_memory,
    }
