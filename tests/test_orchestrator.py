"""test_orchestrator.py — Tests del agente ReAct orquestador y sus herramientas.

Que se prueba:
1. Estructura de las tools: tienen nombre, descripcion y son invocables.
2. Validacion Pydantic de entrada: textos vacios devuelven "Error de validacion".
3. Comportamiento de classify_risk: formatea clasificacion + checklist de cumplimiento.
4. Comportamiento de search_legal_docs: propaga el pipeline RAG (retrieve->grade->generate).
5. run(): devuelve dict con "messages" usando un agente mockeado.

Estrategia de mocking
langchain_aws, langchain_core y langgraph no estan instalados en venv_proyecto
(son dependencias de produccion/app, no de ML). Se inyectan como MagicMock en
sys.modules antes de importar src.orchestrator.main, igual que hace
test_rag_generate.py con langchain_aws. El teardown_module restaura el estado.

Como ejecutar:
    pytest tests/test_orchestrator.py -v
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Inyeccion de mocks de modulos no instalados en venv_proyecto
# ---------------------------------------------------------------------------

_mocked_modules: dict[str, object] = {}

def _inject_module_mock(name: str) -> MagicMock:
    """Crea un MagicMock y lo registra en sys.modules bajo `name` y subpaths."""
    mock = MagicMock()
    _mocked_modules[name] = sys.modules.get(name)
    sys.modules[name] = mock
    return mock

# langchain_aws
_mock_langchain_aws = _inject_module_mock("langchain_aws")
_mock_langchain_aws.ChatBedrockConverse = MagicMock()

# langchain_core.tools — solo mockeamos el submodulo tools (no el parent
# langchain_core) para no romper imports de langchain_core.messages, .tracers, etc.
# El decorador @tool debe devolver la funcion sin modificarla para que los tests
# puedan llamarla directamente. Usamos un wrapper real (no MagicMock).
def _passthrough_tool(func=None, **kwargs):
    """Stub de @tool: devuelve la funcion con atributos minimos de LangChain tool."""
    if func is None:
        return _passthrough_tool
    func.name = func.__name__
    func.description = func.__doc__ or ""
    func.invoke = lambda input_dict: func(**input_dict)
    return func

_mock_langchain_core_tools = _inject_module_mock("langchain_core.tools")
_mock_langchain_core_tools.tool = _passthrough_tool

# langgraph y subpaquetes
_mock_langgraph = _inject_module_mock("langgraph")
_mock_langgraph_prebuilt = _inject_module_mock("langgraph.prebuilt")
_mock_langgraph_prebuilt.create_react_agent = MagicMock(return_value=MagicMock())
_mock_langgraph_prebuilt.InjectedStore = MagicMock()
_mock_langgraph.prebuilt = _mock_langgraph_prebuilt

# langgraph.checkpoint (SQLite y memoria)
_mock_lg_checkpoint = _inject_module_mock("langgraph.checkpoint")
_mock_lg_checkpoint_sqlite = _inject_module_mock("langgraph.checkpoint.sqlite")
_mock_lg_checkpoint_sqlite.SqliteSaver = MagicMock()
_mock_lg_checkpoint_memory = _inject_module_mock("langgraph.checkpoint.memory")
_mock_lg_checkpoint_memory.InMemorySaver = MagicMock()

# langgraph.store (memoria cross-thread)
_mock_lg_store = _inject_module_mock("langgraph.store")
_mock_lg_store_memory = _inject_module_mock("langgraph.store.memory")
_mock_lg_store_memory.InMemoryStore = MagicMock(return_value=MagicMock())

# Importar el modulo DESPUES de los mocks
import src.orchestrator.main as orch_module  # noqa: E402
from src.orchestrator.main import (  # noqa: E402
    SYSTEM_PROMPT,
    _tool_metadata,
    search_legal_docs,
    classify_risk,
    run,
)


def teardown_module(module):
    """Restaura sys.modules al estado original."""
    for name, original in _mocked_modules.items():
        if original is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = original


# ---------------------------------------------------------------------------
# Grupo 0: SYSTEM_PROMPT contiene las instrucciones legales obligatorias
# ---------------------------------------------------------------------------

class TestSystemPrompt:
    """El prompt del agente incluye los requisitos de dominio no negociables."""

    def test_contiene_disclaimer_legal(self):
        assert "Informe preliminar generado por IA. Consulte profesional juridico." in SYSTEM_PROMPT

    def test_menciona_eu_ai_act(self):
        assert "EU AI Act" in SYSTEM_PROMPT

    def test_instruye_citar_fuentes(self):
        assert "cita" in SYSTEM_PROMPT.lower() or "fuentes" in SYSTEM_PROMPT.lower()

    def test_instruye_usar_herramientas(self):
        assert "herramienta" in SYSTEM_PROMPT.lower()

    def test_describe_classify_risk(self):
        assert "classify_risk" in SYSTEM_PROMPT

    def test_describe_search_legal_docs(self):
        assert "search_legal_docs" in SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Grupo 1: Estructura de las tools
# ---------------------------------------------------------------------------

class TestToolsDefinidas:
    """Las 2 tools tienen nombre correcto y descripcion no vacia."""

    def test_search_legal_docs_nombre(self):
        assert search_legal_docs.name == "search_legal_docs"

    def test_classify_risk_nombre(self):
        assert classify_risk.name == "classify_risk"

    def test_todas_tienen_descripcion(self):
        for t in [search_legal_docs, classify_risk]:
            assert t.description, f"Tool '{t.name}' no tiene descripcion"

    def test_build_agent_expone_solo_dos_tools(self):
        """No-regresion: _build_agent pasa exactamente [search_legal_docs, classify_risk]."""
        with patch.object(orch_module, "ChatBedrockConverse"), \
             patch.object(orch_module, "create_react_agent", return_value=MagicMock()) as mock_create:
            orch_module._build_agent()

        tools = mock_create.call_args.args[1]
        assert [t.name for t in tools] == ["search_legal_docs", "classify_risk"]


# ---------------------------------------------------------------------------
# Grupo 2: Validacion Pydantic de entrada
# ---------------------------------------------------------------------------

class TestValidacionEntrada:
    """Entradas invalidas devuelven 'Error de validacion' sin lanzar excepcion."""

    def test_classify_risk_rechaza_texto_vacio(self):
        result = classify_risk.invoke({"system_description": ""})
        assert "Error" in result

    def test_search_legal_docs_rechaza_query_vacia(self):
        result = search_legal_docs.invoke({"query": ""})
        assert "Error" in result


# ---------------------------------------------------------------------------
# Grupo 3: classify_risk devuelve clasificacion + checklist
# ---------------------------------------------------------------------------

class TestClassifyRiskTool:
    """classify_risk transforma predict_risk en checklist de cumplimiento."""

    def setup_method(self):
        orch_module._cached_predict_risk.cache_clear()

    def teardown_method(self):
        orch_module._cached_predict_risk.cache_clear()

    @patch.object(orch_module, "predict_risk")
    def test_incluye_nivel_de_riesgo(self, mock_predict):
        mock_predict.return_value = {
            "risk_level": "alto_riesgo",
            "confidence": 0.85,
            "probabilities": {},
        }
        result = classify_risk.invoke({"system_description": "sistema de scoring crediticio"})
        assert "ALTO_RIESGO" in result

    @patch.object(orch_module, "predict_risk")
    def test_incluye_confianza(self, mock_predict):
        mock_predict.return_value = {
            "risk_level": "alto_riesgo",
            "confidence": 0.85,
            "probabilities": {},
        }
        result = classify_risk.invoke({"system_description": "sistema de scoring crediticio"})
        assert "85%" in result

    @patch.object(orch_module, "predict_risk")
    def test_incluye_obligaciones(self, mock_predict):
        mock_predict.return_value = {
            "risk_level": "alto_riesgo",
            "confidence": 0.9,
            "probabilities": {},
        }
        result = classify_risk.invoke({"system_description": "scoring crediticio"})
        assert "OBLIGACIONES APLICABLES" in result
        assert "Art. 9" in result

    @patch.object(orch_module, "predict_risk")
    def test_incluye_shap_recommendations(self, mock_predict):
        mock_predict.return_value = {
            "risk_level": "alto_riesgo",
            "confidence": 0.9,
            "probabilities": {},
            "shap_top_features": [{"feature": "crediticio", "contribution": 0.5}],
        }
        result = classify_risk.invoke({"system_description": "scoring crediticio"})
        assert "RECOMENDACIONES ESPECIFICAS" in result
        assert "crediticio" in result

    @patch.object(orch_module, "predict_risk")
    def test_incluye_borderline_warning(self, mock_predict):
        mock_predict.return_value = {
            "risk_level": "alto_riesgo",
            "confidence": 0.72,
            "probabilities": {
                "alto_riesgo": 0.72,
                "inaceptable": 0.22,
                "riesgo_limitado": 0.04,
                "riesgo_minimo": 0.02,
            },
        }
        result = classify_risk.invoke({"system_description": "sistema borderline"})
        assert "ADVERTENCIA BORDERLINE" in result

    @patch.object(orch_module, "predict_risk")
    def test_riesgo_minimo_sin_obligaciones_mandatory(self, mock_predict):
        mock_predict.return_value = {
            "risk_level": "riesgo_minimo",
            "confidence": 0.7,
            "probabilities": {},
        }
        result = classify_risk.invoke({"system_description": "filtro de spam"})
        assert "RIESGO_MINIMO" in result
        assert "[VOLUNTARIO]" in result

    @patch.object(orch_module, "predict_risk")
    def test_incluye_disclaimer(self, mock_predict):
        mock_predict.return_value = {
            "risk_level": "riesgo_minimo",
            "confidence": 0.7,
            "probabilities": {},
        }
        result = classify_risk.invoke({"system_description": "filtro de spam"})
        assert "Informe preliminar generado por IA" in result


# ---------------------------------------------------------------------------
# Grupo 4: search_legal_docs propaga el pipeline RAG
# ---------------------------------------------------------------------------

class TestSearchLegalDocsTool:
    """search_legal_docs llama a retrieve->grade->generate y maneja casos vacios."""

    @patch("src.rag.main.retrieve", return_value=[])
    def test_sin_documentos_devuelve_mensaje(self, _mock):
        result = search_legal_docs.invoke({"query": "que dice el articulo 5?"})
        assert "No se encontraron" in result

    @patch("src.rag.main.grade", return_value=[])
    @patch("src.rag.main.retrieve")
    def test_sin_relevantes_devuelve_mensaje(self, mock_retrieve, _mock_grade):
        mock_retrieve.return_value = [{"doc": "texto", "metadata": {}, "score": 0.3}]
        result = search_legal_docs.invoke({"query": "que dice el articulo 5?"})
        assert "ninguno fue relevante" in result

    @patch("src.rag.main.generate")
    @patch("src.rag.main.grade")
    @patch("src.rag.main.retrieve")
    def test_con_documentos_devuelve_respuesta(self, mock_retrieve, mock_grade, mock_generate):
        mock_retrieve.return_value = [{"doc": "Art. 5 prohibe X", "metadata": {}, "score": 0.9}]
        mock_grade.return_value = [{"doc": "Art. 5 prohibe X", "metadata": {}, "score": 0.9}]
        mock_generate.return_value = {
            "answer": "Segun el Art. 5 del EU AI Act...",
            "sources": [],
            "grounded": True,
        }
        result = search_legal_docs.invoke({"query": "que dice el articulo 5?"})
        assert "Art. 5" in result


# ---------------------------------------------------------------------------
# Grupo 5: run() devuelve dict con messages
# ---------------------------------------------------------------------------

class TestRun:
    """run() invoca el agente y devuelve un dict con 'messages'."""

    def setup_method(self):
        orch_module._agent = None

    def teardown_method(self):
        orch_module._agent = None

    @patch.object(orch_module, "_build_agent")
    def test_devuelve_dict(self, mock_build):
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {"messages": [MagicMock(content="respuesta legal")]}
        mock_build.return_value = mock_agent

        result = run("Que riesgo tiene un chatbot?")
        assert isinstance(result, dict)

    @patch.object(orch_module, "_build_agent")
    def test_devuelve_messages(self, mock_build):
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {"messages": [MagicMock(content="respuesta")]}
        mock_build.return_value = mock_agent

        result = run("consulta sobre EU AI Act")
        assert "messages" in result
        assert len(result["messages"]) > 0

    @patch.object(orch_module, "_build_agent")
    def test_agente_recibe_query(self, mock_build):
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {"messages": [MagicMock(content="ok")]}
        mock_build.return_value = mock_agent

        run("pregunta concreta sobre el Art. 9")

        call_args = mock_agent.invoke.call_args[0][0]
        assert "pregunta concreta sobre el Art. 9" in call_args["messages"][0][1]


# ---------------------------------------------------------------------------
# Grupo 6: Side-channel de metadatos (ContextVar)
# ---------------------------------------------------------------------------

class TestToolMetadata:
    """Las tools depositan metadatos verificados en el side-channel ContextVar."""

    def setup_method(self):
        _tool_metadata.set(None)
        orch_module._agent = None
        orch_module._cached_predict_risk.cache_clear()

    def teardown_method(self):
        _tool_metadata.set(None)
        orch_module._agent = None
        orch_module._cached_predict_risk.cache_clear()

    @patch.object(orch_module, "predict_risk")
    def test_classify_risk_deposita_metadata(self, mock_predict):
        """classify_risk deposita risk_level, confidence y legal_ref en meta['risk']."""
        mock_predict.return_value = {
            "risk_level": "alto_riesgo",
            "confidence": 0.85,
            "annex3_ref": None,
        }
        classify_risk.invoke({"system_description": "sistema de scoring crediticio"})

        meta = _tool_metadata.get(None)
        assert meta is not None
        assert meta["risk"] is not None
        assert meta["risk"]["risk_level"] == "alto_riesgo"
        assert meta["risk"]["confidence"] == 0.85
        assert meta["risk"]["legal_ref"] == "Art. 6 + Anexo III EU AI Act"

    @patch("src.rag.main.generate")
    @patch("src.rag.main.grade")
    @patch("src.rag.main.retrieve")
    def test_search_legal_docs_deposita_citations(self, mock_retrieve, mock_grade, mock_generate):
        """search_legal_docs deposita las fuentes del RAG en meta['citations']."""
        mock_retrieve.return_value = [{"doc": "Art. 5 prohíbe X", "metadata": {}, "score": 0.9}]
        mock_grade.return_value = [{"doc": "Art. 5 prohíbe X", "metadata": {}, "score": 0.9}]
        mock_generate.return_value = {
            "answer": "Según el Art. 5...",
            "sources": [
                {"source": "EU AI Act", "unit_title": "Art. 5", "unit_id": "art_5"},
                {"source": "EU AI Act", "unit_title": "Art. 6", "unit_id": "art_6"},
            ],
            "grounded": True,
        }
        search_legal_docs.invoke({"query": "¿qué prácticas están prohibidas?"})

        meta = _tool_metadata.get(None)
        assert meta is not None
        assert len(meta["citations"]) == 2
        assert meta["citations"][0]["source"] == "EU AI Act"
        assert meta["citations"][0]["unit_title"] == "Art. 5"

    @patch.object(orch_module, "_build_agent")
    def test_run_devuelve_metadata(self, mock_build):
        """run() incluye la key 'metadata' en el resultado."""
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {"messages": [MagicMock(content="respuesta")]}
        mock_build.return_value = mock_agent

        result = run("consulta de prueba")

        assert "metadata" in result
        assert "citations" in result["metadata"]
        assert "risk" in result["metadata"]
        assert "report" in result["metadata"]

    @patch.object(orch_module, "_build_agent")
    def test_run_limpia_metadata_entre_invocaciones(self, mock_build):
        """run() limpia la ContextVar antes de cada invocación."""
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {"messages": [MagicMock(content="ok")]}
        mock_build.return_value = mock_agent

        # Contaminar la ContextVar con datos de una invocación anterior
        _tool_metadata.set({"citations": [{"source": "viejo"}], "risk": {"old": True}, "report": None})

        result = run("nueva consulta")

        # El metadata debe estar limpio (el agente mock no llama tools)
        assert result["metadata"]["citations"] == []
        assert result["metadata"]["risk"] is None


# ---------------------------------------------------------------------------
# Grupo 8: Memoria conversacional — run() pasa thread_id en config
# ---------------------------------------------------------------------------

class TestMemoriaConversacional:
    """run() pasa thread_id y solo envía el mensaje nuevo (con checkpointer)."""

    def setup_method(self):
        orch_module._agent = None

    def teardown_method(self):
        orch_module._agent = None

    @patch.object(orch_module, "_build_agent")
    def test_run_pasa_thread_id(self, mock_build):
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {"messages": [MagicMock(content="respuesta")]}
        mock_build.return_value = mock_agent

        run("hola", session_id="test-session-123")

        call_args = mock_agent.invoke.call_args
        config = call_args[1].get("config") or call_args[0][1]
        assert config["configurable"]["thread_id"] == "test-session-123"

    @patch.object(orch_module, "_build_agent")
    def test_run_usa_default_sin_session_id(self, mock_build):
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {"messages": [MagicMock(content="respuesta")]}
        mock_build.return_value = mock_agent

        run("hola")

        call_args = mock_agent.invoke.call_args
        config = call_args[1].get("config") or call_args[0][1]
        assert config["configurable"]["thread_id"] == "default"

    @patch.object(orch_module, "_build_agent")
    def test_run_solo_envia_mensaje_nuevo(self, mock_build):
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {"messages": [MagicMock(content="respuesta")]}
        mock_build.return_value = mock_agent

        run("segunda pregunta", session_id="session-1")

        call_args = mock_agent.invoke.call_args
        input_data = call_args[0][0]
        assert len(input_data["messages"]) == 1
        assert input_data["messages"][0] == ("user", "segunda pregunta")
