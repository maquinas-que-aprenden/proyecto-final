"""test_orchestrator.py — Smoke tests del orquestador ReAct de NormaBot.

¿Qué se está probando aquí?
============================
Este módulo valida ``run(query) -> dict``, el punto de entrada del orquestador,
y las tres herramientas que el agente ReAct puede invocar:
``search_legal_docs``, ``classify_risk`` y ``generate_report``.

¿Por qué smoke tests y no unit tests puros?
============================================
El orquestador depende de Amazon Bedrock (no disponible en CI) y de LangGraph
para crear el agente ReAct. Mockeamos el agente completo para verificar que:
  - El contrato de ``run()`` es estable (devuelve dict con ``messages``).
  - Las herramientas rechazan entradas inválidas antes de llamar a servicios externos.
  - ``classify_risk`` formatea correctamente la salida de ``predict_risk()``.
  - El SYSTEM_PROMPT contiene las instrucciones legales obligatorias.

¿Cómo ejecutarlos?
==================
    pytest tests/test_orchestrator.py -v
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

# Inyectar mocks antes de importar src.orchestrator.main,
# ya que langchain_aws no está instalado en el entorno de test.
_mock_langchain_aws = MagicMock()
_previous_langchain_aws = sys.modules.get("langchain_aws")
sys.modules["langchain_aws"] = _mock_langchain_aws

# langchain_ollama es importado transitivamente por src.rag.main
_mock_langchain_ollama = MagicMock()
_previous_langchain_ollama = sys.modules.get("langchain_ollama")
sys.modules["langchain_ollama"] = _mock_langchain_ollama

import src.orchestrator.main as orch_module  # noqa: E402
from src.orchestrator.main import (  # noqa: E402
    SYSTEM_PROMPT,
    classify_risk,
    generate_report,
    run,
    search_legal_docs,
)


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
# 1. SYSTEM_PROMPT contiene instrucciones clave
# ---------------------------------------------------------------------------


class TestSystemPrompt:
    def test_contiene_disclaimer(self):
        """El prompt debe instruir al agente a añadir el disclaimer legal."""
        assert "profesional jurídico" in SYSTEM_PROMPT

    def test_menciona_eu_ai_act(self):
        """El agente debe saber que su dominio es el EU AI Act."""
        assert "EU AI Act" in SYSTEM_PROMPT

    def test_instruye_citar_fuentes(self):
        """El agente debe citar fuentes legales en sus respuestas."""
        assert "fuentes" in SYSTEM_PROMPT.lower() or "cita" in SYSTEM_PROMPT.lower()

    def test_instruye_usar_herramientas(self):
        """El agente debe usar las herramientas disponibles, no responder de memoria."""
        assert "herramienta" in SYSTEM_PROMPT.lower()


# ---------------------------------------------------------------------------
# 2. Singleton _get_agent()
# ---------------------------------------------------------------------------


class TestAgenteSingleton:
    def setup_method(self):
        """Resetea el singleton antes de cada test."""
        orch_module._agent = None

    def teardown_method(self):
        """Limpia el singleton después de cada test."""
        orch_module._agent = None

    def test_singleton_devuelve_misma_instancia(self):
        """Dos llamadas a _get_agent() deben devolver el mismo objeto."""
        mock_agent = MagicMock()
        with patch.object(orch_module, "_build_agent", return_value=mock_agent):
            first = orch_module._get_agent()
            second = orch_module._get_agent()
        assert first is second

    def test_singleton_construye_una_sola_vez(self):
        """_build_agent() solo se llama una vez aunque _get_agent() se llame varias."""
        mock_agent = MagicMock()
        with patch.object(orch_module, "_build_agent", return_value=mock_agent) as mock_build:
            orch_module._get_agent()
            orch_module._get_agent()
            orch_module._get_agent()
        mock_build.assert_called_once()


# ---------------------------------------------------------------------------
# 3. run() — estructura del resultado
# ---------------------------------------------------------------------------


class TestRunEstructura:
    def setup_method(self):
        orch_module._agent = None

    def teardown_method(self):
        orch_module._agent = None

    def _make_mock_agent(self, content="Respuesta. Consulte profesional jurídico."):
        mock_msg = MagicMock()
        mock_msg.content = content
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {"messages": [mock_msg]}
        return mock_agent

    def test_run_devuelve_dict(self):
        """run() debe devolver un dict (contrato con app.py)."""
        with patch.object(orch_module, "_get_agent", return_value=self._make_mock_agent()):
            result = run("¿Qué es el EU AI Act?")
        assert isinstance(result, dict)

    def test_run_tiene_messages(self):
        """El dict debe tener la clave 'messages' con al menos un mensaje."""
        with patch.object(orch_module, "_get_agent", return_value=self._make_mock_agent()):
            result = run("¿Qué es el EU AI Act?")
        assert "messages" in result
        assert len(result["messages"]) > 0

    def test_ultimo_mensaje_tiene_content(self):
        """El último mensaje debe tener atributo content de tipo string."""
        with patch.object(orch_module, "_get_agent", return_value=self._make_mock_agent()):
            result = run("¿Qué es el EU AI Act?")
        last = result["messages"][-1]
        assert hasattr(last, "content")
        assert isinstance(last.content, str)


# ---------------------------------------------------------------------------
# 4. Validación de entrada de las herramientas
# ---------------------------------------------------------------------------


class TestToolValidacion:
    """Las tools deben rechazar entradas inválidas antes de llamar a servicios externos."""

    def test_search_legal_docs_rechaza_query_vacia(self):
        result = search_legal_docs.invoke({"query": ""})
        assert "error" in result.lower()

    def test_classify_risk_rechaza_descripcion_vacia(self):
        result = classify_risk.invoke({"system_description": ""})
        assert "error" in result.lower()

    def test_generate_report_rechaza_descripcion_vacia(self):
        result = generate_report.invoke({"system_description": ""})
        assert "error" in result.lower()


# ---------------------------------------------------------------------------
# 5. classify_risk — formato de la respuesta
# ---------------------------------------------------------------------------


class TestClassifyRiskOutput:
    def test_devuelve_clasificacion_y_confianza(self):
        """La tool debe formatear el nivel de riesgo y la confianza en texto legible."""
        mock_result = {
            "risk_level": "alto_riesgo",
            "confidence": 0.85,
            "probabilities": {},
        }
        with patch("src.orchestrator.main.predict_risk", return_value=mock_result):
            output = classify_risk.invoke(
                {"system_description": "sistema de reconocimiento facial"}
            )
        assert "ALTO_RIESGO" in output
        assert "85%" in output

    def test_no_explota_sin_shap(self):
        """Sin shap_top_features en el resultado, la tool no debe lanzar excepción."""
        mock_result = {
            "risk_level": "riesgo_minimo",
            "confidence": 0.90,
            "probabilities": {},
        }
        with patch("src.orchestrator.main.predict_risk", return_value=mock_result):
            output = classify_risk.invoke({"system_description": "filtro de spam para email"})
        assert "RIESGO_MINIMO" in output
