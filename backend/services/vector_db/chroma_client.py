import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ChromaNotAvailable(Exception):
    pass


class ChromaClient:
    """
    Lightweight adapter for Chroma (chromadb).
    - Uses local duckdb+parquet persist directory by default (CHROMA_DIR)
    - If CHROMA_SERVER_HOST/PORT present will attempt REST mode.
    Methods are async (wrap blocking chromadb calls with asyncio.to_thread).
    """

    def __init__(self, persist_directory: Optional[str] = None, settings: Optional[Dict[str, Any]] = None) -> None:
        try:
            import chromadb  # type: ignore
            from chromadb.config import Settings  # type: ignore
        except Exception as e:
            logger.debug("chromadb import failed: %s", e)
            raise ChromaNotAvailable("chromadb package is not installed") from e

        persist_dir = persist_directory or os.getenv("CHROMA_DIR") or "./data/vector_db/chroma"
        server_host = os.getenv("CHROMA_SERVER_HOST") or os.getenv("CHROMA_HOST")
        server_port = os.getenv("CHROMA_SERVER_PORT") or os.getenv("CHROMA_PORT") or "8000"

        self._Settings = Settings
        self._client = None

        if server_host:
            try:
                self._client = chromadb.HttpClient(
                    host=server_host,
                    port=int(server_port),
                )
                self._client.heartbeat()
                logger.info("ChromaClient connected to HTTP server %s:%s", server_host, server_port)
            except Exception as e:
                logger.warning(
                    "Unable to connect to Chroma HTTP server %s:%s (%s), falling back to PersistentClient",
                    server_host,
                    server_port,
                    e,
                )
                self._client = None

        if self._client is None:
            try:
                os.makedirs(persist_dir, exist_ok=True)
                self._client = chromadb.PersistentClient(path=persist_dir)
                logger.info("ChromaClient initialized with PersistentClient at %s", persist_dir)
            except Exception as e:
                logger.warning(
                    "Failed to initialize PersistentClient at %s (%s), falling back to EphemeralClient",
                    persist_dir,
                    e,
                )
                self._client = chromadb.EphemeralClient()

        self._closed = False

    async def _run_blocking(self, fn, *args, **kwargs):
        return await asyncio.to_thread(lambda: fn(*args, **kwargs))

    async def create_collection(self, name: str, metadata: Optional[Dict[str, Any]] = None) -> Any:
        def _create():
            return self._client.create_collection(name=name, metadata=metadata or {})

        return await self._run_blocking(_create)

    async def get_or_create_collection(self, name: str, metadata: Optional[Dict[str, Any]] = None):
        def _get():
            try:
                return self._client.get_collection(name)
            except Exception:
                return self._client.create_collection(name=name, metadata=metadata or {})

        return await self._run_blocking(_get)

    async def list_collections(self) -> List[str]:
        def _list():
            cols = self._client.list_collections()
            # chromadb returns list of dicts with 'name' key
            return [c.get("name") for c in cols]

        return await self._run_blocking(_list)

    async def delete_collection(self, name: str) -> None:
        def _delete():
            self._client.delete_collection(name)

        return await self._run_blocking(_delete)

    async def upsert(
        self,
        collection_name: str,
        ids: List[str],
        embeddings: List[List[float]],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        documents: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Upsert vectors/documents into a collection.
        ids, embeddings must be same length. metadatas/documents optional.
        Returns provider response (best-effort).
        """
        if not ids or not embeddings or len(ids) != len(embeddings):
            raise ValueError("ids and embeddings required and must be same length")

        def _upsert():
            coll = None
            try:
                coll = self._client.get_collection(collection_name, embedding_function=None)
            except Exception:
                try:
                    coll = self._client.create_collection(collection_name, embedding_function=None)
                except Exception:
                    coll = self._client.get_collection(collection_name)
            # chromadb's add/upsert API
            try:
                coll.add(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=documents)
            except Exception:
                # fallback to upsert if add fails (collection exists)
                coll.upsert(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=documents)
            # optional persist if supported
            try:
                if hasattr(self._client, "persist"):
                    self._client.persist()
            except Exception:
                pass
            return {"ok": True, "count": len(ids)}

        return await self._run_blocking(_upsert)

    async def query(
        self,
        collection_name: str,
        query_embedding: List[float],
        n_results: int = 5,
        include: Optional[List[str]] = None,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query collection by embedding. Returns list of hits with id, distance, metadata, document.
        """
        # In ChromaDB, 'ids' are always returned in query results and are NOT allowed in include
        include = include or ["metadatas", "documents", "distances"]
        def _query():
            try:
                coll = self._client.get_collection(collection_name, embedding_function=None)
            except Exception:
                try:
                    coll = self._client.get_collection(collection_name)
                except Exception:
                    # Collection does not exist yet (e.g. user has no documents/memories)
                    return []
            res = coll.query(query_embeddings=[query_embedding], n_results=n_results, include=include, where=where)
            # normalize into list of hits
            out: List[Dict[str, Any]] = []
            # chromadb returns lists per field; handle single-query result
            if not res:
                return out
            # res shape: { 'ids': [[...]], 'distances': [[...]], 'metadatas': [[...]], 'documents': [[...]] }
            ids = res.get("ids", [[]])[0]
            dists = res.get("distances", [[]])[0] if "distances" in res else []
            docs = res.get("documents", [[]])[0] if "documents" in res else []
            metas = res.get("metadatas", [[]])[0] if "metadatas" in res else []
            length = max(len(ids), len(dists), len(docs), len(metas))
            for i in range(length):
                hit = {
                    "id": ids[i] if i < len(ids) else None,
                    "distance": dists[i] if i < len(dists) else None,
                    "document": docs[i] if i < len(docs) else None,
                    "metadata": metas[i] if i < len(metas) else None,
                }
                out.append(hit)
            return out

        return await self._run_blocking(_query)

    async def query_documents(
        self, collection_name: str, text_embedding: List[float], top_k: int = 5
    ) -> List[Dict[str, Any]]:
        return await self.query(collection_name, query_embedding=text_embedding, n_results=top_k)

    async def delete(
        self,
        collection_name: str,
        ids: Optional[List[str]] = None,
        where: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        def _delete():
            try:
                coll = self._client.get_collection(collection_name)
                kwargs = {}
                if ids is not None:
                    kwargs["ids"] = ids
                if where is not None:
                    kwargs["where"] = where
                coll.delete(**kwargs)
                return {"ok": True}
            except Exception as e:
                logger.debug("Chroma delete warning for %s: %s", collection_name, e)
                return {"ok": False, "error": str(e)}

        return await self._run_blocking(_delete)

    async def count(self, collection_name: str) -> int:
        def _count():
            try:
                coll = self._client.get_collection(collection_name)
                return coll.count()
            except Exception:
                return 0

        return await self._run_blocking(_count)

    async def persist(self) -> None:
        def _persist():
            try:
                if hasattr(self._client, "persist"):
                    self._client.persist()
            except Exception:
                logger.exception("Chroma persist failed")

        await self._run_blocking(_persist)

    async def close(self) -> None:
        if self._closed:
            return
        def _close():
            try:
                if hasattr(self._client, "persist"):
                    self._client.persist()
            except Exception:
                pass
            try:
                if hasattr(self._client, "close"):
                    self._client.close()
            except Exception:
                pass
        await self._run_blocking(_close)
        self._closed = True


# Module-level default client (singleton)
_default_client: Optional[ChromaClient] = None


def get_chroma_client(persist_directory: Optional[str] = None) -> ChromaClient:
    global _default_client
    if _default_client is None:
        _default_client = ChromaClient(persist_directory)
    return _default_client


# Convenience async wrappers
async def upsert(
    collection_name: str,
    ids: List[str],
    embeddings: List[List[float]],
    metadatas: Optional[List[Dict[str, Any]]] = None,
    documents: Optional[List[str]] = None,
) -> Dict[str, Any]:
    client = get_chroma_client()
    return await client.upsert(collection_name, ids, embeddings, metadatas=metadatas, documents=documents)


async def query(
    collection_name: str,
    query_embedding: List[float],
    n_results: int = 5,
    include: Optional[List[str]] = None,
    where: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    client = get_chroma_client()
    return await client.query(collection_name, query_embedding, n_results=n_results, include=include , where=where )