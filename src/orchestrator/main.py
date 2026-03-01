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
from pydantic import BaseModel, Field

try:
    from langfuse.decorators import observe, langfuse_context
except ImportError:
    def observe(name=None):  # type: ignore[misc]
        def decorator(func):
            return func
        return decorator

    class _NoOpLangfuse:
        def update_current_observation(self, **kwargs): pass
        def score_current_trace(self, **kwargs): pass

    langfuse_context = _NoOpLangfuse()  # type: ignore[assignment]

from src.observability.main import get_langfuse_handler
from src.classifier.main import predict_risk

logger = logging.getLogger(__name__)

# Caché de clasificaciones por sesión: evita llamar al clasificador dos veces
# cuando el agente usa classify_risk y generate_report sobre la misma descripción.
_risk_cache: dict[str, dict] = {}


def _cached_predict_risk(system_description: str) -> dict:
    if system_description not in _risk_cache:
        _risk_cache[system_description] = predict_risk(system_description)
    return _risk_cache[system_description]

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "eu.amazon.nova-lite-v1:0")
BEDROCK_REGION = os.environ.get("BEDROCK_REGION") or os.environ.get("AWS_REGION", "eu-west-1")

SYSTEM_PROMPT = """\
Eres NormaBot, un asistente jurídico especializado en el EU AI Act \
(Reglamento (UE) 2024/1689) y normativa española de inteligencia artificial.

Tu trabajo es ayudar a los usuarios a entender la regulación, clasificar \
sistemas de IA por nivel de riesgo y generar informes de cumplimiento.

Responde SIEMPRE en el mismo idioma en que el usuario escribe. \
Por defecto, responde en español.

Usa las herramientas disponibles para responder. Para clasificaciones de \
riesgo, cita únicamente la referencia legal que devuelva la herramienta \
classify_risk — no añadas ni infergas artículos adicionales del EU AI Act \
que no estén en su respuesta.

Añade siempre al final: "_Informe preliminar generado por IA. Consulte \
profesional jurídico._"\
"""

# ---------------------------------------------------------------------------
# Validacion de entrada (Pydantic)
# ---------------------------------------------------------------------------


class _QueryInput(BaseModel):
    query: str = Field(min_length=1, max_length=4000)


class _SystemDescriptionInput(BaseModel):
    system_description: str = Field(min_length=1, max_length=5000)


# ---------------------------------------------------------------------------
# Herramientas
# ---------------------------------------------------------------------------


@tool
@observe(name="tool.search_legal_docs")
def search_legal_docs(query: str) -> str:
    """Busca normativa, artículos, definiciones y conceptos legales en el
    EU AI Act y legislación española de IA.

    Usa esta herramienta cuando el usuario pregunta sobre leyes, artículos,
    prohibiciones, obligaciones, definiciones o cualquier contenido normativo.
    """
    try:
        _QueryInput(query=query)
    except Exception as e:
        return f"Error de validacion: {e}"

    from src.rag.main import retrieve, grade, generate

    docs = retrieve(query)
    if not docs:
        try:
            langfuse_context.update_current_observation(metadata={"n_docs": 0, "n_relevant": 0})
        except Exception:
            pass
        return "No se encontraron documentos relevantes para esta consulta."

    relevant = grade(query, docs)
    try:
        langfuse_context.update_current_observation(
            metadata={"n_docs": len(docs), "n_relevant": len(relevant)}
        )
    except Exception:
        pass
    if not relevant:
        return "Se encontraron documentos pero ninguno fue relevante para la consulta."

    result = generate(query, relevant)
    return result["answer"]


@tool
@observe(name="tool.classify_risk")
def classify_risk(system_description: str) -> str:
    """Clasifica un sistema de IA según su nivel de riesgo
    (inaceptable, alto, limitado, mínimo).

    Usa esta herramienta cuando el usuario describe un sistema de IA y quiere
    saber su nivel de riesgo según el EU AI Act.
    """
    try:
        _SystemDescriptionInput(system_description=system_description)
    except Exception as e:
        return f"Error de validacion: {e}"

    result = _cached_predict_risk(system_description)
    try:
        langfuse_context.update_current_observation(
            metadata={
                "risk_level": result.get("risk_level"),
                "confidence": result.get("confidence"),
                "annex3_ref": result.get("annex3_ref"),
            }
        )
    except Exception:
        pass

    # Bug 2 — Referencia legal explícita: annex3_ref si hubo override determinista,
    # si no, fallback por nivel de riesgo según EU AI Act.
    _LEGAL_REFS = {
        "inaceptable": "Art. 5 EU AI Act (sistema prohibido)",
        "alto_riesgo": "Art. 6 + Anexo III EU AI Act",
        "riesgo_limitado": "Art. 6 EU AI Act",
        "riesgo_minimo": "Art. 6 EU AI Act (sin obligaciones adicionales)",
    }
    legal_ref = result.get("annex3_ref") or _LEGAL_REFS.get(
        result["risk_level"], "Art. 6 EU AI Act"
    )

    response = (
        f"Clasificacion: {result['risk_level'].upper()}\n"
        f"Confianza: {result['confidence']:.0%}\n"
        f"Referencia legal: {legal_ref}\n"
    )

    # Bug 7 — Mostrar solo features semánticamente interpretables.
    # Excluir componentes SVD (svd_N) y métricas de longitud (num_palabras,
    # num_caracteres), que no tienen significado legal para el usuario.
    _NO_INTERPRETAR = {"num_palabras", "num_caracteres"}
    interpretable = [
        f for f in result.get("shap_top_features", [])
        if not f["feature"].startswith("svd_") and f["feature"] not in _NO_INTERPRETAR
    ]
    if interpretable:
        features = ", ".join(f["feature"] for f in interpretable[:3])
        response += f"Factores clave: {features}\n"

    return response



@tool
@observe(name="tool.generate_report")
def generate_report(system_description: str) -> str:
    """Genera un informe de cumplimiento normativo para un sistema de IA.

    Usa esta herramienta cuando el usuario quiere un informe, reporte o
    evaluación de conformidad para su sistema.
    """
    try:
        _SystemDescriptionInput(system_description=system_description)
    except Exception as e:
        return f"Error de validacion: {e}"

    from src.report.main import generate_report as _build_report

    # 1. Clasificar riesgo del sistema (usa caché si classify_risk ya lo computó)
    risk_result = _cached_predict_risk(system_description)
    risk_level = risk_result["risk_level"]

    # 2. Buscar artículos relevantes en el corpus legal
    articles = []
    try:
        from src.retrieval.retriever import search as search_docs
        hits = search_docs(
            f"obligaciones sistemas de riesgo {risk_level} EU AI Act", k=3,
        )
        for h in hits:
            meta = h.get("metadata", {}) or {}
            source = meta.get("source", "")
            unit = meta.get("unit_title") or meta.get("unit_id", "")
            label = f"{source} — {unit}".strip(" —")
            text = h.get("text", "").strip()
            if label:
                entry = f"{label}\n{text}" if text else label
                articles.append(entry)
    except Exception as e:
        logger.warning("Retriever no disponible para informe: %s", e)

    if not articles:
        logger.warning(
            "Sin artículos verificados del corpus para nivel '%s'. "
            "Informe generado sin citas verificadas.",
            risk_level,
        )
        articles = ["No se pudieron verificar artículos específicos en el corpus legal."]

    try:
        langfuse_context.update_current_observation(
            metadata={
                "risk_level": risk_level,
                "n_articles": len(articles),
                "articles_verified": articles[0] != "No se pudieron verificar artículos específicos en el corpus legal.",
            }
        )
    except Exception:
        pass

    # 3. Generar informe con template
    return _build_report(system_description, risk_level, articles)


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


def run(query: str, session_id: str | None = None, user_id: str | None = None) -> dict:
    """Ejecuta el agente ReAct con una consulta del usuario."""
    agent = _get_agent()

    try:
        callbacks = [
            get_langfuse_handler(
                session_id=session_id,
                user_id=user_id,
                tags=["produccion", "normabot-v1"],
            )
        ]
    except (ImportError, ValueError) as e:
        logger.debug("Langfuse no disponible: %s — continuando sin trazas", e)
        callbacks = []

    result = agent.invoke(
        {"messages": [("user", query)]},
        config={"callbacks": callbacks},
    )
    return result


if __name__ == "__main__":
    import uuid

    # Generamos un ID único para agrupar estas consultas en una misma sesión de Langfuse
    test_session = f"session-{uuid.uuid4().hex[:8]}"

    queries = [
        "¿Qué dice el artículo 5 del EU AI Act?",
        "Clasifica mi sistema de reconocimiento facial",
        "Genera un informe de cumplimiento para mi chatbot",
        "Clasifica un sistema de scoring crediticio y dime que articulos aplican",
    ]

    for q in queries:
        print(f"{'=' * 60}")
        # Pasamos el session_id para que Langfuse v3 lo capture mediante el CallbackHandler
        result = run(q, session_id=test_session)

        final_message = result["messages"][-1]
        print(f"  Query:    {q}")
        print(f"  Response: {final_message.content[:200]}...")
        print()

    print(f"✓ orchestrator/main.py OK — Agente funcional (Sesión: {test_session})")
