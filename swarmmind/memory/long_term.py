"""Long-term memory using vector database for semantic search."""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# Try to import vector DB clients, fall back to simple implementation
try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams, PointStruct
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
    created_at: datetime = field(default_factory=datetime.utcnow)
    score: float = 0.0


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


class InMemoryLongTermMemory(LongTermMemoryBase):
    """In-memory long-term memory (for development)."""

    def __init__(self):
        self._memories: dict[str, MemoryItem] = {}

    async def store(self, content: str, metadata: dict[str, Any] | None = None) -> str:
        """Store a memory item."""
        memory_id = str(uuid.uuid4())
        item = MemoryItem(
            id=memory_id,
            content=content,
            metadata=metadata or {},
        )
        self._memories[memory_id] = item
        return memory_id

    async def retrieve(self, query: str, top_k: int = 5) -> list[MemoryItem]:
        """Retrieve similar memories (simple keyword matching)."""
        query_lower = query.lower()
        results = []

        for item in self._memories.values():
            # Simple scoring based on keyword overlap
            query_words = set(query_lower.split())
            content_words = set(item.content.lower().split())
            score = len(query_words & content_words) / max(len(query_words), 1)

            if score > 0:
                item.score = score
                results.append(item)

        # Sort by score and return top_k
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]

    async def delete(self, memory_id: str) -> None:
        """Delete a memory item."""
        self._memories.pop(memory_id, None)

    async def clear(self) -> None:
        """Clear all memories."""
        self._memories.clear()


class QdrantLongTermMemory(LongTermMemoryBase):
    """Qdrant-based long-term memory."""

    def __init__(self, host: str = "localhost", port: int = 6333, collection: str = "swarmmind"):
        if not QDRANT_AVAILABLE:
            raise ImportError("qdrant-client is not installed")
        self._client = QdrantClient(host=host, port=port)
        self._collection = collection
        self._ensure_collection()

    def _ensure_collection(self):
        """Ensure collection exists."""
        collections = self._client.get_collections().collections
        if not any(c.name == self._collection for c in collections):
            self._client.create_collection(
                collection_name=self._collection,
                vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
            )

    async def store(self, content: str, metadata: dict[str, Any] | None = None) -> str:
        """Store a memory item."""
        memory_id = str(uuid.uuid4())

        # Note: In production, generate embedding using an embedding model
        # For now, use a placeholder
        import numpy as np
        vector = np.random.rand(1536).tolist()

        self._client.upsert(
            collection_name=self._collection,
            points=[
                PointStruct(
                    id=memory_id,
                    vector=vector,
                    payload={
                        "content": content,
                        "metadata": metadata or {},
                        "created_at": datetime.utcnow().isoformat(),
                    },
                )
            ],
        )
        return memory_id

    async def retrieve(self, query: str, top_k: int = 5) -> list[MemoryItem]:
        """Retrieve similar memories."""
        import numpy as np
        query_vector = np.random.rand(1536).tolist()  # Placeholder

        results = self._client.search(
            collection_name=self._collection,
            query_vector=query_vector,
            limit=top_k,
        )

        return [
            MemoryItem(
                id=r.id,
                content=r.payload.get("content", ""),
                metadata=r.payload.get("metadata", {}),
                score=r.score,
            )
            for r in results
        ]

    async def delete(self, memory_id: str) -> None:
        """Delete a memory item."""
        self._client.delete(
            collection_name=self._collection,
            points_selector=[memory_id],
        )

    async def clear(self) -> None:
        """Clear all memories."""
        self._client.delete_collection(self._collection)
        self._ensure_collection()


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
