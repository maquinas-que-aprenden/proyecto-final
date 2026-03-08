"""rag/main.py — Pipeline RAG Normativo (Corrective RAG)
Flujo Retrieve → Grade desde ChromaDB. La generación la hace el orchestrator.
"""

from __future__ import annotations

import logging

try:
    from langchain_ollama import ChatOllama
except ImportError:
    ChatOllama = None  # type: ignore[assignment,misc]

from src.observability.langfuse_compat import observe, langfuse_context

from src.retrieval.retriever import search

try:
    from src.finetuning.grader import (
        predict_relevance as _ft_predict,
        is_available as _ft_available,
        LABEL_RELEVANTE as _FT_RELEVANTE,
    )
    _FINETUNED_GRADER_IMPORTED = True
except Exception:  # dependencias no instaladas o módulo no encontrado
    _FINETUNED_GRADER_IMPORTED = False

logger = logging.getLogger(__name__)

MAX_DOC_CHARS_GRADING = 3000

GRADING_PROMPT = (
    "Dado el siguiente documento y la pregunta, "
    "¿el documento contiene información útil para responder la pregunta?\n\n"
    "Documento: {document}\n"
    "Pregunta: {query}\n\n"
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
def retrieve(query: str, k: int = 5) -> list[dict]:
    """Recupera documentos de ChromaDB y los formatea para grade()."""
    try:
        results = search(query, k=k, mode="soft")
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
            "score": max(0.0, 1.0 - r.get("distance", 1.0)),
        }
        for r in results
    ]
    try:
        langfuse_context.update_current_observation(
            metadata={"k": k, "n_docs_retrieved": len(docs)},
        )
    except Exception:
        pass
    return docs


def _grade_by_score(docs: list[dict], threshold: float = 0.3) -> list[dict]:
    """Fallback: filtra documentos por score de similitud."""
    return [d for d in docs if d["score"] >= threshold]


def _grade_with_finetuned(query: str, docs: list[dict], threshold: float) -> list[dict]:
    """Grading con el modelo fine-tuneado (QLoRA). Fallback por doc a score."""
    relevant = []
    for doc in docs:
        try:
            label = _ft_predict(query=query, document=doc["doc"])
            if label == _FT_RELEVANTE:
                relevant.append(doc)
        except Exception:
            logger.warning("Error en grading fine-tuneado, usando score como fallback para este doc")
            if doc["score"] >= threshold:
                relevant.append(doc)
    return relevant


def _grade_with_ollama(query: str, docs: list[dict], threshold: float) -> list[dict]:
    """Grading con Ollama (Qwen 2.5 3B base). Fallback por doc a score."""
    llm = _get_grading_llm()
    relevant = []
    for doc in docs:
        doc_text = doc["doc"][:MAX_DOC_CHARS_GRADING]
        prompt = GRADING_PROMPT.format(document=doc_text, query=query)
        try:
            response = llm.invoke(prompt)
            answer = response.content.strip().lower()
            answer_first = answer.split()[0] if answer.split() else ""
            if answer_first in ("si", "sí"):
                relevant.append(doc)
        except Exception:
            logger.warning("Error en grading Ollama, incluyendo doc por score")
            if doc["score"] >= threshold:
                relevant.append(doc)
    return relevant


@observe(name="rag.grade")
def grade(query: str, docs: list[dict], threshold: float = 0.3) -> list[dict]:
    """Evalúa relevancia de cada documento con LLM local.

    Jerarquía de métodos:
    1. Modelo fine-tuneado (QLoRA, F1=0.895) — si el adaptador está disponible.
    2. Ollama Qwen 2.5 3B base              — si Ollama está corriendo.
    3. Filtro por score de similitud        — fallback sin LLM.
    """
    if not docs:
        return []

    # 1. Modelo fine-tuneado
    if _FINETUNED_GRADER_IMPORTED and _ft_available():
        try:
            relevant = _grade_with_finetuned(query, docs, threshold)
            try:
                langfuse_context.update_current_observation(
                    metadata={"n_docs_in": len(docs), "n_relevant": len(relevant), "method": "finetuned_lora"},
                )
            except Exception:
                pass
            return relevant
        except Exception:
            logger.warning("Grader fine-tuneado falló, degradando a Ollama")

    # 2. Ollama (modelo base)
    try:
        relevant = _grade_with_ollama(query, docs, threshold)
        try:
            langfuse_context.update_current_observation(
                metadata={"n_docs_in": len(docs), "n_relevant": len(relevant), "method": "ollama"},
            )
        except Exception:
            pass
        return relevant
    except Exception:
        logger.warning("Ollama no disponible, usando fallback por score")

    # 3. Fallback por score
    relevant = _grade_by_score(docs, threshold)
    try:
        langfuse_context.update_current_observation(
            level="WARNING",
            status_message="Sin LLM disponible — grading por score (degradación máxima)",
            metadata={"n_docs_in": len(docs), "n_relevant": len(relevant), "method": "score_fallback"},
        )
    except Exception:
        pass
    return relevant


def format_context(docs: list[dict]) -> str:
    """Formatea los documentos relevantes como contexto para el orchestrator."""
    blocks = []
    for i, d in enumerate(docs, 1):
        meta = d.get("metadata", {})
        source = meta.get("source", "")
        unit = meta.get("unit_title") or meta.get("unit_id", "")
        header = f"[{i}] {source} — {unit}".strip(" —")
        blocks.append(f"{header}\n{d['doc']}")
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
