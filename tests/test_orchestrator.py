"""test_orchestrator.py — Tests del agente ReAct orquestador y sus herramientas.

¿Qué se prueba?
1. Estructura de las tools: tienen nombre, descripción y son invocables.
2. Validación Pydantic de entrada: textos vacíos devuelven "Error de validacion".
3. Comportamiento de classify_risk: formatea correctamente la salida de predict_risk.
4. Comportamiento de search_legal_docs: propaga el pipeline RAG (retrieve→grade→generate).
5. Comportamiento de generate_report: clasifica, busca artículos y llama al generador.
6. run(): devuelve dict con "messages" usando un agente mockeado.

Estrategia de mocking
langchain_aws, langchain_core y langgraph no están instalados en venv_proyecto
(son dependencias de producción/app, no de ML). Se inyectan como MagicMock en
sys.modules antes de importar src.orchestrator.main, igual que hace
test_rag_generate.py con langchain_aws. El teardown_module restaura el estado.

¿Cómo ejecutar?
    pytest tests/test_orchestrator.py -v
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Inyección de mocks de módulos no instalados en venv_proyecto
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

# langchain_core y subpaquetes
_mock_langchain_core = _inject_module_mock("langchain_core")
_mock_langchain_core_tools = _inject_module_mock("langchain_core.tools")

# El decorador @tool debe devolver la función sin modificarla para que los tests
# puedan llamarla directamente. Usamos un wrapper real (no MagicMock).
def _passthrough_tool(func=None, **kwargs):
    """Stub de @tool: devuelve la función con atributos mínimos de LangChain tool."""
    if func is None:
        return _passthrough_tool
    func.name = func.__name__
    func.description = func.__doc__ or ""
    func.invoke = lambda input_dict: func(**input_dict)
    return func

_mock_langchain_core_tools.tool = _passthrough_tool
_mock_langchain_core.tools = _mock_langchain_core_tools

# langgraph y subpaquetes
_mock_langgraph = _inject_module_mock("langgraph")
_mock_langgraph_prebuilt = _inject_module_mock("langgraph.prebuilt")
_mock_langgraph_prebuilt.create_react_agent = MagicMock(return_value=MagicMock())
_mock_langgraph.prebuilt = _mock_langgraph_prebuilt

# Importar el módulo DESPUÉS de los mocks
import src.orchestrator.main as orch_module  # noqa: E402
from src.orchestrator.main import (  # noqa: E402
    SYSTEM_PROMPT,
    _tool_metadata,
    search_legal_docs,
    classify_risk,
    generate_report,
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
        """Requisito de dominio: toda respuesta debe indicar que es un informe preliminar."""
        assert "Informe preliminar generado por IA. Consulte profesional jurídico." in SYSTEM_PROMPT

    def test_menciona_eu_ai_act(self):
        """El agente debe saber que su dominio es el EU AI Act y el BOE."""
        assert "EU AI Act" in SYSTEM_PROMPT

    def test_instruye_citar_fuentes(self):
        """El agente debe citar fuentes legales exactas, no responder de memoria."""
        assert "fuentes" in SYSTEM_PROMPT.lower() or "cita" in SYSTEM_PROMPT.lower()

    def test_instruye_usar_herramientas(self):
        """El agente debe usar las herramientas disponibles antes de responder."""
        assert "herramienta" in SYSTEM_PROMPT.lower()

    def test_generate_report_docstring_indica_clasificacion_interna(self):
        """BUG-04: el docstring de generate_report debe advertir que clasifica internamente."""
        assert "clasifica" in generate_report.description.lower() or "clasificación" in generate_report.description.lower()
        assert "no es necesario" in generate_report.description.lower() or "no llam" in generate_report.description.lower()


# ---------------------------------------------------------------------------
# Grupo 1: Estructura de las tools
# ---------------------------------------------------------------------------

class TestToolsDefinidas:
    """Las 3 tools tienen nombre correcto y descripción no vacía."""

    def test_search_legal_docs_nombre(self):
        assert search_legal_docs.name == "search_legal_docs"

    def test_classify_risk_nombre(self):
        assert classify_risk.name == "classify_risk"

    def test_generate_report_nombre(self):
        assert generate_report.name == "generate_report"

    def test_todas_tienen_descripcion(self):
        for t in [search_legal_docs, classify_risk, generate_report]:
            assert t.description, f"Tool '{t.name}' no tiene descripción"


# ---------------------------------------------------------------------------
# Grupo 2: Validación Pydantic de entrada
# ---------------------------------------------------------------------------

class TestValidacionEntrada:
    """Entradas inválidas devuelven 'Error de validacion' sin lanzar excepción."""

    def test_classify_risk_rechaza_texto_vacio(self):
        result = classify_risk.invoke({"system_description": ""})
        assert "Error" in result

    def test_search_legal_docs_rechaza_query_vacia(self):
        result = search_legal_docs.invoke({"query": ""})
        assert "Error" in result

    def test_generate_report_rechaza_texto_vacio(self):
        result = generate_report.invoke({"system_description": ""})
        assert "Error" in result


# ---------------------------------------------------------------------------
# Grupo 3: classify_risk formatea la respuesta de predict_risk
# ---------------------------------------------------------------------------

class TestClassifyRiskTool:
    """classify_risk transforma el dict de predict_risk en texto legible."""

    def setup_method(self):
        orch_module._cached_predict_risk.cache_clear()

    def teardown_method(self):
        orch_module._cached_predict_risk.cache_clear()

    @patch.object(orch_module, "predict_risk")
    def test_risk_level_en_mayusculas(self, mock_predict):
        mock_predict.return_value = {"risk_level": "alto_riesgo", "confidence": 0.85}
        result = classify_risk.invoke({"system_description": "sistema de scoring crediticio"})
        assert "ALTO_RIESGO" in result

    @patch.object(orch_module, "predict_risk")
    def test_confianza_formateada_como_porcentaje(self, mock_predict):
        mock_predict.return_value = {"risk_level": "alto_riesgo", "confidence": 0.85}
        result = classify_risk.invoke({"system_description": "sistema de scoring crediticio"})
        assert "85%" in result

    @patch.object(orch_module, "predict_risk")
    def test_incluye_shap_cuando_disponible(self, mock_predict):
        mock_predict.return_value = {
            "risk_level": "alto_riesgo",
            "confidence": 0.9,
            "shap_top_features": [{"feature": "crediticio", "contribution": 0.5}],
            "shap_explanation": "Factores principales: crediticio.",
        }
        result = classify_risk.invoke({"system_description": "scoring crediticio"})
        assert "crediticio" in result

    @patch.object(orch_module, "predict_risk")
    def test_sin_shap_no_lanza_error(self, mock_predict):
        mock_predict.return_value = {"risk_level": "riesgo_minimo", "confidence": 0.7}
        result = classify_risk.invoke({"system_description": "filtro de spam"})
        assert "RIESGO_MINIMO" in result

    @patch.object(orch_module, "predict_risk")
    def test_svd_features_excluidas_de_factores_clave(self, mock_predict):
        """Cuando el modelo devuelve features SVD, la respuesta al LLM no las incluye.

        Las componentes SVD (svd_0, svd_42) no tienen significado legal para el usuario
        ni para el LLM. Si se incluyeran, la respuesta sería: 'Factores clave: svd_3,
        svd_17' — completamente inútil. El orquestador filtra estos términos.
        """
        mock_predict.return_value = {
            "risk_level": "alto_riesgo",
            "confidence": 0.88,
            "shap_top_features": [
                {"feature": "svd_3", "contribution": 0.42},
                {"feature": "svd_17", "contribution": 0.31},
                {"feature": "num_palabras", "contribution": 0.15},
            ],
        }
        result = classify_risk.invoke({"system_description": "sistema de scoring crediticio"})
        assert "svd_" not in result
        assert "num_palabras" not in result
        # Al no haber features interpretables, la sección entera debe omitirse
        assert "Factores clave" not in result

    @patch.object(orch_module, "predict_risk")
    def test_override_activo_no_incluye_factores_clave_ml(self, mock_predict):
        """Con override activo, la respuesta no incluye features ML de la clase equivocada.

        Scenario: ML predijo 'riesgo_minimo' pero Anexo III fuerza 'inaceptable'.
        Los features ML (para riesgo_minimo) no deben aparecer junto a 'INACEPTABLE'
        porque producirían inputs contradictorios: el LLM recibiría una explicación
        para la clase incorrecta.
        _annex3_override mueve shap_top_features a ml_prediction — por eso
        result.get("shap_top_features", []) devuelve [] y "Factores clave" se omite.
        """
        mock_predict.return_value = {
            "risk_level": "inaceptable",
            "confidence": 0.85,
            "annex3_override": True,
            "annex3_ref": "Art. 5.1.d",
            # shap_top_features ausente en nivel raíz (movido a ml_prediction)
            "ml_prediction": {
                "risk_level": "riesgo_minimo",
                "confidence": 0.62,
                "shap_top_features": [{"feature": "filtro", "contribution": 0.3}],
            },
        }
        result = classify_risk.invoke({"system_description": "reconocimiento facial en espacios públicos"})
        assert "INACEPTABLE" in result
        # Features del ML (que clasificó mal) no deben contaminar la respuesta
        assert "Factores clave" not in result


# ---------------------------------------------------------------------------
# Grupo 4: search_legal_docs propaga el pipeline RAG
# ---------------------------------------------------------------------------

class TestSearchLegalDocsTool:
    """search_legal_docs llama a retrieve→grade→generate y maneja casos vacíos."""

    @patch("src.rag.main.retrieve", return_value=[])
    def test_sin_documentos_devuelve_mensaje(self, _mock):
        result = search_legal_docs.invoke({"query": "¿qué dice el artículo 5?"})
        assert "No se encontraron" in result

    @patch("src.rag.main.grade", return_value=[])
    @patch("src.rag.main.retrieve")
    def test_sin_relevantes_devuelve_mensaje(self, mock_retrieve, _mock_grade):
        mock_retrieve.return_value = [{"doc": "texto", "metadata": {}, "score": 0.3}]
        result = search_legal_docs.invoke({"query": "¿qué dice el artículo 5?"})
        assert "ninguno fue relevante" in result

    @patch("src.rag.main.generate")
    @patch("src.rag.main.grade")
    @patch("src.rag.main.retrieve")
    def test_con_documentos_devuelve_respuesta(self, mock_retrieve, mock_grade, mock_generate):
        mock_retrieve.return_value = [{"doc": "Art. 5 prohíbe X", "metadata": {}, "score": 0.9}]
        mock_grade.return_value = [{"doc": "Art. 5 prohíbe X", "metadata": {}, "score": 0.9}]
        mock_generate.return_value = {
            "answer": "Según el Art. 5 del EU AI Act...",
            "sources": [],
            "grounded": True,
        }
        result = search_legal_docs.invoke({"query": "¿qué dice el artículo 5?"})
        assert "Art. 5" in result


# ---------------------------------------------------------------------------
# Grupo 5: generate_report clasifica y construye el informe
# ---------------------------------------------------------------------------

class TestGenerateReportTool:
    """generate_report llama a predict_risk, retriever y report.generate_report."""

    def setup_method(self):
        orch_module._cached_predict_risk.cache_clear()

    def teardown_method(self):
        orch_module._cached_predict_risk.cache_clear()

    @patch("src.report.main.generate_report")
    @patch("src.retrieval.retriever.search")
    @patch.object(orch_module, "predict_risk")
    def test_genera_informe(self, mock_predict, mock_search, mock_report):
        mock_predict.return_value = {"risk_level": "alto_riesgo", "confidence": 0.9}
        mock_search.return_value = []
        mock_report.return_value = "## Informe de Cumplimiento\n..."

        result = generate_report.invoke({"system_description": "sistema de scoring crediticio"})

        assert result
        mock_report.assert_called_once()

    @patch("src.report.main.generate_report")
    @patch("src.retrieval.retriever.search")
    @patch.object(orch_module, "predict_risk")
    def test_pasa_risk_level_al_informe(self, mock_predict, mock_search, mock_report):
        mock_predict.return_value = {"risk_level": "inaceptable", "confidence": 0.95}
        mock_search.return_value = []
        mock_report.return_value = "## Informe\n..."

        generate_report.invoke({"system_description": "sistema de puntuación social"})

        call_args = mock_report.call_args
        assert call_args[0][1] == "inaceptable"

    @patch("src.report.main.generate_report")
    @patch("src.retrieval.retriever.search")
    @patch.object(orch_module, "predict_risk")
    def test_report_alto_riesgo_busca_multiples_articulos(self, mock_predict, mock_search, mock_report):
        """Para alto_riesgo se hace una búsqueda por cada obligación (6 queries con k=1)."""
        mock_predict.return_value = {"risk_level": "alto_riesgo", "confidence": 0.9}
        mock_search.return_value = [
            {"id": "unique", "text": "texto", "metadata": {"source": "EU AI Act", "unit_title": "Art. X"}},
        ]
        mock_report.return_value = "## Informe\n..."

        generate_report.invoke({"system_description": "sistema de scoring crediticio"})

        # alto_riesgo tiene 6 queries en _REPORT_QUERIES → 6 llamadas a search
        assert mock_search.call_count == 6
        # Cada llamada debe usar k=1
        for call in mock_search.call_args_list:
            assert call[1].get("k", call[0][1] if len(call[0]) > 1 else None) == 1

    @patch("src.report.main.generate_report")
    @patch("src.retrieval.retriever.search")
    @patch.object(orch_module, "predict_risk")
    def test_report_deduplica_resultados(self, mock_predict, mock_search, mock_report):
        """Si dos queries devuelven el mismo doc_id, el artículo no se duplica."""
        mock_predict.return_value = {"risk_level": "alto_riesgo", "confidence": 0.9}
        # Todas las queries devuelven el mismo documento (mismo id)
        mock_search.return_value = [
            {"id": "chunk_42", "text": "texto legal", "metadata": {"source": "EU AI Act", "unit_title": "Art. 9"}},
        ]
        mock_report.return_value = "## Informe\n..."

        generate_report.invoke({"system_description": "sistema de scoring crediticio"})

        # Se llamó a _build_report con articles; como todos tienen el mismo id,
        # solo debe haber 1 artículo (no 6 duplicados)
        call_args = mock_report.call_args
        articles_arg = call_args[0][2]
        assert len(articles_arg) == 1


# ---------------------------------------------------------------------------
# Grupo 5b: BUG-04 — caché evita doble computación classify+report
# ---------------------------------------------------------------------------

class TestNoDobleClasificacion:
    """BUG-04: predict_risk no debe ejecutarse dos veces si classify_risk
    y generate_report reciben la misma descripción en la misma sesión.

    El lru_cache de _cached_predict_risk garantiza que la segunda llamada
    devuelve el resultado cacheado sin volver a ejecutar el modelo ML.
    """

    def setup_method(self):
        orch_module._cached_predict_risk.cache_clear()

    def teardown_method(self):
        orch_module._cached_predict_risk.cache_clear()

    @patch("src.report.main.generate_report")
    @patch("src.retrieval.retriever.search")
    @patch.object(orch_module, "predict_risk")
    def test_predict_risk_llamado_una_sola_vez(self, mock_predict, mock_search, mock_report):
        """predict_risk se ejecuta una sola vez aunque classify_risk y generate_report reciban el mismo input."""
        mock_predict.return_value = {"risk_level": "alto_riesgo", "confidence": 0.9}
        mock_search.return_value = []
        mock_report.return_value = "## Informe\n..."

        descripcion = "sistema de evaluacion de solvencia crediticia para prestamos"
        classify_risk.invoke({"system_description": descripcion})
        generate_report.invoke({"system_description": descripcion})

        mock_predict.assert_called_once_with(descripcion)

    @patch("src.report.main.generate_report")
    @patch("src.retrieval.retriever.search")
    @patch.object(orch_module, "predict_risk")
    def test_inputs_distintos_llaman_predict_risk_dos_veces(self, mock_predict, mock_search, mock_report):
        """Si el LLM pasa strings distintos a classify_risk y generate_report,
        la caché no puede evitar la doble llamada. Este test documenta el
        comportamiento esperado (limitación conocida de lru_cache por string exacto).
        """
        mock_predict.return_value = {"risk_level": "alto_riesgo", "confidence": 0.9}
        mock_search.return_value = []
        mock_report.return_value = "## Informe\n..."

        classify_risk.invoke({"system_description": "sistema de scoring crediticio"})
        # Input ligeramente diferente (como podría hacer el LLM)
        generate_report.invoke({"system_description": "Sistema de scoring crediticio."})

        assert mock_predict.call_count == 2


# ---------------------------------------------------------------------------
# Grupo 6: run() devuelve dict con messages
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

        result = run("¿Qué riesgo tiene un chatbot?")
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
# Grupo 7: Side-channel de metadatos (ContextVar)
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
