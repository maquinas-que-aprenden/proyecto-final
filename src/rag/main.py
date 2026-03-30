"""rag/main.py — Pipeline RAG Normativo (Corrective RAG)
Flujo Retrieve → Grade desde ChromaDB. La generación la hace el orchestrator.
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

try:
    from langchain_ollama import ChatOllama
except ImportError:
    ChatOllama = None  # type: ignore[assignment,misc]

from src.observability.langfuse_compat import observe, langfuse_context

from src.retrieval.retriever import search

logger = logging.getLogger(__name__)

PARENTS_JSONL = Path(__file__).resolve().parents[2] / "data" / "processed" / "chunks_legal" / "chunks_padres.jsonl"

_parents: dict[str, str] | None = None
_parents_lock = threading.Lock()


def _load_parents() -> dict[str, str]:
    """Carga chunks_padres.jsonl en dict {parent_id: texto_padre} de forma lazy."""
    global _parents
    if _parents is not None:
        return _parents
    with _parents_lock:
        if _parents is not None:
            return _parents
        result: dict[str, str] = {}
        if PARENTS_JSONL.exists():
            with PARENTS_JSONL.open("r", encoding="utf-8") as f:
                for line in f:
                    rec = json.loads(line)
                    result[rec["parent_id"]] = rec["text"]
        _parents = result
    return _parents

MAX_DOC_CHARS_GRADING = 3000

GRADING_PROMPT = (
    "Dado el siguiente documento y la pregunta, "
    "¿el documento contiene información parcial o totalmente útil para responder la pregunta?\n\n"
    "Sé permisivo: responde 'si' si el documento toca el tema aunque no lo responda completamente.\n"
    "Solo responde 'no' si el documento es completamente irrelevante.\n\n"
    "Documento: {document}\n"
    "Pregunta: {query}\n\n"
    "IMPORTANTE: Responde únicamente con 'si' o 'no'. No añadas explicaciones ni te inventes información.\n"
    'Responde solo con "si" o "no":'
)

_grading_llm = None


def _get_grading_llm():
    """Devuelve el LLM local para grading (Qwen 2.5 3B via Ollama)."""
    if ChatOllama is None:
        raise ImportError("langchain_ollama no instalado. Ejecuta: pip install langchain-ollama")
    global _grading_llm
    if _grading_llm is None:
        _grading_llm = ChatOllama(
            model="qwen2.5:3b",
            temperature=0,
            num_predict=10,
            num_ctx=4096,
        )
    return _grading_llm


@observe(name="rag.retrieve")
def retrieve(
    query: str,
    k: int = 9,
    mode: str = "soft",
    filters: dict | None = None,
) -> list[dict]:
    """Recupera documentos de ChromaDB y los formatea para grade().

    Args:
        mode: "soft" (default), "base" o "hybrid" (BM25 + semántico + RRF).
        filters: filtros de metadata para pre-filtrar en Chroma, ej. {"unit_id": "5"}.
                 Solo aplicable en mode="hybrid".
    """
    try:
        results = search(query, k=k, mode=mode, filters=filters)
    except Exception:
        logger.exception("Error al buscar en ChromaDB")
        try:
            langfuse_context.update_current_observation(
                level="ERROR",
                status_message="ChromaDB no disponible — retrieve devuelve vacío",
                metadata={"error": "ChromaDB unavailable", "k": k},
            )
        except Exception:
            pass
        return []

    docs = [
        {
            "doc": r["text"],
            "metadata": r.get("metadata", {}),
            # hybrid no devuelve distancia coseno; score=1.0 para no penalizar
            "score": max(0.0, 1.0 - r["distance"]) if r.get("distance") is not None else 1.0,
        }
        for r in results
    ]
    try:
        langfuse_context.update_current_observation(
            metadata={"k": k, "mode": mode, "n_docs_retrieved": len(docs)},
        )
    except Exception:
        pass
    return docs


def _grade_by_score(docs: list[dict], threshold: float = 0.3) -> list[dict]:
    """Fallback: filtra documentos por score de similitud."""
    return [d for d in docs if d["score"] >= threshold]


@observe(name="rag.grade")
def grade(query: str, docs: list[dict], threshold: float = 0.3) -> list[dict]:
    """Evalúa relevancia de cada documento con LLM local (Ollama).

    Fallback a filtro por score si Ollama no está disponible.
    """
    if not docs:
        return []

    try:
        llm = _get_grading_llm()
    except Exception:
        logger.warning("Ollama no disponible, usando fallback por score")
        relevant = _grade_by_score(docs, threshold)
        try:
            langfuse_context.update_current_observation(
                level="WARNING",
                status_message="Ollama no disponible — grading por score (degradación)",
                metadata={"n_docs_in": len(docs), "n_relevant": len(relevant), "method": "score_fallback"},
            )
        except Exception:
            pass
        return relevant

    relevant = []
    for doc in docs:
        doc_text = doc["doc"][:MAX_DOC_CHARS_GRADING]
        prompt = GRADING_PROMPT.format(document=doc_text, query=query)
        try:
            response = llm.invoke(prompt)
            answer = response.content.strip().lower()
            if answer.startswith("si") or answer.startswith("sí"):
                relevant.append(doc)
        except Exception:
            logger.warning("Error en grading LLM, incluyendo doc por score")
            if doc["score"] >= threshold:
                relevant.append(doc)

    # Garantía mínima: si el grader descartó todo, usar filtro por score
    # Solo pasa docs que superen el umbral de similitud, evita pasar basura al generador
    if not relevant:
        relevant = _grade_by_score(docs, threshold)
        logger.warning("Grader devolvió 0 relevantes — fallback a filtro por score")
        try:
            langfuse_context.update_current_observation(
                level="WARNING",
                status_message="Grader devolvió 0 relevantes — fallback a filtro por score",
                metadata={"n_docs_in": len(docs), "n_relevant": len(relevant), "method": "empty_fallback"},
            )
        except Exception:
            pass

    try:
        langfuse_context.update_current_observation(
            metadata={"n_docs_in": len(docs), "n_relevant": len(relevant), "method": "llm"},
        )
    except Exception:
        pass
    return relevant


def format_context(docs: list[dict]) -> str:
    """Formatea los documentos relevantes como contexto para el orchestrator.

    Para chunks hijos, incluye el texto completo del artículo padre como contexto
    ampliado, seguido del fragmento preciso recuperado.
    """
    parents = _load_parents()
    blocks = []
    for i, d in enumerate(docs, 1):
        meta = d.get("metadata", {})
        source = meta.get("source", "")
        unit = meta.get("unit_title") or meta.get("unit_id", "")
        header = f"[{i}] {source} — {unit}".strip(" —")

        tipo_nodo = meta.get("tipo_nodo", "single")
        parent_id = meta.get("parent_id") or ""

        if tipo_nodo == "hijo" and parent_id and parent_id in parents:
            parent_text = parents[parent_id]
            block = (
                f"{header}\n"
                f"[Contexto completo del artículo]\n{parent_text}\n\n"
                f"[Fragmento relevante]\n{d['doc']}"
            )
        else:
            block = f"{header}\n{d['doc']}"

        blocks.append(block)
    return "\n\n".join(blocks)


if __name__ == "__main__":
    query = "¿Qué prácticas de IA están prohibidas?"
    print(f"Query: {query}\n")

    docs = retrieve(query)
    print(f"Retrieve:  {len(docs)} docs encontrados")

    relevant = grade(query, docs)
    print(f"Grade:     {len(relevant)} relevantes")

    print(f"Context:\n{format_context(relevant)}")

    print("\n✓ rag/main.py OK")
