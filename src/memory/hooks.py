"""memory/hooks.py — Pre-model hook para gestion de historial de mensajes.

Recorta el historial antes de enviarlo al LLM para evitar exceder
la ventana de contexto, sin modificar el estado guardado en el checkpointer.
"""

from __future__ import annotations

import logging

from langchain_core.messages.utils import (
    count_tokens_approximately,
    trim_messages,
)

logger = logging.getLogger(__name__)

# Nova Lite v1 soporta ~300K tokens, pero dejamos margen para
# tool responses, system prompt y respuesta del modelo.
MAX_CONVERSATION_TOKENS = 30_000


def pre_model_hook(state: dict) -> dict:
    """Recorta mensajes antes de enviarlos al LLM.

    Devuelve ``llm_input_messages`` para que el historial completo se
    preserve en el checkpointer mientras el LLM solo recibe los mensajes
    recientes.
    """
    messages = state.get("messages", [])

    trimmed = trim_messages(
        messages,
        strategy="last",
        token_counter=count_tokens_approximately,
        max_tokens=MAX_CONVERSATION_TOKENS,
        start_on="human",
        include_system=True,
    )

    return {"llm_input_messages": trimmed}
