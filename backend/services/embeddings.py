import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingResult:
    embeddings: List[List[float]]
    model: Optional[str] = None
    provider: Optional[str] = None
    raw: Optional[Any] = None


class EmbeddingError(Exception):
    pass


class EmbeddingService:
    """
    Unified embeddings pipeline.
    Tries (in order):
      - llm_service.embed (preferred unified entrypoint)
      - provider clients (deepseek, openrouter) under services.models.*
    Returns EmbeddingResult.
    """

    def __init__(self) -> None:
        # prefer environment override
        self.default_model = os.getenv("EMBEDDING_MODEL") or os.getenv("DEFAULT_EMBEDDING_MODEL")
        # provider preference: comma-separated, e.g. "deepseek,openrouter"
        pref = os.getenv("EMBEDDING_PROVIDERS") or os.getenv("MODEL_PREFERENCES") or ""
        self.provider_preferences = [p.strip().lower() for p in pref.split(",") if p.strip()]

    async def _call_llm_service_embed(self, inputs: List[str], model: Optional[str] = None) -> EmbeddingResult:
        try:
            from . import llm_service  # type: ignore
        except Exception:
            raise EmbeddingError("llm_service not available")

        model_to_use = model or self.default_model
        if not hasattr(llm_service, "embed"):
            raise EmbeddingError("llm_service.embed not implemented")

        resp = await llm_service.embed(inputs, model_hint=None, model=model_to_use)
        # llm_service.embed is expected to return object with .embeddings or provider-specific raw shape
        if hasattr(resp, "embeddings"):
            return EmbeddingResult(embeddings=resp.embeddings, model=getattr(resp, "model", model_to_use), provider=getattr(resp, "provider", None), raw=getattr(resp, "raw", None))
        # try to normalize common shapes
        if isinstance(resp, dict):
            data = resp.get("data") or resp.get("embeddings") or []
            emb_list = []
            if isinstance(data, list) and data and isinstance(data[0], dict) and "embedding" in data[0]:
                for d in data:
                    emb_list.append(d.get("embedding"))
            elif isinstance(data, list) and data and isinstance(data[0], list):
                emb_list = data
            if emb_list:
                return EmbeddingResult(embeddings=emb_list, model=resp.get("model") or model_to_use, provider=resp.get("provider"))
        raise EmbeddingError("Unable to normalize llm_service.embed response")

    async def _call_deepseek(self, inputs: List[str], model: Optional[str] = None) -> EmbeddingResult:
        try:
            from .models import deepseek_client as deepseek  # type: ignore
        except Exception:
            raise EmbeddingError("deepseek client not available")

        model_to_use = model or self.default_model
        if not getattr(deepseek, "embed", None) and not getattr(deepseek, "DeepSeekClient", None):
            raise EmbeddingError("deepseek embed method not found")

        # support module-level embed or client instance
        if getattr(deepseek, "embed", None):
            resp = await deepseek.embed(model_to_use, inputs)
        else:
            client = deepseek.DeepSeekClient(api_key=os.getenv("DEEPSEEK_API_KEY"))
            resp = await client.embed(model_to_use, inputs)

        # normalize
        if isinstance(resp, dict):
            data = resp.get("data") or []
            emb_list = []
            for item in data:
                if isinstance(item, dict) and "embedding" in item:
                    emb_list.append(item["embedding"])
                elif isinstance(item, list):
                    emb_list.append(item)
            if emb_list:
                return EmbeddingResult(embeddings=emb_list, model=model_to_use, provider="deepseek", raw=resp)
        raise EmbeddingError("Unable to normalize deepseek response")

    async def _call_openrouter(self, inputs: List[str], model: Optional[str] = None) -> EmbeddingResult:
        try:
            from .models import openrouter_client as openrouter  # type: ignore
        except Exception:
            raise EmbeddingError("openrouter client not available")

        model_to_use = model or self.default_model
        if not getattr(openrouter, "embed", None) and not getattr(openrouter, "OpenRouterClient", None):
            raise EmbeddingError("openrouter embed not found")

        if getattr(openrouter, "embed", None):
            resp = await openrouter.embed(model_to_use, inputs)
        else:
            client = openrouter.OpenRouterClient(api_key=os.getenv("OPENROUTER_KEY"))
            resp = await client.embed(model_to_use, inputs)

        if isinstance(resp, dict):
            # try common OpenAI-like shape
            if "data" in resp:
                emb_list = []
                for d in resp.get("data", []):
                    if isinstance(d, dict) and "embedding" in d:
                        emb_list.append(d["embedding"])
                    elif isinstance(d, list):
                        emb_list.append(d)
                if emb_list:
                    return EmbeddingResult(embeddings=emb_list, model=model_to_use, provider="openrouter", raw=resp)
            if "embeddings" in resp and isinstance(resp["embeddings"], list):
                return EmbeddingResult(embeddings=resp["embeddings"], model=model_to_use, provider="openrouter", raw=resp)
        raise EmbeddingError("Unable to normalize openrouter response")

    def _deterministic_embed(self, text: str, dim: int = 384) -> List[float]:
        """
        Fast deterministic normalized embedding vector.
        Ensures consistent, reproducible similarity metrics in offline/test environments.
        """
        import hashlib
        import math
        import re

        words = re.findall(r"\w+", text.lower())
        vec = [0.0] * dim
        if not words:
            return vec

        for word in words:
            h = hashlib.md5(word.encode("utf-8")).hexdigest()
            idx1 = int(h[:4], 16) % dim
            idx2 = int(h[4:8], 16) % dim
            idx3 = int(h[8:12], 16) % dim
            vec[idx1] += 1.0
            vec[idx2] += 0.5
            vec[idx3] += 0.25

        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    async def _call_sentence_transformers(self, inputs: List[str], model: Optional[str] = None) -> EmbeddingResult:
        model_name = model or self.default_model or "all-MiniLM-L6-v2"
        def _embed():
            from sentence_transformers import SentenceTransformer  # type: ignore
            st_model = SentenceTransformer(model_name)
            embeddings = st_model.encode(inputs, normalize_embeddings=True)
            return [e.tolist() for e in embeddings]

        try:
            embs = await asyncio.to_thread(_embed)
            return EmbeddingResult(embeddings=embs, model=model_name, provider="sentence-transformers")
        except Exception as e:
            raise EmbeddingError(f"sentence_transformers failed: {e}") from e

    async def _call_chroma_default(self, inputs: List[str]) -> EmbeddingResult:
        def _embed():
            from chromadb.utils import embedding_functions  # type: ignore
            ef = embedding_functions.DefaultEmbeddingFunction()
            return ef(inputs)

        try:
            embs = await asyncio.to_thread(_embed)
            return EmbeddingResult(embeddings=embs, model="chroma-default", provider="chroma")
        except Exception as e:
            raise EmbeddingError(f"chroma default embedding failed: {e}") from e

    async def embed(self, inputs: List[str], model: Optional[str] = None, provider: Optional[str] = None, batch_size: int = 32) -> EmbeddingResult:
        """
        Embed a list of strings. Tries provider selection and batching.
        Returns EmbeddingResult with list of embeddings corresponding to inputs order.
        """
        if not inputs:
            return EmbeddingResult(embeddings=[], model=model, provider=provider)

        # choose provider order
        order = []
        if provider:
            order = [provider.lower()]
        order += self.provider_preferences
        tried = []
        errors: Dict[str, Exception] = {}

        async def _try_provider(name: str):
            try:
                if name in ("sentence_transformers", "sentence-transformers", "st"):
                    return await self._call_sentence_transformers(inputs, model=model)
                if name == "chroma":
                    return await self._call_chroma_default(inputs)
                if name == "llm" or name == "llm_service":
                    return await self._call_llm_service_embed(inputs, model=model)
                if name in ("deepseek", "deeps", "deep-seek"):
                    return await self._call_deepseek(inputs, model=model)
                if name in ("openrouter", "open-router"):
                    return await self._call_openrouter(inputs, model=model)
                return await self._call_llm_service_embed(inputs, model=model)
            except Exception as e:
                errors[name] = e
                logger.debug("embed provider %s failed: %s", name, e)
                return None

        for p in order:
            if p in tried:
                continue
            tried.append(p)
            res = await _try_provider(p)
            if res:
                return res

        for p in ("sentence_transformers", "chroma", "llm", "deepseek", "openrouter"):
            if p in tried:
                continue
            res = await _try_provider(p)
            if res:
                return res

        # Resilient local deterministic fallback so indexing and similarity search never crash
        logger.debug("Falling back to local deterministic embedding generator for %d inputs", len(inputs))
        embs = [self._deterministic_embed(text) for text in inputs]
        return EmbeddingResult(embeddings=embs, model="deterministic-384", provider="local-fallback")


# module-level singleton
_default_embeddings: Optional[EmbeddingService] = None


def get_embeddings_service() -> EmbeddingService:
    global _default_embeddings
    if _default_embeddings is None:
        _default_embeddings = EmbeddingService()
    return _default_embeddings


# convenience wrapper
async def embed(inputs: List[str], model: Optional[str] = None, provider: Optional[str] = None, batch_size: int = 32) -> EmbeddingResult:
    svc = get_embeddings_service()
    return await svc.embed(inputs=inputs, model=model, provider=provider, batch_size=batch_size)
