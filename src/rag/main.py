"""rag/main.py — Agente RAG Normativo (Corrective RAG)
Flujo Retrieve → Grade → Generate con citas legales desde ChromaDB.
"""

from __future__ import annotations

import logging
import os

try:
    from langchain_ollama import ChatOllama
except ImportError:
    ChatOllama = None  # type: ignore[assignment,misc]
try:
    from langchain_aws import ChatBedrockConverse as _ChatBedrockConverse
except ImportError:
    _ChatBedrockConverse = None  # type: ignore[assignment,misc]

from src.observability.langfuse_compat import observe, langfuse_context

from src.retrieval.retriever import search

logger = logging.getLogger(__name__)

MAX_DOC_CHARS_GRADING = 3000

BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "eu.amazon.nova-lite-v1:0")
BEDROCK_REGION = os.environ.get("BEDROCK_REGION") or os.environ.get("AWS_REGION", "eu-west-1")

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


def _grade_by_score(docs: list[dict], threshold: float = 0.7) -> list[dict]:
    """Fallback: filtra documentos por score de similitud."""
    return [d for d in docs if d["score"] >= threshold]


@observe(name="rag.grade")
def grade(query: str, docs: list[dict], threshold: float = 0.7) -> list[dict]:
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

    try:
        langfuse_context.update_current_observation(
            metadata={"n_docs_in": len(docs), "n_relevant": len(relevant), "method": "llm"},
        )
    except Exception:
        pass
    return relevant


GENERATE_PROMPT = """\
Eres un asistente juridico especializado en el EU AI Act y normativa española de IA.
Responde la pregunta usando SOLO la informacion de los documentos proporcionados.
Cita siempre la ley y articulo exactos. Si no hay informacion suficiente, dilo.
No inventes articulos ni citas que no aparezcan en los documentos.

Documentos:
{context}

Pregunta: {query}

Responde de forma clara y estructurada. Cita las fuentes al final."""

_generate_llm = None


def _get_generate_llm():
    """Devuelve el LLM para generacion (Bedrock Nova Lite, singleton)."""
    if _ChatBedrockConverse is None:
        raise ImportError("langchain_aws no instalado. Ejecuta: pip install langchain-aws")
    global _generate_llm
    if _generate_llm is None:
        _generate_llm = _ChatBedrockConverse(
            model=BEDROCK_MODEL_ID,
            region_name=BEDROCK_REGION,
            temperature=0.1,
            max_tokens=1024,
        )
    return _generate_llm


def _format_context(docs: list[dict]) -> str:
    """Formatea los documentos recuperados como contexto para el prompt."""
    blocks = []
    for i, d in enumerate(docs, 1):
        meta = d.get("metadata", {})
        source = meta.get("source", "")
        unit = meta.get("unit_title") or meta.get("unit_id", "")
        header = f"[{i}] {source} — {unit}".strip(" —")
        blocks.append(f"{header}\n{d['doc']}")
    return "\n\n".join(blocks)


@observe(name="rag.generate")
def generate(query: str, context: list[dict]) -> dict:
    """Genera una respuesta con citas legales usando Bedrock Nova Lite."""
    sources = [d.get("metadata", {}) for d in context]

    if not context:
        langfuse_context.update_current_observation(
            metadata={"n_context_docs": 0},
        )
        return {
            "answer": "No se encontraron documentos relevantes para esta consulta.",
            "sources": [],
        }

    formatted_context = _format_context(context)
    prompt = GENERATE_PROMPT.format(context=formatted_context, query=query)

    llm = _get_generate_llm()
    response = llm.invoke(prompt)
    answer = response.content.strip()
    answer += "\n\n_Informe preliminar generado por IA. Consulte profesional jurídico._"

    try:
        langfuse_context.update_current_observation(
            metadata={"n_context_docs": len(context)},
        )
    except Exception:
        pass
    return {
        "answer": answer,
        "sources": sources,
    }


if __name__ == "__main__":
    query = "¿Qué prácticas de IA están prohibidas?"
    print(f"Query: {query}\n")

    docs = retrieve(query)
    print(f"Retrieve:  {len(docs)} docs encontrados")

    relevant = grade(query, docs)
    print(f"Grade:     {len(relevant)} relevantes")

    result = generate(query, relevant)
    print(f"Generate:  {result['answer']}")
    print(f"Sources:   {result['sources']}")

    print("\n✓ rag/main.py OK")
