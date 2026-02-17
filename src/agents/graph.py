"""Grafo LangGraph — Orquestador de 3 agentes NormaBot.

Flujo:
    START → route_query → (condicional) → rag / classifier / report → synthesize → END

Cada nodo-agente es un stub que será reemplazado por la implementación real
de src/rag, src/classifier y src/report conforme avancen los sprints.
"""

from __future__ import annotations

from typing import Literal

from langgraph.graph import END, START, StateGraph

from src.agents.state import AgentState

# ---------------------------------------------------------------------------
# Nodos del grafo
# ---------------------------------------------------------------------------

ROUTE_RAG = "rag"
ROUTE_CLASSIFIER = "classifier"
ROUTE_REPORT = "report"


def route_query(state: AgentState) -> AgentState:
    """Analiza la consulta y decide qué agente activar.

    TODO: reemplazar heurística por LLM call (Groq) que clasifique el intent.
    """
    query = state["query"].lower()

    if any(kw in query for kw in ("clasifica", "riesgo", "nivel", "anexo")):
        route = ROUTE_CLASSIFIER
    elif any(kw in query for kw in ("informe", "cumplimiento", "reporte", "obligaciones")):
        route = ROUTE_REPORT
    else:
        route = ROUTE_RAG

    return {"route": route}


def pick_agent(
    state: AgentState,
) -> Literal["rag_agent", "classifier_agent", "report_agent"]:
    """Routing condicional: devuelve el nombre del nodo-agente destino."""
    mapping = {
        ROUTE_RAG: "rag_agent",
        ROUTE_CLASSIFIER: "classifier_agent",
        ROUTE_REPORT: "report_agent",
    }
    return mapping[state["route"]]


# --- Agentes (stubs → se conectarán con src/rag, src/classifier, src/report) ---


def rag_agent(state: AgentState) -> AgentState:
    """Agente RAG Normativo — Corrective RAG pipeline.

    TODO (día 3-4): conectar con src/rag (retrieve → grade → transform → generate → self-reflection).
    """
    query = state["query"]
    docs = [
        {
            "content": "Art. 5: Quedan prohibidas las prácticas de IA que manipulen el comportamiento humano.",
            "ley": "EU AI Act",
            "articulo": "5",
            "score": 0.92,
        },
    ]
    sources = [{"ley": d["ley"], "articulo": d["articulo"]} for d in docs]

    return {
        "documents": docs,
        "sources": sources,
        "response": f"[RAG] Según Art. 5 del EU AI Act, las prácticas prohibidas incluyen... (query: {query})",
    }


def classifier_agent(state: AgentState) -> AgentState:
    """Agente Clasificador de Riesgo — ML pipeline.

    TODO: conectar con src/classifier (XGBoost + SHAP).
    """
    query = state["query"]
    return {
        "risk_level": "Alto riesgo",
        "sources": [{"ley": "EU AI Act", "articulo": "6"}, {"ley": "EU AI Act", "articulo": "Anexo III"}],
        "response": f"[Clasificador] Sistema clasificado como ALTO RIESGO — Anexo III, Art. 6. (query: {query})",
    }


def report_agent(state: AgentState) -> AgentState:
    """Agente de Informes de Cumplimiento.

    TODO: conectar con src/report (template + LLM genera informe con citas).
    """
    query = state["query"]
    return {
        "report": "## Informe de Cumplimiento\n\n*Informe preliminar, consulte profesional jurídico.*",
        "sources": [{"ley": "EU AI Act", "articulo": "43"}, {"ley": "EU AI Act", "articulo": "9"}],
        "response": f"[Informe] Informe de cumplimiento generado con citas legales. (query: {query})",
    }


def synthesize(state: AgentState) -> AgentState:
    """Sintetiza la respuesta final a partir del output del agente ejecutado.

    TODO: usar LLM para generar respuesta unificada combinando response + sources.
    """
    sources_str = ", ".join(
        f"Art. {s['articulo']} {s['ley']}" for s in state.get("sources", [])
    )
    disclaimer = "\n\n_Informe preliminar generado por IA. Consulte profesional jurídico._"
    response = state.get("response", "")

    return {
        "response": f"{response}\n\nFuentes: {sources_str}{disclaimer}",
    }


# ---------------------------------------------------------------------------
# Construcción del grafo
# ---------------------------------------------------------------------------


def build_graph() -> StateGraph:
    """Construye y compila el grafo de agentes NormaBot.

    Grafo:
        START → route_query →(condicional)→ rag_agent
                                           → classifier_agent  → synthesize → END
                                           → report_agent
    """
    workflow = StateGraph(AgentState)

    # Nodos
    workflow.add_node("route_query", route_query)
    workflow.add_node("rag_agent", rag_agent)
    workflow.add_node("classifier_agent", classifier_agent)
    workflow.add_node("report_agent", report_agent)
    workflow.add_node("synthesize", synthesize)

    # Edges
    workflow.add_edge(START, "route_query")
    workflow.add_conditional_edges(
        "route_query",
        pick_agent,
        ["rag_agent", "classifier_agent", "report_agent"],
    )
    workflow.add_edge("rag_agent", "synthesize")
    workflow.add_edge("classifier_agent", "synthesize")
    workflow.add_edge("report_agent", "synthesize")
    workflow.add_edge("synthesize", END)

    return workflow.compile()


# Grafo compilado listo para usar: graph.invoke({"query": "..."})
graph = build_graph()
