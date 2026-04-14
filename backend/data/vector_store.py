"""
PolPilot — Wrapper de ChromaDB para búsqueda vectorial.

Collections por empresa:
  - internal_docs:        embeddings de documentos y datos internos
  - external_research:    embeddings de créditos, regulaciones, señales
  - conversation_context: embeddings de resúmenes y mensajes clave

ChromaDB usa su propio modelo de embeddings por defecto
(all-MiniLM-L6-v2) — suficiente para la hackathon.
"""

import chromadb
from pathlib import Path

DATA_ROOT = Path(__file__).resolve().parent.parent.parent / "data"

COLLECTIONS = [
    "internal_docs",
    "external_research",
    "conversation_context",
]


class VectorStore:
    """Wrapper de ChromaDB para una empresa específica."""

    def __init__(self, empresa_id: str):
        self.empresa_id = empresa_id
        self.path = DATA_ROOT / empresa_id / "vectors"
        self.path.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(self.path))
        self._collections: dict[str, chromadb.Collection] = {}

    def _get_collection(self, name: str) -> chromadb.Collection:
        if name not in self._collections:
            self._collections[name] = self.client.get_or_create_collection(
                name=name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collections[name]

    # ------------------------------------------------------------------
    # Escritura
    # ------------------------------------------------------------------

    def add_documents(
        self,
        collection_name: str,
        documents: list[str],
        metadatas: list[dict],
        ids: list[str],
    ) -> None:
        """Agrega documentos a una collection. ChromaDB genera embeddings automáticamente."""
        col = self._get_collection(collection_name)
        col.add(documents=documents, metadatas=metadatas, ids=ids)

    def upsert_documents(
        self,
        collection_name: str,
        documents: list[str],
        metadatas: list[dict],
        ids: list[str],
    ) -> None:
        """Upsert: actualiza si el id existe, inserta si no."""
        col = self._get_collection(collection_name)
        col.upsert(documents=documents, metadatas=metadatas, ids=ids)

    # ------------------------------------------------------------------
    # Lectura
    # ------------------------------------------------------------------

    def search(
        self,
        collection_name: str,
        query_text: str,
        n_results: int = 5,
        where: dict | None = None,
    ) -> dict:
        """Búsqueda semántica por texto. Retorna docs + distancias + metadatas."""
        col = self._get_collection(collection_name)
        kwargs: dict = {
            "query_texts": [query_text],
            "n_results": n_results,
        }
        if where:
            kwargs["where"] = where
        return col.query(**kwargs)

    def count(self, collection_name: str) -> int:
        """Cantidad de documentos en una collection."""
        return self._get_collection(collection_name).count()

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------

    def init_collections(self) -> None:
        """Inicializa las 3 collections (idempotente)."""
        for name in COLLECTIONS:
            self._get_collection(name)

    def list_collections(self) -> list[str]:
        return [c.name for c in self.client.list_collections()]
