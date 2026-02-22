from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
APP_VERSION = os.getenv("APP_VERSION", "dev")
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "eu.amazon.nova-lite-v1:0")


def get_langfuse_handler(
    query: str,
    session_id: str | None = None,
    user_id: str | None = None,
    tags: list[str] | None = None,
) -> Any:
    """Devuelve un CallbackHandler de Langfuse listo para pasar al agente.

    Args:
        query:      Consulta original del usuario (preview en los metadatos de la traza).
        session_id: Identificador de sesión (agrupa trazas de un mismo usuario).
        user_id:    Identificador de usuario (opcional, para dashboards por usuario).
        tags:       Tags custom, p.ej. ["produccion", "rag"].

    Returns:
        langfuse.callback.CallbackHandler

    Raises:
        ImportError: Si langfuse no está instalado (pip install langfuse).
        ValueError:  Si LANGFUSE_PUBLIC_KEY o LANGFUSE_SECRET_KEY no están definidas.
    """
    try:
        from langfuse.callback import CallbackHandler
    except ImportError as exc:
        raise ImportError("Instala langfuse: pip install langfuse") from exc

    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")

    if not public_key or not secret_key:
        raise ValueError("Define LANGFUSE_PUBLIC_KEY y LANGFUSE_SECRET_KEY como variables de entorno.\n")

    return CallbackHandler(
        public_key=public_key,
        secret_key=secret_key,
        host=LANGFUSE_HOST,
        trace_name="normabot-query",
        session_id=session_id,
        user_id=user_id,
        tags=tags or ["produccion"],
        metadata={
            "model": BEDROCK_MODEL_ID,
            "version": APP_VERSION,
            "input_preview": query[:120],
        },
    )
