"""orchestrator/main.py — Agente ReAct orquestador de NormaBot.

Usa Amazon Bedrock (Nova Lite v1) como LLM con tool calling.
El agente razona sobre la consulta del usuario y decide qué herramientas
usar: búsqueda normativa (RAG) o clasificación de riesgo con checklist
de cumplimiento.
"""

from __future__ import annotations

import contextvars
import logging
import os
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any

from typing_extensions import Annotated

from langchain_aws import ChatBedrockConverse
from langchain_core.runnables import RunnableConfig
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

from src.observability.langfuse_compat import observe, langfuse_context
from src.observability.main import get_langfuse_handler
from src.classifier.main import predict_risk

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Side-channel para metadatos verificados de las herramientas
# Los datos legales (citas, nivel de riesgo) se transportan por fuera del LLM
# para evitar que el modelo reformule o alucine referencias legales.
# ---------------------------------------------------------------------------

_tool_metadata: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "tool_metadata", default=None
)


def _get_tool_metadata() -> dict[str, Any]:
    """Devuelve (o inicializa) el dict de metadatos de la invocación actual."""
    meta = _tool_metadata.get(None)
    if meta is None:
        meta = {"citations": [], "risk": None, "report": None}
        _tool_metadata.set(meta)
    return meta


@lru_cache(maxsize=256)
def _cached_predict_risk(system_description: str) -> dict:
    """Evita clasificar dos veces la misma descripción en una misma sesión."""
    return predict_risk(system_description)

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "eu.amazon.nova-lite-v1:0")
BEDROCK_REGION = os.environ.get("BEDROCK_REGION") or os.environ.get("AWS_REGION", "eu-west-1")
MEMORY_DIR = os.environ.get("NORMABOT_MEMORY_DIR", "data/memory")

SYSTEM_PROMPT = """\
Eres NormaBot, un asistente juridico especializado en el EU AI Act \
(Reglamento (UE) 2024/1689) y normativa espanola de inteligencia artificial.

Tu trabajo es ayudar a los usuarios a entender la regulacion, clasificar \
sistemas de IA por nivel de riesgo y evaluar sus obligaciones de cumplimiento.

Responde SIEMPRE en el mismo idioma en que el usuario escribe. \
Por defecto, responde en espanol.

Dispones de dos herramientas:

1. **search_legal_docs**: Busca articulos, definiciones y conceptos legales \
en el corpus normativo (EU AI Act, BOE). Usala para preguntas sobre contenido \
de la ley.

2. **classify_risk**: Clasifica un sistema de IA por nivel de riesgo y genera \
un checklist completo de cumplimiento. Incluye: clasificacion, obligaciones \
legales aplicables, advertencias si el caso es borderline, y recomendaciones \
especificas basadas en las caracteristicas del sistema. Usala cuando el \
usuario describe un sistema de IA, pide clasificacion, informe, evaluacion \
o checklist de cumplimiento.

Reglas:
- Cita unicamente las referencias legales que devuelvan las herramientas. \
No inventes ni infieras articulos adicionales.
- Presenta los resultados del checklist de forma clara y estructurada.
- Si el checklist indica un caso borderline, destaca la advertencia.
- Si el nivel es 'inaceptable', enfatiza que el sistema esta PROHIBIDO.
- Para informes completos, combina classify_risk + search_legal_docs.

Anade siempre al final: "_Informe preliminar generado por IA. Consulte \
profesional juridico._"\
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

    # Side-channel: depositar citas verificadas
    meta = _get_tool_metadata()
    for source_meta in result.get("sources", []):
        if isinstance(source_meta, dict) and source_meta:
            meta["citations"].append({
                "source": source_meta.get("source", ""),
                "unit_title": source_meta.get("unit_title", ""),
                "unit_id": source_meta.get("unit_id", ""),
            })

    return result["answer"]


@tool
@observe(name="tool.classify_risk")
def classify_risk(system_description: str) -> str:
    """Clasifica un sistema de IA segun su nivel de riesgo
    (inaceptable, alto, limitado, minimo) y genera un checklist de
    cumplimiento con obligaciones legales, recomendaciones especificas
    y deteccion de casos borderline.

    Usa esta herramienta cuando el usuario describe un sistema de IA y quiere
    saber su nivel de riesgo, obtener un informe de cumplimiento, evaluacion
    o checklist segun el EU AI Act.
    """
    try:
        _SystemDescriptionInput(system_description=system_description)
    except Exception as e:
        return f"Error de validacion: {e}"

    from src.checklist.main import build_compliance_checklist

    result = _cached_predict_risk(system_description)
    checklist = build_compliance_checklist(result, system_description)

    try:
        langfuse_context.update_current_observation(
            metadata={
                "risk_level": checklist["risk_level"],
                "confidence": checklist["confidence"],
                "annex3_ref": checklist.get("annex3_ref"),
                "borderline": checklist["borderline_warning"] is not None,
                "n_obligations": len(checklist["obligations"]),
                "n_specific_recs": len(checklist["specific_recommendations"]),
            }
        )
    except Exception:
        pass

    # Referencia legal determinista: annex3_ref si hubo override del clasificador,
    # si no, fallback por nivel de riesgo según EU AI Act.
    # El side-channel (meta["risk"]) transporta este valor directo a la UI
    # para que el LLM no pueda reformularlo ni alucinar otra cita.
    _LEGAL_REFS = {
        "inaceptable": "Art. 5 EU AI Act (sistema prohibido)",
        "alto_riesgo": "Art. 6 + Anexo III EU AI Act",
        "riesgo_limitado": "Art. 6 EU AI Act",
        "riesgo_minimo": "Art. 6 EU AI Act (sin obligaciones adicionales)",
    }
    legal_ref = result.get("annex3_ref") or _LEGAL_REFS.get(
        result["risk_level"], "Art. 6 EU AI Act"
    )

    # Side-channel: depositar clasificación verificada
    meta = _get_tool_metadata()
    meta["risk"] = {
        "risk_level": result["risk_level"],
        "confidence": result["confidence"],
        "legal_ref": legal_ref,
        "annex3_ref": result.get("annex3_ref"),
        "annex3_override": result.get("annex3_override", False),
    }

    return _format_checklist(checklist)


def _format_checklist(checklist: dict) -> str:
    """Formatea el checklist como texto estructurado para el agente."""
    lines = [
        f"NIVEL DE RIESGO: {checklist['risk_level'].upper()}",
        f"CONFIANZA: {checklist['confidence']:.0%}",
    ]

    if checklist.get("annex3_override"):
        lines.append(f"OVERRIDE ANEXO III: {checklist.get('annex3_ref', '')}")

    if checklist.get("borderline_warning"):
        lines.append(f"ADVERTENCIA BORDERLINE: {checklist['borderline_warning']}")

    lines.append("")
    lines.append("OBLIGACIONES APLICABLES:")
    for i, ob in enumerate(checklist["obligations"], 1):
        tag = "[OBLIGATORIO]" if ob["mandatory"] else "[VOLUNTARIO]"
        lines.append(f"  {i}. {tag} {ob['article']} - {ob['title']}")
        lines.append(f"     {ob['description']}")

    if checklist["specific_recommendations"]:
        lines.append("")
        lines.append("RECOMENDACIONES ESPECIFICAS (basadas en caracteristicas del sistema):")
        for i, rec in enumerate(checklist["specific_recommendations"], 1):
            lines.append(f"  {i}. [{rec['annex_ref']}] (feature: {rec['feature']})")
            lines.append(f"     {rec['recommendation']}")

    lines.append("")
    lines.append(checklist["disclaimer"])

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Herramienta de memoria de usuario
# ---------------------------------------------------------------------------


def _user_namespace(config: RunnableConfig) -> tuple[str, str]:
    """Namespace aislado por usuario para el store de preferencias.

    Usa ``user_id`` si está disponible (preferencias persisten entre sesiones),
    sino ``thread_id`` como fallback (preferencias aisladas por sesión).
    """
    cfg = config.get("configurable", {})
    scope = cfg.get("user_id") or cfg.get("thread_id", "default")
    return ("user_preferences", scope)


@tool
def save_user_preference(
    key: str,
    value: str,
    store: Annotated[Any, InjectedStore()],
    config: RunnableConfig,
) -> str:
    """Guarda una preferencia o dato del usuario para recordarlo en futuras
    conversaciones.

    Usa esta herramienta cuando el usuario te pida explícitamente que
    recuerdes algo sobre él o su organización (sector, tipo de sistema,
    preferencias, contexto).
    """
    store.put(_user_namespace(config), key, {"value": value})
    return f"Preferencia guardada: {key} = {value}"


@tool
def get_user_preferences(
    store: Annotated[Any, InjectedStore()],
    config: RunnableConfig,
) -> str:
    """Recupera las preferencias guardadas del usuario.

    Usa esta herramienta al inicio de la conversación o cuando necesites
    contexto sobre el usuario.
    """
    items = store.search(_user_namespace(config))
    if not items:
        return "No hay preferencias guardadas."
    return "\n".join(f"- {item.key}: {item.value['value']}" for item in items)


# ---------------------------------------------------------------------------
# Agente ReAct con memoria
# ---------------------------------------------------------------------------

_agent = None
_checkpointer = None
_store = None
_lock = threading.Lock()


def _get_checkpointer():
    """Singleton thread-safe del checkpointer (double-checked locking).

    Intenta SQLite si está disponible; degrada a InMemorySaver si falla
    la creación del directorio o la inicialización de la base de datos.
    """
    global _checkpointer
    if _checkpointer is not None:
        return _checkpointer

    with _lock:
        if _checkpointer is not None:
            return _checkpointer

        if _SQLITE_AVAILABLE:
            try:
                memory_dir = Path(MEMORY_DIR)
                memory_dir.mkdir(parents=True, exist_ok=True)
                db_path = str(memory_dir / "conversations.db")
                saver = SqliteSaver.from_conn_string(db_path)
                saver.setup()
                _checkpointer = saver
                logger.info("Checkpointer SQLite inicializado: %s", db_path)
            except Exception:
                logger.warning(
                    "SQLite checkpointer falló, degradando a memoria",
                    exc_info=True,
                )
                _checkpointer = InMemorySaver()
        else:
            _checkpointer = InMemorySaver()
            logger.info(
                "Checkpointer en memoria (langgraph-checkpoint-sqlite no instalado)"
            )

    return _checkpointer


def _get_store() -> InMemoryStore:
    """Singleton thread-safe del store para memoria cross-thread."""
    global _store
    if _store is not None:
        return _store

    with _lock:
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
    _tool_metadata.set(None)  # limpiar invocación anterior

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
            "user_id": user_id,
        },
    }

    result = agent.invoke(
        {"messages": [("user", query)]},
        config=config,
    )

    # Recoger metadatos verificados de las herramientas (side-channel)
    tool_meta = _tool_metadata.get(None)
    result["metadata"] = tool_meta or {"citations": [], "risk": None, "report": None}
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
