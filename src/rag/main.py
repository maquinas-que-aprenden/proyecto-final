"""rag/main.py — Agente RAG Normativo (Corrective RAG)
Flujo Retrieve → Grade → Generate con citas legales desde ChromaDB.
"""

import logging

from langchain_ollama import ChatOllama

from src.retrieval.retriever import search

logger = logging.getLogger(__name__)

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
    global _grading_llm
    if _grading_llm is None:
        _grading_llm = ChatOllama(
            model="qwen2.5:3b",
            temperature=0,
            num_predict=10,
        )
    return _grading_llm


def retrieve(query: str, k: int = 5) -> list[dict]:
    """Recupera documentos de ChromaDB y los formatea para grade()."""
    try:
        results = search(query, k=k, mode="soft")
    except Exception:
        logger.exception("Error al buscar en ChromaDB")
        return []

    return [
        {
            "doc": r["text"],
            "metadata": r.get("metadata", {}),
            "score": max(0.0, 1.0 - r.get("distance", 1.0)),
        }
        for r in results
    ]


def _grade_by_score(docs: list[dict], threshold: float = 0.7) -> list[dict]:
    """Fallback: filtra documentos por score de similitud."""
    return [d for d in docs if d["score"] >= threshold]


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
        return _grade_by_score(docs, threshold)

    relevant = []
    for doc in docs:
        prompt = GRADING_PROMPT.format(document=doc["doc"], query=query)
        try:
            response = llm.invoke(prompt)
            answer = response.content.strip().lower()
            if answer.startswith("si") or answer.startswith("sí"):
                relevant.append(doc)
        except Exception:
            logger.warning("Error en grading LLM, incluyendo doc por score")
            if doc["score"] >= threshold:
                relevant.append(doc)

    return relevant


def generate(query: str, context: list[dict]) -> dict:
    # TODO: reemplazar con Groq LLM call
    citations = ", ".join(f"Art. {d['metadata']['articulo']} {d['metadata']['ley']}" for d in context)
    return {
        "answer": f"Según {citations}: las prácticas de IA que manipulen el comportamiento humano están prohibidas por el EU AI Act.",
        "sources": [d["metadata"] for d in context],
        "grounded": True,
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
    print(f"Grounded:  {result['grounded']}")

    print("\n✓ rag/main.py OK")
