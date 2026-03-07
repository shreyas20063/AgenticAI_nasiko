"""
Vector Store Tool - ChromaDB-backed semantic search
for HR policies, FAQs, and knowledge base.
"""

from typing import Optional
from tools.base_tool import BaseTool, ToolResult
from config import get_settings
import structlog

logger = structlog.get_logger()
settings = get_settings()

# Lazy-loaded ChromaDB client
_chroma_client = None
_collection = None


def _get_collection():
    """Lazy init ChromaDB collection."""
    global _chroma_client, _collection
    if _collection is None:
        import chromadb
        _chroma_client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
        _collection = _chroma_client.get_or_create_collection(
            name=settings.chroma_collection_name,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


class VectorStoreTool(BaseTool):
    name = "search_policies"
    description = "Search HR policy documents and knowledge base using semantic search"

    async def execute(self, parameters: dict, context: dict) -> ToolResult:
        query = parameters.get("query", "")
        n_results = parameters.get("n_results", 5)
        category = parameters.get("category")
        tenant_id = context.get("tenant_id")

        if not query:
            return ToolResult(success=False, error="Query is required", tool_name=self.name)

        try:
            collection = _get_collection()

            # Build filter for tenant isolation
            where_filter = {"tenant_id": tenant_id} if tenant_id else None
            if category:
                if where_filter:
                    where_filter = {"$and": [
                        {"tenant_id": tenant_id},
                        {"category": category},
                    ]}
                else:
                    where_filter = {"category": category}

            results = collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where_filter,
                include=["documents", "metadatas", "distances"],
            )

            documents = []
            if results and results["documents"]:
                for i, doc in enumerate(results["documents"][0]):
                    meta = results["metadatas"][0][i] if results["metadatas"] else {}
                    distance = results["distances"][0][i] if results["distances"] else None
                    documents.append({
                        "content": doc,
                        "metadata": meta,
                        "relevance_score": round(1 - (distance or 0), 3),
                    })

            return ToolResult(
                success=True,
                data={
                    "query": query,
                    "results": documents,
                    "count": len(documents),
                },
                tool_name=self.name,
            )

        except Exception as e:
            logger.error("vector_search_failed", error=str(e))
            return ToolResult(
                success=False,
                error=f"Search failed: {str(e)}",
                tool_name=self.name,
            )

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query text"},
                    "n_results": {"type": "integer", "default": 5, "description": "Number of results to return"},
                    "category": {"type": "string", "description": "Filter by document category"},
                },
                "required": ["query"],
            },
        }


async def index_document(
    tenant_id: str,
    doc_id: str,
    content: str,
    metadata: dict = None,
    chunk_size: int = 500,
) -> int:
    """
    Index a document into the vector store with chunking.
    Returns number of chunks indexed.
    """
    collection = _get_collection()

    # Simple chunking by paragraphs/sentences
    chunks = []
    paragraphs = content.split("\n\n")
    current_chunk = ""

    for para in paragraphs:
        if len(current_chunk) + len(para) > chunk_size and current_chunk:
            chunks.append(current_chunk.strip())
            current_chunk = para
        else:
            current_chunk += "\n\n" + para if current_chunk else para

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    # Index chunks with metadata
    ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]
    metadatas = [
        {
            "tenant_id": tenant_id,
            "doc_id": doc_id,
            "chunk_index": i,
            **(metadata or {}),
        }
        for i in range(len(chunks))
    ]

    collection.upsert(
        ids=ids,
        documents=chunks,
        metadatas=metadatas,
    )

    logger.info("document_indexed", doc_id=doc_id, chunks=len(chunks), tenant_id=tenant_id)
    return len(chunks)
