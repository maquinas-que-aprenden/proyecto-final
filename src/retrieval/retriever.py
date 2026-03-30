from pathlib import Path
from typing import List, Dict, Any, Optional
import re
import json
import pickle
import threading
from src.observability.langfuse_compat import observe, langfuse_context

# Configuración

DEFAULT_K = 5

CHROMA_DIR = Path(__file__).resolve().parents[2] / "data" / "processed" / "vectorstore" / "chroma"
COLLECTION_NAME = "normabot_legal_chunks"
# Mismo modelo usado en data/index.py para generar los embeddings del vectorstore
EMBED_MODEL_NAME = "intfloat/multilingual-e5-base"

CHUNKS_JSONL = Path(__file__).resolve().parents[2] / "data" / "processed" / "chunks_legal" / "chunks_final_all_sources.jsonl"
BM25_CACHE = Path(__file__).resolve().parents[2] / "data" / "processed" / "vectorstore" / "bm25_index.pkl"

# Pesos RRF para fusión BM25 + semántico
_BM25_WEIGHT = 0.4
_SEMANTIC_WEIGHT = 0.6


# Inicialización Chroma (lazy)

_client = None
_collection = None
_embed_model = None
_lock = threading.Lock()

# Inicialización BM25 (lazy)

_bm25 = None
_bm25_docs = None  # lista de dicts {id, text, metadata}
_bm25_lock = threading.Lock()


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


# Inicialización BM25


def _get_bm25():
    """Inicializa el índice BM25 de forma lazy. Usa caché pickle para evitar reconstruir."""
    global _bm25, _bm25_docs
    if _bm25 is not None:
        return _bm25, _bm25_docs

    with _bm25_lock:
        if _bm25 is not None:
            return _bm25, _bm25_docs

        from rank_bm25 import BM25Okapi

        # Intentar cargar desde caché
        if BM25_CACHE.exists() and CHUNKS_JSONL.exists():
            chunks_mtime = CHUNKS_JSONL.stat().st_mtime
            cache_mtime = BM25_CACHE.stat().st_mtime
            if cache_mtime >= chunks_mtime:
                with BM25_CACHE.open("rb") as f:
                    _bm25, _bm25_docs = pickle.load(f)
                return _bm25, _bm25_docs

        # Construir desde el JSONL
        docs = []
        with CHUNKS_JSONL.open("r", encoding="utf-8") as f:
            for line in f:
                record = json.loads(line)
                docs.append({
                    "id": record["id"],
                    "text": record["text"],
                    "metadata": {k: v for k, v in record.items() if k not in ("id", "text")},
                })

        tokenized = [doc["text"].lower().split() for doc in docs]
        bm25_index = BM25Okapi(tokenized)

        # Guardar caché
        BM25_CACHE.parent.mkdir(parents=True, exist_ok=True)
        with BM25_CACHE.open("wb") as f:
            pickle.dump((bm25_index, docs), f)

        _bm25, _bm25_docs = bm25_index, docs
        return _bm25, _bm25_docs


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


# Búsqueda HYBRID (BM25 + semántico fusionados con RRF)

def _rrf(rankings: List[List[str]], weights: List[float], k: int = 60) -> List[str]:
    """Reciprocal Rank Fusion ponderada sobre varias listas de ids ordenados."""
    scores: Dict[str, float] = {}
    for ranking, weight in zip(rankings, weights):
        for rank, doc_id in enumerate(ranking):
            scores[doc_id] = scores.get(doc_id, 0.0) + weight * (1.0 / (k + rank + 1))
    return sorted(scores, key=lambda x: scores[x], reverse=True)


def search_hybrid(
    query: str,
    k: int = DEFAULT_K,
    filters: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Búsqueda híbrida: BM25 léxico + ChromaDB semántico fusionados con RRF.

    Args:
        filters: dict con pares campo→valor para pre-filtrar en Chroma,
                 ej. {"unit_id": "5"} para buscar solo en el artículo 5.
    """
    fetch_k = k * 2
    bm25_index, bm25_docs = _get_bm25()

    # BM25
    tokenized_query = query.lower().split()
    bm25_scores = bm25_index.get_scores(tokenized_query)
    bm25_top_idx = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)[:fetch_k]
    bm25_ranking = [bm25_docs[i]["id"] for i in bm25_top_idx]

    # ChromaDB semántico (con filtro opcional)
    collection = _get_collection()
    chroma_kwargs: Dict[str, Any] = {
        "query_embeddings": [_embed_query(query)],
        "n_results": fetch_k,
    }
    if filters:
        chroma_kwargs["where"] = {k_: {"$eq": v} for k_, v in filters.items()}

    chroma_results = collection.query(**chroma_kwargs)
    chroma_ranking = chroma_results.get("ids", [[]])[0]

    # Fusión RRF
    fused_ids = _rrf(
        [bm25_ranking, chroma_ranking],
        [_BM25_WEIGHT, _SEMANTIC_WEIGHT],
    )

    # Construir respuesta final desde bm25_docs (lookup por id)
    id_to_doc = {doc["id"]: doc for doc in bm25_docs}
    results = []
    for doc_id in fused_ids[:k]:
        if doc_id in id_to_doc:
            doc = id_to_doc[doc_id]
            results.append({
                "id": doc_id,
                "text": doc["text"],
                "metadata": doc["metadata"],
                "distance": None,  # RRF no produce distancia coseno
            })
    return results


# API principal

@observe(name="retriever.search")
def search(
    query: str,
    mode: str = "soft",
    k: int = DEFAULT_K,
    filters: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    if mode == "hybrid":
        results = search_hybrid(query, k, filters)
    elif mode == "base":
        results = search_base(query, k)
    else:
        results = search_soft(query, k)
    try:
        distances = [r["distance"] for r in results if r["distance"] is not None]
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
