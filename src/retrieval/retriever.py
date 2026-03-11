from pathlib import Path
from typing import List, Dict, Any, Optional
import re
import threading
from src.observability.langfuse_compat import observe, langfuse_context

# Configuración

DEFAULT_K = 5

CHROMA_DIR = Path(__file__).resolve().parents[2] / "data" / "processed" / "vectorstore" / "chroma"
COLLECTION_NAME = "normabot_legal_chunks"
# Mismo modelo usado en data/index.py para generar los embeddings del vectorstore
EMBED_MODEL_NAME = "intfloat/multilingual-e5-base"


# Inicialización Chroma (lazy)

_client = None
_collection = None
_embed_model = None
_lock = threading.Lock()


def _get_collection():
    """Inicializa el cliente ChromaDB y obtiene la colección de forma lazy."""
    global _client, _collection
    if _collection is None:
        import chromadb
        _client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        _collection = _client.get_collection(COLLECTION_NAME)
    return _collection


def _get_embed_model():
    """Singleton del modelo de embeddings (mismo que en data/index.py), thread-safe."""
    global _embed_model
    if _embed_model is None:
        with _lock:
            if _embed_model is None:
                from sentence_transformers import SentenceTransformer
                _embed_model = SentenceTransformer(EMBED_MODEL_NAME)
    return _embed_model


def _embed_query(query: str) -> list:
    """Genera el embedding de la query con el mismo modelo usado en indexación."""
    return _get_embed_model().encode(f"query: {query}").tolist()


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


def _detect_article_number(query: str) -> Optional[str]:
    """Detecta si la query menciona un artículo específico por número.

    Soporta: "artículo 5", "articulo 5", "art. 5", "art 5".
    """
    m = re.search(r'\bart(?:[íi]culo|\.?)\s+(\d+)\b', query, flags=re.IGNORECASE)
    if m:
        return m.group(1)
    return None


def _detect_annex_reference(query: str) -> Optional[str]:
    """Detecta si la query menciona un anexo específico (ej: 'Anexo III')."""
    m = re.search(r'\banexo\s+([IVXLC]+|\d+)\b', query, flags=re.IGNORECASE)
    if m:
        return m.group(1).upper()
    return None


def _detect_priority_sources(query: str) -> Optional[List[str]]:
    query_lower = query.lower()

    priority_sources = []

    if "rgpd" in query_lower or "lopd" in query_lower:
        priority_sources.append("lopd_rgpd")

    if "aesia" in query_lower:
        priority_sources.append("aesia")

    if "ai act" in query_lower or "alto riesgo" in query_lower:
        priority_sources.append("eu_ai_act")

    if "boe" in query_lower or "ley orgánica" in query_lower or "ley organica" in query_lower or "derechos digitales" in query_lower:
        priority_sources.append("boe")

    return priority_sources if priority_sources else None


# Búsqueda BASE

def search_base(query: str, k: int = DEFAULT_K) -> List[Dict[str, Any]]:
    collection = _get_collection()
    results = collection.query(
        query_embeddings=[_embed_query(query)],
        n_results=k
    )

    return _format_results(results)


# Búsqueda SOFT (prioridad suave)

def search_soft(query: str, k: int = DEFAULT_K) -> List[Dict[str, Any]]:
    priority_sources = _detect_priority_sources(query)
    article_num = _detect_article_number(query)
    annex_ref = _detect_annex_reference(query)

    collection = _get_collection()
    results = collection.query(
        query_embeddings=[_embed_query(query)],
        n_results=k * 2
    )

    formatted = _format_results(results)

    if not priority_sources and not article_num and not annex_ref:
        return formatted[:k]

    exact_hits = []
    source_hits = []
    other_hits = []

    for hit in formatted:
        meta = hit.get("metadata", {})
        unit_id = str(meta.get("unit_id", ""))
        unit_title = str(meta.get("unit_title", ""))
        source = meta.get("source", "")

        if article_num and unit_id == article_num:
            exact_hits.append(hit)
        elif annex_ref and annex_ref in unit_title.upper():
            exact_hits.append(hit)
        elif priority_sources and source in priority_sources:
            source_hits.append(hit)
        else:
            other_hits.append(hit)

    return (exact_hits + source_hits + other_hits)[:k]


# API principal

@observe(name="retriever.search")
def search(query: str, mode: str = "soft", k: int = DEFAULT_K) -> List[Dict[str, Any]]:
    if mode == "base":
        results = search_base(query, k)
    else:
        results = search_soft(query, k)
    try:
        distances = [r["distance"] for r in results]
        langfuse_context.update_current_observation(
            metadata={
                "mode": mode,
                "k": k,
                "n_results": len(results),
                "min_distance": round(min(distances), 4) if distances else None,
                "max_distance": round(max(distances), 4) if distances else None,
            }
        )
    except Exception:
        pass
    return results
