from pathlib import Path
from typing import List, Dict, Any, Optional
import chromadb

# Configuración

DEFAULT_K = 5

CHROMA_DIR = Path(__file__).resolve().parents[2] / "processed" / "vectorstore" / "chroma"
COLLECTION_NAME = "normabot_legal_chunks"


# Inicialización Chroma

_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
_collection = _client.get_collection(COLLECTION_NAME)


# Funciones internas

def _format_results(results: Dict[str, Any]) -> List[Dict[str, Any]]:
    ids = results.get("ids", [[]])[0]
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    formatted = []

    for i in range(len(ids)):
        formatted.append({
            "id": ids[i],
            "text": docs[i],
            "metadata": metas[i],
            "distance": distances[i],
        })

    return formatted


def _detect_priority_sources(query: str) -> Optional[List[str]]:
    query_lower = query.lower()

    priority_sources = []

    if "rgpd" in query_lower or "lopd" in query_lower:
        priority_sources.append("RGPD")

    if "aesia" in query_lower:
        priority_sources.append("AESIA")

    if "ai act" in query_lower or "alto riesgo" in query_lower:
        priority_sources.append("EU_AI_ACT")

    return priority_sources if priority_sources else None


# Búsqueda BASE

def search_base(query: str, k: int = DEFAULT_K) -> List[Dict[str, Any]]:
    results = _collection.query(
        query_texts=[query],
        n_results=k
    )

    return _format_results(results)


# Búsqueda SOFT (prioridad suave)

def search_soft(query: str, k: int = DEFAULT_K) -> List[Dict[str, Any]]:
    priority_sources = _detect_priority_sources(query)

    results = _collection.query(
        query_texts=[query],
        n_results=k * 2
    )

    formatted = _format_results(results)

    if not priority_sources:
        return formatted[:k]

    priority_hits = []
    other_hits = []

    for hit in formatted:
        source = hit.get("metadata", {}).get("source", "")

        if source in priority_sources:
            priority_hits.append(hit)
        else:
            other_hits.append(hit)

    ordered = priority_hits + other_hits

    return ordered[:k]


# API principal

def search(query: str, mode: str = "soft", k: int = DEFAULT_K) -> List[Dict[str, Any]]:
    if mode == "base":
        return search_base(query, k)
    return search_soft(query, k)