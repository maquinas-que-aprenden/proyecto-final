"""test_memory.py — Tests para el pre_model_hook de memoria de NormaBot.

Verifica que el hook recorta mensajes correctamente para evitar
exceder la ventana de contexto del LLM.
"""

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.memory.hooks import pre_model_hook


# ---------------------------------------------------------------------------
# Tests del pre_model_hook
# ---------------------------------------------------------------------------


class TestPreModelHook:
    """Verifica que el pre_model_hook recorta mensajes correctamente."""

    def test_devuelve_llm_input_messages(self):
        state = {"messages": [HumanMessage(content="hola")]}
        result = pre_model_hook(state)
        assert "llm_input_messages" in result

    def test_no_recorta_mensajes_cortos(self):
        msgs = [HumanMessage(content="hola"), AIMessage(content="mundo")]
        state = {"messages": msgs}
        result = pre_model_hook(state)
        assert len(result["llm_input_messages"]) == 2

    def test_recorta_mensajes_largos(self):
        # Crear muchos mensajes largos para exceder MAX_CONVERSATION_TOKENS
        msgs = []
        for i in range(200):
            msgs.append(HumanMessage(content="x" * 2000))
            msgs.append(AIMessage(content="y" * 2000))
        state = {"messages": msgs}
        result = pre_model_hook(state)
        assert len(result["llm_input_messages"]) < len(msgs)

    def test_preserva_system_message(self):
        msgs = [
            SystemMessage(content="Eres NormaBot"),
            HumanMessage(content="hola"),
            AIMessage(content="respuesta"),
        ]
        state = {"messages": msgs}
        result = pre_model_hook(state)
        has_system = any(
            isinstance(m, SystemMessage) for m in result["llm_input_messages"]
        )
        assert has_system

    def test_estado_vacio(self):
        result = pre_model_hook({"messages": []})
        assert result["llm_input_messages"] == []
