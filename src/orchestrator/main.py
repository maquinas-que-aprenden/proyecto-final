"""orchestrator/main.py — Agente ReAct orquestador de NormaBot.

Usa Amazon Bedrock (Nova Lite v1) como LLM con tool calling.
El agente razona sobre la consulta del usuario y decide qué herramientas
usar: búsqueda normativa (RAG), clasificación de riesgo, o informe de
cumplimiento.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from typing_extensions import Annotated

from langchain_aws import ChatBedrockConverse
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent, InjectedStore
from langgraph.store.memory import InMemoryStore
from pydantic import BaseModel, Field

from src.memory.hooks import pre_model_hook

# Checkpointer: SQLite persistente si está disponible, sino en memoria
try:
    from langgraph.checkpoint.sqlite import SqliteSaver

    _SQLITE_AVAILABLE = True
except ImportError:
    from langgraph.checkpoint.memory import InMemorySaver

    _SQLITE_AVAILABLE = False

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

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "eu.amazon.nova-lite-v1:0")
BEDROCK_REGION = os.environ.get("BEDROCK_REGION") or os.environ.get("AWS_REGION", "eu-west-1")
MEMORY_DIR = os.environ.get("NORMABOT_MEMORY_DIR", "data/memory")

SYSTEM_PROMPT = """\
Eres NormaBot, un asistente jurídico especializado en el EU AI Act \
(Reglamento (UE) 2024/1689) y normativa española de inteligencia artificial.

Tu trabajo es ayudar a los usuarios a entender la regulación, clasificar \
sistemas de IA por nivel de riesgo y generar informes de cumplimiento.

Responde SIEMPRE en el mismo idioma en que el usuario escribe. \
Por defecto, responde en español.

Usa las herramientas disponibles para responder. Siempre cita las fuentes \
legales (ley y artículo) en tu respuesta.

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

    result = predict_risk(system_description)
    try:
        langfuse_context.update_current_observation(
            metadata={
                "risk_level": result.get("risk_level"),
                "confidence": result.get("confidence"),
            }
        )
    except Exception:
        pass
    response = (
        f"Clasificacion: {result['risk_level'].upper()}\n"
        f"Confianza: {result['confidence']:.0%}\n"
    )
    if result.get("shap_top_features"):
        features = ", ".join(f["feature"] for f in result["shap_top_features"][:3])
        response += f"Factores clave: {features}\n"
    if result.get("shap_explanation"):
        response += f"Explicacion: {result['shap_explanation']}\n"
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

    # 1. Clasificar riesgo del sistema
    risk_result = predict_risk(system_description)
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
# Herramienta de memoria de usuario
# ---------------------------------------------------------------------------


@tool
def save_user_preference(
    key: str,
    value: str,
    store: Annotated[Any, InjectedStore()],
) -> str:
    """Guarda una preferencia o dato del usuario para recordarlo en futuras
    conversaciones.

    Usa esta herramienta cuando el usuario te pida explícitamente que
    recuerdes algo sobre él o su organización (sector, tipo de sistema,
    preferencias, contexto).
    """
    store.put(("user_preferences",), key, {"value": value})
    return f"Preferencia guardada: {key} = {value}"


@tool
def get_user_preferences(
    store: Annotated[Any, InjectedStore()],
) -> str:
    """Recupera las preferencias guardadas del usuario.

    Usa esta herramienta al inicio de la conversación o cuando necesites
    contexto sobre el usuario.
    """
    items = store.search(("user_preferences",))
    if not items:
        return "No hay preferencias guardadas."
    return "\n".join(f"- {item.key}: {item.value['value']}" for item in items)


# ---------------------------------------------------------------------------
# Agente ReAct con memoria
# ---------------------------------------------------------------------------

_agent = None
_checkpointer = None
_store = None


def _get_checkpointer():
    """Singleton del checkpointer — SQLite si disponible, sino en memoria."""
    global _checkpointer
    if _checkpointer is not None:
        return _checkpointer

    if _SQLITE_AVAILABLE:
        memory_dir = Path(MEMORY_DIR)
        memory_dir.mkdir(parents=True, exist_ok=True)
        db_path = str(memory_dir / "conversations.db")
        _checkpointer = SqliteSaver.from_conn_string(db_path)
        _checkpointer.setup()
        logger.info("Checkpointer SQLite inicializado: %s", db_path)
    else:
        _checkpointer = InMemorySaver()
        logger.info("Checkpointer en memoria (langgraph-checkpoint-sqlite no instalado)")

    return _checkpointer


def _get_store() -> InMemoryStore:
    """Singleton del store para memoria cross-thread."""
    global _store
    if _store is None:
        _store = InMemoryStore()
        logger.info("InMemoryStore inicializado para preferencias de usuario")
    return _store


def _build_agent():
    """Construye el agente ReAct con Bedrock Nova Lite, herramientas y memoria."""
    llm = ChatBedrockConverse(
        model=BEDROCK_MODEL_ID,
        region_name=BEDROCK_REGION,
        temperature=0.0,
    )
    tools = [
        search_legal_docs,
        classify_risk,
        generate_report,
        save_user_preference,
        get_user_preferences,
    ]
    return create_react_agent(
        llm,
        tools,
        prompt=SYSTEM_PROMPT,
        checkpointer=_get_checkpointer(),
        store=_get_store(),
        pre_model_hook=pre_model_hook,
    )


def _get_agent():
    """Singleton lazy del agente — se crea en el primer uso."""
    global _agent
    if _agent is None:
        _agent = _build_agent()
    return _agent


def run(query: str, session_id: str | None = None, user_id: str | None = None) -> dict:
    """Ejecuta el agente ReAct con memoria conversacional.

    Con el checkpointer, solo se envía el mensaje nuevo. El checkpointer
    carga automáticamente el historial previo para el ``thread_id``.
    """
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

    config = {
        "callbacks": callbacks,
        "configurable": {
            "thread_id": session_id or "default",
        },
    }

    result = agent.invoke(
        {"messages": [("user", query)]},
        config=config,
    )
    return result


if __name__ == "__main__":
    import uuid

    # Generamos un ID único para agrupar estas consultas en una misma sesión
    test_session = f"session-{uuid.uuid4().hex[:8]}"

    # Demo de memoria multi-turn: las queries usan la misma sesión
    queries = [
        "¿Qué dice el artículo 5 del EU AI Act?",
        "Clasifica mi sistema de reconocimiento facial",
        # Esta query depende del contexto previo (multi-turn):
        "Genera un informe de cumplimiento para ese sistema",
    ]

    for q in queries:
        print(f"{'=' * 60}")
        result = run(q, session_id=test_session)

        final_message = result["messages"][-1]
        print(f"  Query:    {q}")
        print(f"  Response: {final_message.content[:200]}...")
        print()

    print(f"✓ orchestrator/main.py OK — Agente con memoria (Sesión: {test_session})")
