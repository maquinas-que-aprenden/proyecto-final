from pathlib import Path
from typing import List, Dict, Any, Optional
import threading
import chromadb
from langfuse.decorators import observe, langfuse_context

# Configuración

DEFAULT_K = 5

CHROMA_DIR = Path(__file__).resolve().parents[2] / "data" / "processed" / "vectorstore" / "chroma"
COLLECTION_NAME = "normabot_legal_chunks"
# Mismo modelo usado en data/index.py para generar los embeddings del vectorstore
EMBED_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


# Inicialización Chroma (lazy)

_client = None
_collection = None
_embed_model = None
_lock = threading.Lock()


def _get_collection():
    """Inicializa el cliente ChromaDB y obtiene la colección de forma lazy."""
    global _client, _collection
    if _collection is None:
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
    return _get_embed_model().encode(query).tolist()


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
    collection = _get_collection()
    results = collection.query(
        query_embeddings=[_embed_query(query)],
        n_results=k
    )

    return _format_results(results)


# Búsqueda SOFT (prioridad suave)

def search_soft(query: str, k: int = DEFAULT_K) -> List[Dict[str, Any]]:
    priority_sources = _detect_priority_sources(query)

    collection = _get_collection()
    results = collection.query(
        query_embeddings=[_embed_query(query)],
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



    # --- Tool output for Agents / LangGraph ---
@observe(name="retriever.search_tool")
def search_tool(query: str, k: int = DEFAULT_K, mode: str = "soft", max_chars: int = 3500) -> str:
    """
    Devuelve contexto listo para LLM (string), basado en la búsqueda del vectorstore.
    - No cambia la API 'search()' (que devuelve hits crudos).
    - Este wrapper es para agentes: texto limpio + fuentes.
    """
    hits = search(query=query, mode=mode, k=k)

    if not hits:
        return "NO_RESULTS"

    blocks = []
    sources = []

    for i, h in enumerate(hits, start=1):
        meta = h.get("metadata", {}) or {}
        src = meta.get("source", "unknown")
        file = meta.get("file", "unknown")
        unit = meta.get("unit_title") or meta.get("unit_id") or meta.get("unit_type") or ""

        sources.append(f"{src}:{file}:{unit}".strip(":"))

        text = (h.get("text") or "").strip()
        if not text:
            continue

        blocks.append(f"[{i}] source={src} file={file}\n{text}")

    out = "CONTEXT:\n" + "\n\n".join(blocks)
    out += "\n\nSOURCES:\n" + "\n".join(sorted(set(sources)))

    truncated = len(out) > max_chars
    # Recorte por seguridad
    if truncated:
        out = out[:max_chars] + "\n\n[TRUNCATED]"

    try:
        langfuse_context.update_current_observation(
            metadata={
                "n_hits": len(hits),
                "n_blocks": len(blocks),
                "n_sources": len(set(sources)),
                "output_chars": len(out),
                "truncated": truncated,
            }
        )
    except Exception:
        pass

    return out
