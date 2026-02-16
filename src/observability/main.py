"""observability/main.py — Langfuse Trazas LLM
Hello world: simula crear trazas de observabilidad.
"""


def create_trace(query: str, steps: list[dict]) -> dict:
    # TODO: reemplazar con Langfuse().trace() + span() + generation()
    return {
        "trace_id": "trace-abc123",
        "query": query,
        "spans": [
            {"name": s["name"], "duration_ms": s["duration_ms"], "status": "ok"}
            for s in steps
        ],
        "total_ms": sum(s["duration_ms"] for s in steps),
    }


if __name__ == "__main__":
    trace = create_trace(
        query="¿Qué sistemas de IA son de alto riesgo?",
        steps=[
            {"name": "rag_retrieval", "duration_ms": 120},
            {"name": "rag_grading", "duration_ms": 45},
            {"name": "llm_generation", "duration_ms": 890},
            {"name": "self_reflection", "duration_ms": 340},
        ],
    )
    print(f"Trace ID:  {trace['trace_id']}")
    print(f"Query:     {trace['query']}")
    print(f"Total:     {trace['total_ms']}ms")
    print(f"Spans:")
    for s in trace["spans"]:
        print(f"  {s['name']:>20} {s['duration_ms']:>5}ms  {s['status']}")

    print(f"\n  TODO: Langfuse dashboard → https://cloud.langfuse.com")
    print("\n✓ observability/main.py OK")
