from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

def get_langfuse_handler(
    session_id: str | None = None,
    user_id: str | None = None,
    tags: list[str] | None = None,
) -> Any:
    """Devuelve un CallbackHandler de Langfuse compatible con LangChain."""
    try:
        from langfuse.callback import CallbackHandler
    except ImportError as exc:
        raise ImportError("Instala langfuse: pip install langfuse") from exc

    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")

    if not public_key or not secret_key:
        raise ValueError("Define LANGFUSE_PUBLIC_KEY y LANGFUSE_SECRET_KEY.")

    return CallbackHandler(
        public_key=public_key,
        secret_key=secret_key,
        host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
        session_id=session_id,
        user_id=user_id,
        tags=tags or ["produccion"],
        version=os.getenv("APP_VERSION", "dev")
    )