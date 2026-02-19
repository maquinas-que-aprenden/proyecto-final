"""orchestrator/main.py — Agente ReAct orquestador de NormaBot.

Usa Amazon Bedrock (Nova Lite v1) como LLM con tool calling.
El agente razona sobre la consulta del usuario y decide qué herramientas
usar: búsqueda normativa (RAG), clasificación de riesgo, o informe de
cumplimiento.
"""

from __future__ import annotations

import logging
import os

from langchain_aws import ChatBedrockConverse
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

BEDROCK_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID", "eu.amazon.nova-lite-v1:0"
)
BEDROCK_REGION = os.environ.get("AWS_REGION", "eu-west-1")

SYSTEM_PROMPT = """\
Eres NormaBot, un asistente jurídico especializado en el EU AI Act \
(Reglamento (UE) 2024/1689) y normativa española de inteligencia artificial.

Tu trabajo es ayudar a los usuarios a entender la regulación, clasificar \
sistemas de IA por nivel de riesgo y generar informes de cumplimiento.

Usa las herramientas disponibles para responder. Siempre cita las fuentes \
legales (ley y artículo) en tu respuesta.

Añade siempre al final: "_Informe preliminar generado por IA. Consulte \
profesional jurídico._"\
"""

# ---------------------------------------------------------------------------
# Herramientas (stubs → se conectarán con src/rag, src/classifier, src/report)
# ---------------------------------------------------------------------------


@tool
def search_legal_docs(query: str) -> str:
    """Busca normativa, artículos, definiciones y conceptos legales en el
    EU AI Act y legislación española de IA.

    Usa esta herramienta cuando el usuario pregunta sobre leyes, artículos,
    prohibiciones, obligaciones, definiciones o cualquier contenido normativo.
    """
    # TODO: conectar con src/rag (retrieve → grade → transform → generate)
    return (
        "Resultado de búsqueda:\n"
        "- Art. 5 EU AI Act: Quedan prohibidas las prácticas de IA que "
        "manipulen el comportamiento humano.\n"
        "Fuentes: Art. 5 EU AI Act"
    )


@tool
def classify_risk(system_description: str) -> str:
    """Clasifica un sistema de IA según su nivel de riesgo
    (inaceptable, alto, limitado, mínimo).

    Usa esta herramienta cuando el usuario describe un sistema de IA y quiere
    saber su nivel de riesgo según el EU AI Act.
    """
    # TODO: conectar con src/classifier (XGBoost + SHAP)
    return (
        "Clasificación: ALTO RIESGO\n"
        "El sistema descrito se clasifica como alto riesgo según el Anexo III "
        "del EU AI Act, Art. 6.\n"
        "Fuentes: Art. 6 EU AI Act, Anexo III EU AI Act"
    )


@tool
def generate_report(system_description: str) -> str:
    """Genera un informe de cumplimiento normativo para un sistema de IA.

    Usa esta herramienta cuando el usuario quiere un informe, reporte o
    evaluación de conformidad para su sistema.
    """
    # TODO: conectar con src/report (template + LLM)
    return (
        "## Informe de Cumplimiento\n\n"
        "Sistema evaluado según EU AI Act.\n"
        "Obligaciones aplicables: Art. 9 (gestión de riesgos), "
        "Art. 43 (evaluación de conformidad).\n"
        "Fuentes: Art. 9 EU AI Act, Art. 43 EU AI Act\n\n"
        "*Informe preliminar, consulte profesional jurídico.*"
    )


# ---------------------------------------------------------------------------
# Agente ReAct
# ---------------------------------------------------------------------------

_agent = None


def _build_agent():
    """Construye el agente ReAct con Bedrock Nova Lite y las herramientas."""
    llm = ChatBedrockConverse(
        model=BEDROCK_MODEL_ID,
        region_name=BEDROCK_REGION,
        temperature=0.0,
    )
    tools = [search_legal_docs, classify_risk, generate_report]
    return create_react_agent(llm, tools, prompt=SYSTEM_PROMPT)


def _get_agent():
    """Singleton lazy del agente — se crea en el primer uso."""
    global _agent
    if _agent is None:
        _agent = _build_agent()
    return _agent


def run(query: str) -> dict:
    """Ejecuta el agente ReAct con una consulta del usuario."""
    agent = _get_agent()
    result = agent.invoke({"messages": [("user", query)]})
    return result


if __name__ == "__main__":
    queries = [
        "¿Qué dice el artículo 5 del EU AI Act?",
        "Clasifica mi sistema de reconocimiento facial",
        "Genera un informe de cumplimiento para mi chatbot",
    ]
    for q in queries:
        print(f"{'=' * 60}")
        result = run(q)
        final_message = result["messages"][-1]
        print(f"  Query:    {q}")
        print(f"  Response: {final_message.content[:200]}...")
        print()

    print("✓ orchestrator/main.py OK — Agente ReAct funcional")
