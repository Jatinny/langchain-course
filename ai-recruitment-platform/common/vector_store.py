"""Vector store client for semantic search using Pinecone."""
import logging
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from pinecone import Pinecone, ServerlessSpec

from common.config import settings
from common.llm import embed_text, embed_batch

logger = logging.getLogger(__name__)


class VectorStoreClient:
    """Pinecone vector store client for semantic search."""

    NAMESPACES = {
        "candidates": "candidate-profiles",
        "jobs": "job-descriptions",
        "employers": "employer-descriptions",
        "templates": "email-templates",
    }

    def __init__(self) -> None:
        self._pc: Optional[Pinecone] = None
        self._index = None

    def _get_client(self) -> Pinecone:
        if self._pc is None:
            self._pc = Pinecone(api_key=settings.pinecone_api_key)
        return self._pc

    def _get_index(self):
        if self._index is None:
            pc = self._get_client()
            existing = pc.list_indexes().names()
            if settings.pinecone_index_name not in existing:
                pc.create_index(
                    name=settings.pinecone_index_name,
                    dimension=settings.embedding_dimensions,
                    metric="cosine",
                    spec=ServerlessSpec(
                        cloud="aws",
                        region=settings.pinecone_environment,
                    ),
                )
                logger.info("Created Pinecone index", index=settings.pinecone_index_name)
            self._index = pc.Index(settings.pinecone_index_name)
        return self._index

    async def upsert(
        self,
        document_id: str,
        text: str,
        namespace: str = "candidates",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Embed text and upsert to vector store."""
        vector = await embed_text(text)
        index = self._get_index()
        index.upsert(
            vectors=[{
                "id": document_id,
                "values": vector,
                "metadata": metadata or {},
            }],
            namespace=self.NAMESPACES.get(namespace, namespace),
        )
        return document_id

    async def upsert_batch(
        self,
        documents: List[Dict[str, Any]],
        namespace: str = "candidates",
    ) -> List[str]:
        """Batch upsert documents."""
        texts = [doc["text"] for doc in documents]
        vectors = await embed_batch(texts)
        index = self._get_index()

        batch = [
            {
                "id": doc.get("id", str(uuid4())),
                "values": vec,
                "metadata": doc.get("metadata", {}),
            }
            for doc, vec in zip(documents, vectors)
        ]
        index.upsert(
            vectors=batch,
            namespace=self.NAMESPACES.get(namespace, namespace),
        )
        return [item["id"] for item in batch]

    async def search(
        self,
        query_text: str,
        namespace: str = "candidates",
        top_k: int = 10,
        filter_dict: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[str, float, Dict[str, Any]]]:
        """Search for similar documents."""
        query_vector = await embed_text(query_text)
        index = self._get_index()

        results = index.query(
            vector=query_vector,
            top_k=top_k,
            namespace=self.NAMESPACES.get(namespace, namespace),
            filter=filter_dict,
            include_metadata=True,
        )

        return [
            (match["id"], match["score"], match.get("metadata", {}))
            for match in results["matches"]
        ]

    async def delete(self, document_id: str, namespace: str = "candidates") -> None:
        """Delete a document from the vector store."""
        index = self._get_index()
        index.delete(
            ids=[document_id],
            namespace=self.NAMESPACES.get(namespace, namespace),
        )


# Singleton
vector_store = VectorStoreClient()
