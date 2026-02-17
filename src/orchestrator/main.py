"""orchestrator/main.py — LLM Provider + Orquestador LangGraph
Hello world: simula llamada a Groq y grafo con router + 3 agentes stub.
"""


# --- LLM Provider ---

def call_llm(query: str) -> dict:
    # TODO: reemplazar con Groq(api_key=...).chat.completions.create(...)
    return {
        "model": "llama-3.3-70b-versatile",
        "query": query,
        "response": "El EU AI Act (Reglamento UE 2024/1689) es la primera regulación integral de inteligencia artificial a nivel mundial.",
        "tokens": {"input": 24, "output": 31, "total": 55},
    }


# --- Orquestador LangGraph ---

def router(query: str) -> str:
    # TODO: reemplazar con LangGraph StateGraph + conditional_edges
    q = query.lower()
    if "clasifica" in q or "riesgo" in q:
        return "classifier"
    elif "informe" in q or "cumplimiento" in q:
        return "report"
    return "rag"


def rag_node(query: str) -> str:
    return f"[RAG] Según el Art. 6 del EU AI Act, los sistemas de alto riesgo deben cumplir requisitos específicos. (query: {query})"


def classifier_node(query: str) -> str:
    return f"[Clasificador] Sistema clasificado como ALTO RIESGO — Anexo III. (query: {query})"


def report_node(query: str) -> str:
    return f"[Informe] Informe de cumplimiento generado con 3 artículos citados. (query: {query})"


AGENTS = {
    "rag": rag_node,
    "classifier": classifier_node,
    "report": report_node,
}


def run(query: str) -> dict:
    route = router(query)
    response = AGENTS[route](query)
    return {"query": query, "route": route, "response": response}


if __name__ == "__main__":
    # LLM Provider
    result = call_llm("¿Qué es el EU AI Act?")
    print(f"Model:     {result['model']}")
    print(f"Query:     {result['query']}")
    print(f"Response:  {result['response']}")
    print(f"Tokens:    {result['tokens']['total']} ({result['tokens']['input']} in + {result['tokens']['output']} out)")
    print()

    # Orquestador
    queries = [
        "¿Qué dice el artículo 5 del EU AI Act?",
        "Clasifica mi sistema de reconocimiento facial",
        "Genera un informe de cumplimiento para mi chatbot",
    ]
    for q in queries:
        r = run(q)
        print(f"  Query:    {r['query']}")
        print(f"  Route:    {r['route']}")
        print(f"  Response: {r['response']}")
        print()

    print("✓ orchestrator/main.py OK")
