"""orchestrator/main.py — Punto de entrada del grafo LangGraph.

Expone `run(query)` que invoca el grafo compilado de src/agents/graph.py.
El grafo hace: route_query → agente (rag|classifier|report) → synthesize.
"""

from src.agents.graph import graph


def run(query: str) -> dict:
    """Ejecuta el grafo LangGraph con una consulta del usuario."""
    result = graph.invoke({
        "query": query,
        "route": "",
        "documents": [],
        "risk_level": "",
        "report": "",
        "response": "",
        "sources": [],
    })
    return result


if __name__ == "__main__":
    queries = [
        "¿Qué dice el artículo 5 del EU AI Act?",
        "Clasifica mi sistema de reconocimiento facial",
        "Genera un informe de cumplimiento para mi chatbot",
    ]
    for q in queries:
        print(f"{'=' * 60}")
        r = run(q)
        print(f"  Query:      {r['query']}")
        print(f"  Route:      {r['route']}")
        print(f"  Response:   {r['response'][:120]}...")
        print(f"  Sources:    {r['sources']}")
        if r.get("risk_level"):
            print(f"  Risk Level: {r['risk_level']}")
        if r.get("report"):
            print(f"  Report:     {r['report'][:80]}...")
        print()

    print("✓ orchestrator/main.py OK — LangGraph funcional")
