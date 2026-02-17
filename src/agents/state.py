"""Estado compartido del grafo LangGraph.

Define AgentState, el TypedDict que fluye por todos los nodos del grafo.
Cada nodo recibe el estado completo y devuelve solo las claves que modifica.
"""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict


class AgentState(TypedDict):
    """Estado que fluye por el grafo de agentes NormaBot.

    Campos:
        query: consulta original del usuario.
        route: agente seleccionado por el router ("rag", "classifier", "report").
        documents: chunks recuperados del vector store (RAG).
        risk_level: nivel de riesgo asignado por el clasificador ML.
        report: informe de cumplimiento generado.
        response: respuesta final sintetizada para el usuario.
        sources: citas legales (ley, artículo, fecha).
    """

    query: str
    route: str
    documents: Annotated[list[dict], operator.add]
    risk_level: str
    report: str
    response: str
    sources: Annotated[list[dict], operator.add]
    # operator.add : equivalente a hacer lista_existente + lista_nueva (concatenacion). Asi cada nodo puede aportar sus resultados sin perder los de nodos anteriores.
