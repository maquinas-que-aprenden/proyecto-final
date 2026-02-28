"""Tests para el flujo de generacion RAG (src/rag/main.py).

Cubre: constante GENERATE_PROMPT, singleton _get_generate_llm(),
y flujo generate() con ChatBedrockConverse mockeado.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

# Inyectar mocks antes de importar src.rag.main,
# ya que langchain_aws y langchain_ollama pueden no estar instalados en el entorno de test.
_mock_langchain_aws = MagicMock()
_previous_langchain_aws = sys.modules.get("langchain_aws")
sys.modules["langchain_aws"] = _mock_langchain_aws

_mock_langchain_ollama = MagicMock()
_previous_langchain_ollama = sys.modules.get("langchain_ollama")
sys.modules["langchain_ollama"] = _mock_langchain_ollama

import src.rag.main as rag_module  # noqa: E402
from src.rag.main import GENERATE_PROMPT, generate  # noqa: E402


def teardown_module(module):
    if _previous_langchain_aws is None:
        sys.modules.pop("langchain_aws", None)
    else:
        sys.modules["langchain_aws"] = _previous_langchain_aws

    if _previous_langchain_ollama is None:
        sys.modules.pop("langchain_ollama", None)
    else:
        sys.modules["langchain_ollama"] = _previous_langchain_ollama


# ---------------------------------------------------------------------------
# 1. GENERATE_PROMPT contiene secciones esperadas
# ---------------------------------------------------------------------------


class TestGeneratePrompt:
    def test_contiene_placeholder_context(self):
        assert "{context}" in GENERATE_PROMPT

    def test_contiene_placeholder_query(self):
        assert "{query}" in GENERATE_PROMPT

    def test_instruccion_citar_fuentes(self):
        assert "fuentes" in GENERATE_PROMPT.lower()

    def test_instruccion_no_inventar(self):
        assert "No inventes" in GENERATE_PROMPT

    def test_formatea_sin_error(self):
        result = GENERATE_PROMPT.format(context="docs aqui", query="pregunta aqui")
        assert "docs aqui" in result
        assert "pregunta aqui" in result


# ---------------------------------------------------------------------------
# 2. Singleton _get_generate_llm()
# ---------------------------------------------------------------------------


class TestGetGenerateLlmSingleton:
    def setup_method(self):
        """Resetea el singleton y garantiza que el mock está activo."""
        rag_module._generate_llm = None
        sys.modules["langchain_aws"] = _mock_langchain_aws

    def teardown_method(self):
        """Limpia el singleton despues de cada test."""
        rag_module._generate_llm = None

    def test_singleton_devuelve_misma_instancia(self):
        mock_instance = MagicMock()
        _mock_langchain_aws.ChatBedrockConverse.return_value = mock_instance

        first = rag_module._get_generate_llm()
        second = rag_module._get_generate_llm()

        assert first is second

    def test_singleton_crea_instancia_una_sola_vez(self):
        _mock_langchain_aws.ChatBedrockConverse.reset_mock()
        _mock_langchain_aws.ChatBedrockConverse.return_value = MagicMock()

        rag_module._get_generate_llm()
        rag_module._get_generate_llm()
        rag_module._get_generate_llm()

        _mock_langchain_aws.ChatBedrockConverse.assert_called_once()

    def test_singleton_asigna_variable_global(self):
        mock_instance = MagicMock()
        _mock_langchain_aws.ChatBedrockConverse.return_value = mock_instance

        assert rag_module._generate_llm is None
        rag_module._get_generate_llm()
        assert rag_module._generate_llm is mock_instance


# ---------------------------------------------------------------------------
# 3. Flujo generate() con mock de ChatBedrockConverse
# ---------------------------------------------------------------------------


class TestGenerateFlow:
    def setup_method(self):
        rag_module._generate_llm = None
        sys.modules["langchain_aws"] = _mock_langchain_aws

    def teardown_method(self):
        rag_module._generate_llm = None

    def test_llm_recibe_parametros_correctos(self):
        _mock_langchain_aws.ChatBedrockConverse.reset_mock()
        mock_instance = MagicMock()
        mock_instance.invoke.return_value = MagicMock(content="Respuesta mock")
        _mock_langchain_aws.ChatBedrockConverse.return_value = mock_instance

        context = [{"doc": "Art. 5 prohibe X", "metadata": {"source": "EU AI Act"}}]
        generate("pregunta test", context)

        _mock_langchain_aws.ChatBedrockConverse.assert_called_once_with(
            model=rag_module.BEDROCK_MODEL_ID,
            region_name=rag_module.BEDROCK_REGION,
            temperature=0.1,
            max_tokens=1024,
        )

    def test_prompt_incluye_context_y_query(self):
        mock_instance = MagicMock()
        mock_instance.invoke.return_value = MagicMock(content="Respuesta mock")
        _mock_langchain_aws.ChatBedrockConverse.return_value = mock_instance

        context = [{"doc": "Contenido del articulo", "metadata": {"source": "BOE"}}]
        generate("mi pregunta legal", context)

        prompt_enviado = mock_instance.invoke.call_args[0][0]
        assert "Contenido del articulo" in prompt_enviado
        assert "mi pregunta legal" in prompt_enviado

    def test_genera_respuesta_con_disclaimer(self):
        mock_instance = MagicMock()
        mock_instance.invoke.return_value = MagicMock(content="El art. 5 establece...")
        _mock_langchain_aws.ChatBedrockConverse.return_value = mock_instance

        context = [{"doc": "texto", "metadata": {"source": "EU AI Act"}}]
        result = generate("pregunta", context)

        assert "El art. 5 establece..." in result["answer"]
        assert "Consulte profesional jurídico" in result["answer"]
        assert result["grounded"] is True
        assert len(result["sources"]) == 1

    @patch.object(rag_module, "_get_generate_llm")
    def test_fallback_cuando_llm_falla(self, mock_get_llm):
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = RuntimeError("Bedrock no disponible")
        mock_get_llm.return_value = mock_llm

        context = [
            {
                "doc": "Texto del documento legal relevante",
                "metadata": {"source": "EU AI Act", "unit_title": "Art. 5"},
            },
        ]
        result = generate("pregunta", context)

        assert result["grounded"] is False
        assert "documentos encontrados" in result["answer"]
        assert "EU AI Act — Art. 5" in result["answer"]
        assert "Consulte profesional jurídico" in result["answer"]

    def test_context_vacio_devuelve_no_encontrados(self):
        result = generate("pregunta", [])

        assert result["grounded"] is False
        assert "No se encontraron" in result["answer"]
        assert result["sources"] == []
