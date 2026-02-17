"""Corrective RAG — Subgrafo LangGraph.

Pipeline: retrieve → grade_documents → (generate | transform_query → retrieve)
Cada función es un nodo del subgrafo que recibe y devuelve RAGState.
"""

from __future__ import annotations

from typing import TypedDict


# ---------------------------------------------------------------------------
# Estado interno del subgrafo RAG
# ---------------------------------------------------------------------------

class RAGState(TypedDict):
    """Estado que fluye por el subgrafo Corrective RAG.

    Campos:
        query: consulta actual (puede ser reformulada por transform_query).
        original_query: consulta original del usuario (no se modifica).
        documents: chunks recuperados del vector store.
        relevant_docs: chunks que pasaron el filtro de relevancia.
        response: respuesta generada con citas legales.
        attempt: número de intento de retrieval (máx 2 para evitar loops infinitos).
    """

    query: str
    original_query: str
    documents: list[dict]
    relevant_docs: list[dict]
    response: str
    attempt: int


# ---------------------------------------------------------------------------
# Corpus mock — simula ChromaDB hasta que Persona A lo tenga listo
# ---------------------------------------------------------------------------

_MOCK_CORPUS = [
    {
        "content": "Artículo 5. Quedan prohibidas las siguientes prácticas de IA: a) sistemas que utilicen técnicas subliminales para alterar el comportamiento de una persona de manera que cause o pueda causar perjuicio físico o psicológico.",
        "metadata": {"ley": "EU AI Act", "articulo": "5", "seccion": "Título II", "fecha": "2024-07-12"},
    },
    {
        "content": "Artículo 6. Un sistema de IA se considerará de alto riesgo cuando esté comprendido en alguno de los ámbitos del Anexo III y presente un riesgo significativo de perjuicio para la salud, la seguridad o los derechos fundamentales.",
        "metadata": {"ley": "EU AI Act", "articulo": "6", "seccion": "Título III, Cap. 1", "fecha": "2024-07-12"},
    },
    {
        "content": "Artículo 9. Se establecerá un sistema de gestión de riesgos en relación con los sistemas de IA de alto riesgo. Consistirá en un proceso iterativo continuo planificado y ejecutado durante todo el ciclo de vida del sistema.",
        "metadata": {"ley": "EU AI Act", "articulo": "9", "seccion": "Título III, Cap. 2", "fecha": "2024-07-12"},
    },
    {
        "content": "Artículo 10. Los conjuntos de datos de entrenamiento, validación y prueba estarán sujetos a prácticas de gobernanza y gestión de datos adecuadas al fin previsto del sistema de IA de alto riesgo.",
        "metadata": {"ley": "EU AI Act", "articulo": "10", "seccion": "Título III, Cap. 2", "fecha": "2024-07-12"},
    },
    {
        "content": "Artículo 14. Los sistemas de IA de alto riesgo se diseñarán y desarrollarán de modo que puedan ser vigilados de manera efectiva por personas físicas durante su período de utilización, incluida la posibilidad de intervención humana.",
        "metadata": {"ley": "EU AI Act", "articulo": "14", "seccion": "Título III, Cap. 2", "fecha": "2024-07-12"},
    },
    {
        "content": "Artículo 52. Los proveedores garantizarán que los sistemas de IA destinados a interactuar con personas físicas se diseñen de modo que las personas sean informadas de que están interactuando con un sistema de IA.",
        "metadata": {"ley": "EU AI Act", "articulo": "52", "seccion": "Título IV", "fecha": "2024-07-12"},
    },
    {
        "content": "Artículo 71. Las infracciones de las prácticas prohibidas del artículo 5 estarán sujetas a multas administrativas de hasta 35 000 000 EUR o el 7% del volumen de negocios total anual mundial.",
        "metadata": {"ley": "EU AI Act", "articulo": "71", "seccion": "Título X", "fecha": "2024-07-12"},
    },
    {
        "content": "Artículo 80 bis de la LOPD-GDD. El responsable del tratamiento deberá realizar una evaluación de impacto cuando el tratamiento entrañe un alto riesgo para los derechos y libertades de las personas físicas.",
        "metadata": {"ley": "LOPD-GDD", "articulo": "80 bis", "seccion": "Título VI", "fecha": "2018-12-06"},
    },
]


# ---------------------------------------------------------------------------
# Nodo 1: retrieve
# ---------------------------------------------------------------------------

def retrieve(state: RAGState) -> RAGState:
    """Busca documentos relevantes en el vector store.

    Simula una búsqueda por similitud semántica contra ChromaDB.
    Cuando Persona A tenga ChromaDB listo, se reemplaza el contenido
    de esta función por una query real:

        results = collection.query(query_texts=[query], n_results=k)

    La firma del nodo (recibe RAGState, devuelve dict parcial) no cambia.
    """
    query = state["query"]
    query_lower = query.lower()

    # Mock: filtro por keywords (simula similitud semántica)
    scored_docs = []
    for doc in _MOCK_CORPUS:
        content_lower = doc["content"].lower()
        # Puntuar por coincidencia de palabras clave de la query
        query_words = [w for w in query_lower.split() if len(w) > 3]
        matches = sum(1 for w in query_words if w in content_lower)
        score = matches / max(len(query_words), 1)
        if score > 0:
            scored_docs.append({**doc, "score": round(score, 2)})

    # Ordenar por score y tomar top-k
    scored_docs.sort(key=lambda d: d["score"], reverse=True)
    top_k = scored_docs[:4]

    return {
        "documents": top_k,
        "attempt": state.get("attempt", 0) + 1,
    }


# ---------------------------------------------------------------------------
# Nodo 2: grade_documents
# ---------------------------------------------------------------------------

_RELEVANCE_THRESHOLD = 0.3


def grade_documents(state: RAGState) -> RAGState:
    """Evalúa la relevancia de cada documento recuperado respecto a la query.

    Un LLM actúa como juez: para cada chunk decide "yes" o "no".

    TODO: reemplazar mock por LLM call real. Prompt tipo:
        "Dado este documento: {doc} ¿Es relevante para responder: {query}?
         Responde solo 'yes' o 'no'."
    """
    documents = state["documents"]

    relevant = []
    for doc in documents:
        # Mock: usa el score del retrieve como proxy de relevancia
        # En producción: llm.invoke(grade_prompt.format(doc=doc, query=query))
        score = doc.get("score", 0)
        if score >= _RELEVANCE_THRESHOLD:
            relevant.append(doc)

    return {"relevant_docs": relevant}


# ---------------------------------------------------------------------------
# Nodo 3: transform_query
# ---------------------------------------------------------------------------

def transform_query(state: RAGState) -> RAGState:
    """Reformula la query cuando los documentos recuperados no son relevantes.

    Se activa solo si grade_documents no encontró docs válidos.
    El objetivo es reescribir la consulta para mejorar el retrieval
    en el siguiente intento.

    TODO: reemplazar mock por LLM call real. Prompt tipo:
        "La siguiente consulta no obtuvo resultados relevantes en una base
         de legislación española (BOE, EU AI Act, LOPD).
         Consulta original: {query}
         Reescríbela para mejorar la búsqueda en el corpus legal."
    """
    original = state["original_query"]

    # Mock: añade contexto legal a la query para mejorar el retrieval
    # En producción: llm.invoke(rewrite_prompt.format(query=original))
    rewritten = f"normativa regulación IA {original}"

    return {"query": rewritten}
