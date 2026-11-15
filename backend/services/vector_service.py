from __future__ import annotations

from typing import Any

from .vector_db.chroma_client import get_chroma_client


class VectorServiceError(Exception):
    """Raised when vector DB operations fail."""


class VectorService:
    """Thin service wrapper around the Chroma client."""

    def __init__(self) -> None:
        self.client = get_chroma_client()

    async def upsert(
        self,
        collection_name: str,
        ids: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]] | None = None,
        documents: list[str] | None = None,
    ) -> dict[str, Any]:
        try:
            return await self.client.upsert(
                collection_name=collection_name,
                ids=ids,
                embeddings=embeddings,
                metadatas=metadatas,
                documents=documents,
            )
        except Exception as exc:
            raise VectorServiceError(str(exc)) from exc

    async def query(
        self,
        collection_name: str,
        query_embedding: list[float],
        top_k: int = 5,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        try:
            return await self.client.query(
                collection_name=collection_name,
                query_embedding=query_embedding,
                n_results=top_k,
                where=where,
            )
        except Exception as exc:
            raise VectorServiceError(str(exc)) from exc

    async def delete(self, collection_name: str, ids: list[str]) -> bool:
        try:
            collection = await self.client.get_or_create_collection(collection_name)
            await self.client._run_blocking(collection.delete, ids=ids)
            return True
        except Exception as exc:
            raise VectorServiceError(str(exc)) from exc


_default_vector_service: VectorService | None = None


def get_vector_service() -> VectorService:
    """Return the singleton vector service."""

    global _default_vector_service
    if _default_vector_service is None:
        _default_vector_service = VectorService()
    return _default_vector_service
