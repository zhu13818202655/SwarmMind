"""Long-term memory abstractions and implementations."""

from __future__ import annotations

import hashlib
import math
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, PointStruct, VectorParams

    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False

try:
    import chromadb
    from chromadb.config import Settings

    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False


@dataclass
class MemoryItem:
    """A memory item."""

    id: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    score: float = 0.0


class EmbeddingProvider(Protocol):
    """Text embedding abstraction."""

    async def embed_text(self, text: str) -> list[float]:
        ...


class VectorStore(Protocol):
    """Vector storage abstraction."""

    async def upsert(self, item: MemoryItem, vector: list[float]) -> None:
        ...

    async def query(self, vector: list[float], top_k: int = 5) -> list[MemoryItem]:
        ...

    async def delete(self, memory_id: str) -> None:
        ...

    async def clear(self) -> None:
        ...


class LongTermMemoryBase:
    """Base class for long-term memory."""

    async def store(self, content: str, metadata: dict[str, Any] | None = None) -> str:
        """Store a memory item."""
        raise NotImplementedError

    async def retrieve(self, query: str, top_k: int = 5) -> list[MemoryItem]:
        """Retrieve similar memories."""
        raise NotImplementedError

    async def delete(self, memory_id: str) -> None:
        """Delete a memory item."""
        raise NotImplementedError

    async def clear(self) -> None:
        """Clear all memories."""
        raise NotImplementedError


class HashingEmbeddingProvider:
    """Deterministic local embedding provider for development and tests."""

    def __init__(self, dimensions: int = 256):
        self._dimensions = dimensions

    async def embed_text(self, text: str) -> list[float]:
        values = [0.0] * self._dimensions
        tokens = text.lower().split()
        if not tokens:
            return values

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:4], "big") % self._dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            values[bucket] += sign

        magnitude = math.sqrt(sum(value * value for value in values)) or 1.0
        return [value / magnitude for value in values]


class InMemoryVectorStore:
    """Simple vector store for local development."""

    def __init__(self) -> None:
        self._items: dict[str, tuple[MemoryItem, list[float]]] = {}

    async def upsert(self, item: MemoryItem, vector: list[float]) -> None:
        self._items[item.id] = (item, vector)

    async def query(self, vector: list[float], top_k: int = 5) -> list[MemoryItem]:
        scored: list[MemoryItem] = []
        for item, stored_vector in self._items.values():
            score = _cosine_similarity(vector, stored_vector)
            candidate = MemoryItem(
                id=item.id,
                content=item.content,
                metadata=dict(item.metadata),
                created_at=item.created_at,
                score=score,
            )
            scored.append(candidate)
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:top_k]

    async def delete(self, memory_id: str) -> None:
        self._items.pop(memory_id, None)

    async def clear(self) -> None:
        self._items.clear()


class QdrantVectorStore:
    """Qdrant-backed vector store."""

    def __init__(self, url: str = "http://127.0.0.1:6333", collection: str = "swarmmind", dimensions: int = 256):
        if not QDRANT_AVAILABLE:
            raise ImportError("qdrant-client is not installed")
        self._client = QdrantClient(url=url, check_compatibility=False)
        self._collection = collection
        self._dimensions = dimensions
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        collections = self._client.get_collections().collections
        if any(collection.name == self._collection for collection in collections):
            return
        self._client.create_collection(
            collection_name=self._collection,
            vectors_config=VectorParams(size=self._dimensions, distance=Distance.COSINE),
        )

    async def upsert(self, item: MemoryItem, vector: list[float]) -> None:
        self._client.upsert(
            collection_name=self._collection,
            points=[
                PointStruct(
                    id=item.id,
                    vector=vector,
                    payload={
                        "content": item.content,
                        "metadata": item.metadata,
                        "created_at": item.created_at.isoformat(),
                    },
                )
            ],
        )

    async def query(self, vector: list[float], top_k: int = 5) -> list[MemoryItem]:
        results = self._search(vector, top_k)
        return [
            MemoryItem(
                id=str(result.id),
                content=result.payload.get("content", ""),
                metadata=result.payload.get("metadata", {}),
                created_at=_parse_datetime(result.payload.get("created_at")),
                score=float(result.score),
            )
            for result in results
        ]

    async def delete(self, memory_id: str) -> None:
        self._client.delete(collection_name=self._collection, points_selector=[memory_id])

    async def clear(self) -> None:
        self._client.delete_collection(self._collection)
        self._ensure_collection()

    def _search(self, vector: list[float], top_k: int):
        search = getattr(self._client, "search", None)
        if callable(search):
            return search(
                collection_name=self._collection,
                query_vector=vector,
                limit=top_k,
            )

        query_points = getattr(self._client, "query_points", None)
        if callable(query_points):
            response = query_points(
                collection_name=self._collection,
                query=vector,
                limit=top_k,
            )
            points = getattr(response, "points", None)
            if points is not None:
                return list(points)

        raise AttributeError("Qdrant client does not expose a supported vector query method")


class VectorLongTermMemory(LongTermMemoryBase):
    """Long-term memory composed from an embedding provider and vector store."""

    def __init__(self, embedding_provider: EmbeddingProvider, vector_store: VectorStore):
        self._embedding_provider = embedding_provider
        self._vector_store = vector_store

    async def store(self, content: str, metadata: dict[str, Any] | None = None) -> str:
        memory_id = str(uuid.uuid4())
        item = MemoryItem(id=memory_id, content=content, metadata=metadata or {})
        vector = await self._embedding_provider.embed_text(content)
        await self._vector_store.upsert(item, vector)
        return memory_id

    async def retrieve(self, query: str, top_k: int = 5) -> list[MemoryItem]:
        vector = await self._embedding_provider.embed_text(query)
        return await self._vector_store.query(vector, top_k=top_k)

    async def delete(self, memory_id: str) -> None:
        await self._vector_store.delete(memory_id)

    async def clear(self) -> None:
        await self._vector_store.clear()


class InMemoryLongTermMemory(LongTermMemoryBase):
    """In-memory long-term memory (for development)."""

    def __init__(self):
        self._delegate = VectorLongTermMemory(HashingEmbeddingProvider(), InMemoryVectorStore())

    async def store(self, content: str, metadata: dict[str, Any] | None = None) -> str:
        return await self._delegate.store(content, metadata)

    async def retrieve(self, query: str, top_k: int = 5) -> list[MemoryItem]:
        return await self._delegate.retrieve(query, top_k)

    async def delete(self, memory_id: str) -> None:
        await self._delegate.delete(memory_id)

    async def clear(self) -> None:
        await self._delegate.clear()


class QdrantLongTermMemory(LongTermMemoryBase):
    """Qdrant-based long-term memory."""

    def __init__(self, url: str = "http://127.0.0.1:6333", collection: str = "swarmmind", dimensions: int = 256):
        self._delegate = VectorLongTermMemory(
            HashingEmbeddingProvider(dimensions=dimensions),
            QdrantVectorStore(url=url, collection=collection, dimensions=dimensions),
        )

    async def store(self, content: str, metadata: dict[str, Any] | None = None) -> str:
        return await self._delegate.store(content, metadata)

    async def retrieve(self, query: str, top_k: int = 5) -> list[MemoryItem]:
        return await self._delegate.retrieve(query, top_k)

    async def delete(self, memory_id: str) -> None:
        await self._delegate.delete(memory_id)

    async def clear(self) -> None:
        await self._delegate.clear()


class ChromaLongTermMemory(LongTermMemoryBase):
    """Chroma-based long-term memory."""

    def __init__(self, persist_directory: str = "./chroma_data", collection: str = "swarmmind"):
        if not CHROMA_AVAILABLE:
            raise ImportError("chromadb is not installed")
        self._client = chromadb.Client(Settings(persist_directory=persist_directory))
        self._collection = collection
        self._ensure_collection()

    def _ensure_collection(self):
        """Ensure collection exists."""
        try:
            self._client.get_collection(self._collection)
        except Exception:
            self._client.create_collection(self._collection)

    async def store(self, content: str, metadata: dict[str, Any] | None = None) -> str:
        """Store a memory item."""
        memory_id = str(uuid.uuid4())
        self._client.add(
            documents=[content],
            metadatas=[metadata or {}],
            ids=[memory_id],
            collection=self._collection,
        )
        return memory_id

    async def retrieve(self, query: str, top_k: int = 5) -> list[MemoryItem]:
        """Retrieve similar memories."""
        results = self._client.query(
            query_texts=[query],
            n_results=top_k,
            collection=self._collection,
        )

        items = []
        if results["ids"] and results["ids"][0]:
            for i, memory_id in enumerate(results["ids"][0]):
                items.append(MemoryItem(
                    id=memory_id,
                    content=results["documents"][0][i] if results["documents"] else "",
                    metadata=results["metadatas"][0][i] if results["metadatas"] else {},
                    score=1.0,  # Chroma doesn't return scores by default
                ))

        return items

    async def delete(self, memory_id: str) -> None:
        """Delete a memory item."""
        self._client.delete(ids=[memory_id], collection=self._collection)

    async def clear(self) -> None:
        """Clear all memories."""
        self._client.delete_collection(self._collection)
        self._ensure_collection()


def create_long_term_memory(
    storage_type: str = "memory",
    **kwargs,
) -> LongTermMemoryBase:
    """Factory function to create long-term memory."""
    if storage_type == "memory":
        return InMemoryLongTermMemory()
    elif storage_type == "qdrant" and QDRANT_AVAILABLE:
        return QdrantLongTermMemory(**kwargs)
    elif storage_type == "chroma" and CHROMA_AVAILABLE:
        return ChromaLongTermMemory(**kwargs)
    else:
        return InMemoryLongTermMemory()


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    numerator = sum(lval * rval for lval, rval in zip(left, right, strict=False))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return numerator / (left_norm * right_norm)


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass
    return datetime.now(UTC)
