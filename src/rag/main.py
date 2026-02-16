"""rag/main.py — Agente RAG Normativo (Corrective RAG)
Hello world: simula el flujo Retrieve → Grade → Generate con citas.
"""


def retrieve(query: str) -> list[dict]:
    # TODO: reemplazar con ChromaDB query real
    return [
        {"doc": "Art. 5: Quedan prohibidas las prácticas de IA que manipulen el comportamiento humano.", "metadata": {"ley": "EU AI Act", "articulo": "5"}, "score": 0.89},
        {"doc": "Art. 6: Los sistemas de alto riesgo del Anexo III deberán cumplir requisitos.", "metadata": {"ley": "EU AI Act", "articulo": "6"}, "score": 0.62},
    ]


def grade(docs: list[dict], threshold: float = 0.7) -> list[dict]:
    # TODO: reemplazar con LLM que evalúe relevancia
    relevant = [d for d in docs if d["score"] >= threshold]
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

    relevant = grade(docs)
    print(f"Grade:     {len(relevant)} relevantes (threshold=0.7)")

    result = generate(query, relevant)
    print(f"Generate:  {result['answer']}")
    print(f"Sources:   {result['sources']}")
    print(f"Grounded:  {result['grounded']}")

    print("\n✓ rag/main.py OK")
