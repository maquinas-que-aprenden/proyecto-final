"""test_classifier.py — Smoke tests del servicio de clasificación de riesgo EU AI Act.

¿Qué se está probando aquí?
============================
Este módulo valida ``predict_risk(text) -> dict``, la función que expone el
clasificador de riesgo como servicio para el orquestador ReAct.

La función hace cuatro cosas encadenadas:

  1. Validación de entrada (Pydantic ``_TextInput``)
  2. Carga lazy del modelo serializado (``mejor_modelo.joblib`` + ``tfidf_vectorizer``)
  3. Preprocesado del texto (limpieza spaCy o fallback regex → TF-IDF)
  4. Predicción + explicabilidad (probabilidades + contribuciones lineales por feature)

¿Por qué smoke tests y no unit tests puros?
============================================
El clasificador depende de artefactos serializados en disco (archivos ``.joblib``).
Mockear el modelo para tests unitarios puro añadiría complejidad sin beneficio real
en esta fase del proyecto: lo que importa para la demo es que el pipeline completo
funciona con el modelo entrenado real.

Los smoke tests aquí:
  - Cargan el modelo real desde ``classifier_dataset_artificial/model/``.
  - Verifican que ninguna entrada razonable lanza una excepción.
  - Comprueban que la estructura de respuesta es siempre correcta.
  - NO asertan la clase predicha para un texto concreto (el modelo puede variar
    entre reentrenamientos; lo que debe ser estable es la estructura, no el valor).

¿Cómo ejecutarlos?
==================
Desde la raíz del proyecto::

    pytest tests/test_classifier.py -v

Para ver también los logs de carga del modelo::

    pytest tests/test_classifier.py -v -s

Dependencias necesarias:
  - joblib, numpy, scipy, pydantic  (requirements/ml.txt)
  - spaCy ``es_core_news_sm`` (opcional — fallback a regex si no está disponible)
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from src.classifier.main import predict_risk, predict_risk_bert

# Conjunto de niveles de riesgo válidos según el EU AI Act (EU 2024/1689).
# Son los valores que el clasificador puede devolver en ``risk_level``.
RISK_LEVELS = {"inaceptable", "alto_riesgo", "riesgo_limitado", "riesgo_minimo"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def resultado_facial():
    """Resultado de clasificar un sistema de reconocimiento facial.

    Scope ``module`` para evitar cargar el modelo dos veces en tests del mismo
    módulo. El modelo se inicializa en el primer uso (lazy loading thread-safe)
    y queda en memoria para el resto de la sesión de pytest.
    """
    return predict_risk("sistema de reconocimiento facial en aeropuertos para control de acceso")


# ---------------------------------------------------------------------------
# Grupo 1: Estructura del resultado
# ---------------------------------------------------------------------------

class TestEstructuraRespuesta:
    """Verifica que predict_risk siempre devuelve un dict con las claves correctas.

    Estos tests son los más importantes: si la estructura cambia, el orquestador
    (``src/orchestrator/main.py``, tool ``classify_risk``) dejará de funcionar.
    """

    def test_devuelve_dict(self, resultado_facial):
        """La función debe devolver un dict, nunca None ni otro tipo."""
        assert isinstance(resultado_facial, dict)

    def test_contiene_risk_level(self, resultado_facial):
        """``risk_level`` es la clave principal que consume el orquestador."""
        assert "risk_level" in resultado_facial

    def test_contiene_confidence(self, resultado_facial):
        """``confidence`` es la probabilidad máxima entre las 4 clases."""
        assert "confidence" in resultado_facial

    def test_contiene_probabilities(self, resultado_facial):
        """``probabilities`` expone la distribución completa para análisis."""
        assert "probabilities" in resultado_facial

    def test_risk_level_es_valor_valido(self, resultado_facial):
        """``risk_level`` debe ser una de las 4 categorías EU AI Act."""
        assert resultado_facial["risk_level"] in RISK_LEVELS

    def test_confidence_es_probabilidad(self, resultado_facial):
        """``confidence`` debe estar en [0, 1]."""
        c = resultado_facial["confidence"]
        assert isinstance(c, float)
        assert 0.0 <= c <= 1.0

    def test_probabilities_suman_uno(self, resultado_facial):
        """Las probabilidades de las 4 clases deben sumar 1 (±0.01 por redondeo)."""
        total = sum(resultado_facial["probabilities"].values())
        assert abs(total - 1.0) < 0.01

    def test_probabilities_cubre_todas_las_clases(self, resultado_facial):
        """El dict de probabilidades debe tener una entrada por cada clase."""
        assert set(resultado_facial["probabilities"].keys()) == RISK_LEVELS


# ---------------------------------------------------------------------------
# Grupo 2: Casos de entrada variados (robustez)
# ---------------------------------------------------------------------------

class TestRobustez:
    """Verifica que predict_risk no lanza excepciones con entradas diversas.

    El clasificador recibirá textos de usuarios reales a través del orquestador.
    Estos tests aseguran que ninguna entrada razonable rompe el pipeline.
    """

    def test_texto_largo(self):
        """Un sistema descrito con muchos detalles no debe provocar errores."""
        texto = (
            "Sistema automatizado de vigilancia biométrica en espacios públicos "
            "que utiliza reconocimiento facial en tiempo real para identificar "
            "personas en listas de seguimiento policial, integrado con cámaras "
            "de circuito cerrado en estaciones de metro, aeropuertos y centros "
            "comerciales, con capacidad de procesamiento de más de 10.000 rostros "
            "por hora y alertas automáticas a las fuerzas de seguridad."
        )
        resultado = predict_risk(texto)
        assert resultado["risk_level"] in RISK_LEVELS

    def test_texto_corto(self):
        """Texto muy corto (dos palabras) debe clasificarse sin excepción."""
        resultado = predict_risk("IA médica")
        assert resultado["risk_level"] in RISK_LEVELS

    def test_texto_sin_keywords_dominio(self):
        """Texto sin palabras clave del EU AI Act debe devolver igualmente una clase."""
        resultado = predict_risk("software de gestión de inventario para almacenes")
        assert resultado["risk_level"] in RISK_LEVELS

    def test_texto_en_ingles(self):
        """El modelo se entrenó en español, pero no debe explotar con texto en inglés."""
        resultado = predict_risk("facial recognition system for airport security")
        assert resultado["risk_level"] in RISK_LEVELS

    def test_llamadas_consecutivas_consistentes(self):
        """Llamar dos veces con el mismo texto debe dar el mismo resultado.

        Verifica que el lazy loading no altera el estado entre llamadas.
        """
        texto = "chatbot de atención al cliente para tienda online"
        r1 = predict_risk(texto)
        r2 = predict_risk(texto)
        assert r1["risk_level"] == r2["risk_level"]
        assert r1["confidence"] == r2["confidence"]


# ---------------------------------------------------------------------------
# Grupo 3: Explicabilidad
# ---------------------------------------------------------------------------

class TestExplicabilidad:
    """Verifica la estructura de la explicabilidad cuando está disponible.

    La explicabilidad es opcional: si el modelo no tiene ``coef_`` (e.g., XGBoost
    sin LinearExplainer), se omite sin error. Estos tests son condicionales.
    """

    def test_shap_top_features_es_lista(self, resultado_facial):
        """Si ``shap_top_features`` existe, debe ser una lista."""
        if "shap_top_features" not in resultado_facial:
            pytest.skip("Explicabilidad no disponible para este modelo")
        assert isinstance(resultado_facial["shap_top_features"], list)

    def test_shap_top_features_no_vacio(self, resultado_facial):
        """La lista de features influyentes no debe estar vacía."""
        if "shap_top_features" not in resultado_facial:
            pytest.skip("Explicabilidad no disponible para este modelo")
        assert len(resultado_facial["shap_top_features"]) > 0

    def test_shap_feature_tiene_claves_correctas(self, resultado_facial):
        """Cada feature debe tener ``feature`` (nombre) y ``contribution`` (valor)."""
        if "shap_top_features" not in resultado_facial:
            pytest.skip("Explicabilidad no disponible para este modelo")
        for item in resultado_facial["shap_top_features"]:
            assert "feature" in item, f"Falta clave 'feature' en: {item}"
            assert "contribution" in item, f"Falta clave 'contribution' en: {item}"
            assert isinstance(item["feature"], str)
            assert isinstance(item["contribution"], float)

    def test_shap_explanation_es_string(self, resultado_facial):
        """``shap_explanation`` debe ser un string legible para el usuario."""
        if "shap_explanation" not in resultado_facial:
            pytest.skip("Explicabilidad no disponible para este modelo")
        assert isinstance(resultado_facial["shap_explanation"], str)
        assert len(resultado_facial["shap_explanation"]) > 0

    def test_shap_top_features_contiene_al_menos_un_feature_interpretable(self, resultado_facial):
        """shap_top_features puede incluir features SVD (internos del modelo XGBoost+SVD),
        pero debe existir al menos uno interpretable para que shap_explanation tenga
        contenido significativo.

        Los svd_N son componentes de reducción de dimensionalidad — representan
        combinaciones lineales del vocabulario, no palabras. Si todos los top features
        son SVD, el usuario no recibiría ninguna explicación legible.
        La explicabilidad final (shap_explanation) excluye svd_* via filtrado,
        por lo que este test verifica que el filtrado tiene "algo con qué trabajar".
        """
        if "shap_top_features" not in resultado_facial:
            pytest.skip("Explicabilidad no disponible para este modelo")
        _ILEGIBLES = {"num_palabras", "num_caracteres"}
        features_legibles = [
            f for f in resultado_facial["shap_top_features"]
            if not f["feature"].startswith("svd_") and f["feature"] not in _ILEGIBLES
        ]
        assert len(features_legibles) > 0, (
            "Todos los top features son componentes SVD o métricas internas. "
            "El usuario no recibirá ninguna explicación significativa. "
            f"Features actuales: {[f['feature'] for f in resultado_facial['shap_top_features']]}"
        )

    def test_shap_explanation_no_contiene_svd(self, resultado_facial):
        """El string shap_explanation no debe mencionar componentes SVD.

        Bug latente: si el pipeline activo es tfidf_svd, shap_explanation podría
        decir 'Factores principales para alto_riesgo: svd_3, svd_42' — un string
        inútil que el LLM recibiría como explicación. El fix filtra estos términos
        antes de construir el string.
        """
        if "shap_explanation" not in resultado_facial:
            pytest.skip("Explicabilidad no disponible para este modelo")
        assert "svd_" not in resultado_facial["shap_explanation"], (
            "shap_explanation contiene nombres de componentes SVD ilegibles: "
            f"'{resultado_facial['shap_explanation']}'"
        )


# ---------------------------------------------------------------------------
# Grupo 4: Validación de entrada (Pydantic)
# ---------------------------------------------------------------------------

class TestValidacionEntrada:
    """Verifica que entradas inválidas se rechazan antes de llegar al modelo.

    ``predict_risk`` usa ``_TextInput`` (Pydantic BaseModel) para validar.
    Esto protege el pipeline de entradas que romperían el TF-IDF o el modelo.
    """

    def test_texto_vacio_lanza_excepcion(self):
        """Un string vacío debe lanzar ValidationError de Pydantic."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            predict_risk("")

    def test_texto_demasiado_largo_lanza_excepcion(self):
        """Un texto de más de 5000 caracteres debe lanzar ValidationError."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            predict_risk("a" * 5001)


# ---------------------------------------------------------------------------
# Grupo 5: Annex III override — coherencia de campos post-override
# ---------------------------------------------------------------------------

# Resultado ML intencionalmente incorrecto para forzar el override en tests.
# La función _annex3_override solo actúa cuando result["risk_level"] != best_level,
# así que necesitamos un resultado ML que difiera del nivel que dicta el Anexo III.
_MOCK_RESULT_ML = {
    "risk_level": "riesgo_minimo",     # ML equivocado
    "confidence": 0.62,
    "probabilities": {
        "inaceptable": 0.05,
        "alto_riesgo": 0.20,
        "riesgo_limitado": 0.13,
        "riesgo_minimo": 0.62,
    },
    "shap_top_features": [{"feature": "chatbot", "contribution": 0.3}],
}


class TestAnnex3Override:
    """Verifica que _annex3_override produce campos coherentes cuando actúa.

    Este grupo cierra BUG-01: antes del fix, probabilities no se recalibraban
    tras el override y podían contradecir risk_level.

    Se testea _annex3_override directamente (unit tests) para no depender de
    lo que el modelo ML prediga en cada reentrenamiento. Los textos elegidos
    activan patrones del Anexo III de forma determinista.
    """

    @pytest.fixture(scope="class")
    def override_recidiva(self):
        """Override aplicado a texto de recidiva con predicción ML incorrecta."""
        from src.classifier.main import _annex3_override
        texto = "evaluación del riesgo de recidiva para recomendar libertad condicional"
        return _annex3_override(texto, _MOCK_RESULT_ML.copy())

    @pytest.fixture(scope="class")
    def override_biometrico(self):
        """Override aplicado a texto biométrico con predicción ML incorrecta."""
        from src.classifier.main import _annex3_override
        texto = (
            "reconocimiento facial en tiempo real en espacios públicos "
            "para identificación de personas"
        )
        return _annex3_override(texto, _MOCK_RESULT_ML.copy())

    def test_override_activo_en_recidiva(self, override_recidiva):
        """_annex3_override debe activar annex3_override=True para texto de recidiva."""
        assert override_recidiva.get("annex3_override") is True

    def test_risk_level_corregido_a_alto_riesgo(self, override_recidiva):
        """El texto de recidiva debe sobreescribirse a alto_riesgo (Anexo III cat. 6)."""
        assert override_recidiva["risk_level"] == "alto_riesgo"

    def test_probabilities_coherentes_tras_override_recidiva(self, override_recidiva):
        """probabilities[risk_level] debe ser el valor máximo del dict tras override."""
        nivel = override_recidiva["risk_level"]
        probs = override_recidiva["probabilities"]
        assert probs[nivel] == max(probs.values()), (
            f"BUG-01: probabilities no coherentes: risk_level='{nivel}' "
            f"pero max prob es '{max(probs, key=probs.get)}'"
        )

    def test_confidence_igual_a_prob_del_nivel_asignado(self, override_recidiva):
        """confidence debe coincidir con probabilities[risk_level] tras override."""
        nivel = override_recidiva["risk_level"]
        probs = override_recidiva["probabilities"]
        assert override_recidiva["confidence"] == probs[nivel]

    def test_probabilities_suman_uno_tras_override(self, override_recidiva):
        """Las probabilities recalibradas deben sumar 1 (±0.02 por redondeo)."""
        total = sum(override_recidiva["probabilities"].values())
        assert abs(total - 1.0) < 0.02

    def test_ml_prediction_preserva_risk_level_original(self, override_recidiva):
        """ml_prediction debe guardar el risk_level que el ML predijo antes del override."""
        ml = override_recidiva.get("ml_prediction", {})
        assert ml.get("risk_level") == "riesgo_minimo"

    def test_ml_prediction_preserva_probabilidades_originales(self, override_recidiva):
        """ml_prediction debe incluir las probabilities ML originales para trazabilidad."""
        ml = override_recidiva.get("ml_prediction", {})
        assert "probabilities" in ml, "ml_prediction debe incluir 'probabilities'"
        assert set(ml["probabilities"].keys()) == RISK_LEVELS
        # Las probabilidades originales deben ser las del mock (ML incorrecto)
        assert ml["probabilities"]["riesgo_minimo"] == 0.62

    def test_override_activo_en_biometrico(self, override_biometrico):
        """_annex3_override debe activar annex3_override=True para texto biométrico."""
        assert override_biometrico.get("annex3_override") is True

    def test_risk_level_corregido_a_inaceptable(self, override_biometrico):
        """El texto biométrico en espacio público debe sobreescribirse a inaceptable."""
        assert override_biometrico["risk_level"] == "inaceptable"

    def test_probabilities_coherentes_tras_override_biometrico(self, override_biometrico):
        """probabilities[risk_level] debe ser el valor máximo también para inaceptable."""
        nivel = override_biometrico["risk_level"]
        probs = override_biometrico["probabilities"]
        assert probs[nivel] == max(probs.values())

    def test_shap_features_no_en_nivel_superior_tras_override(self, override_recidiva):
        """shap_top_features no debe estar en el nivel raíz del resultado tras override.

        Cuando el override actúa, los features SHAP pertenecen a la predicción ML
        (clase equivocada). Exponerlos al nivel raíz causaría al LLM recibir algo como
        'Inaceptable: características para alto_riesgo: kw_algo' — inputs contradictorios.
        _annex3_override mueve shap_top_features a ml_prediction para evitar esto.
        """
        assert "shap_top_features" not in override_recidiva, (
            "shap_top_features no debe estar en nivel raíz tras override: "
            "los features ML se mueven a ml_prediction para evitar explicaciones contradictorias."
        )

    def test_ml_prediction_contiene_shap_features_originales(self, override_recidiva):
        """ml_prediction debe conservar shap_top_features del modelo ML para trazabilidad.

        Aunque los features ML no son válidos para explicar el nivel determinado por
        la ley, deben preservarse en ml_prediction para debugging y auditoría.
        """
        ml = override_recidiva.get("ml_prediction", {})
        assert "shap_top_features" in ml, (
            "ml_prediction debe contener shap_top_features del modelo ML original"
        )
        features = ml["shap_top_features"]
        assert isinstance(features, list)
        assert len(features) > 0
        feature_names = {f["feature"] for f in features}
        assert "chatbot" in feature_names, (
            f"El feature 'chatbot' del mock debería estar en ml_prediction.shap_top_features, "
            f"pero se encontraron: {feature_names}"
        )

    def test_shap_explanation_es_referencia_legal_tras_override(self, override_recidiva):
        """shap_explanation tras override debe ser la referencia legal, no nombres de features ML.

        Bug: sin el fix, shap_explanation podía decir
        'Factores principales para inaceptable: kw_alto_riesgo, svd_3'
        — inputs contradictorios que el LLM no puede interpretar correctamente.
        Con el fix, el override produce una explicación legal como
        'Clasificación determinada por Anexo III cat. 6 EU AI Act.'
        """
        expl = override_recidiva.get("shap_explanation", "")
        assert "EU AI Act" in expl, (
            f"shap_explanation tras override debe mencionar EU AI Act: '{expl}'"
        )
        for prefijo in ("svd_", "kw_", "num_palabras", "num_caracteres"):
            assert prefijo not in expl, (
                f"shap_explanation tras override menciona un término ML ('{prefijo}'): '{expl}'"
            )

    def test_no_actua_si_ml_ya_coincide_con_anexo_iii(self):
        """Si ML ya predijo el nivel correcto del Anexo III, override no modifica el resultado."""
        from src.classifier.main import _annex3_override
        resultado_correcto = {
            "risk_level": "alto_riesgo",
            "confidence": 0.91,
            "probabilities": {
                "inaceptable": 0.05,
                "alto_riesgo": 0.91,
                "riesgo_limitado": 0.03,
                "riesgo_minimo": 0.01,
            },
        }
        resultado = _annex3_override(
            "evaluación del riesgo de recidiva para recomendar libertad condicional",
            resultado_correcto.copy(),
        )
        # No debe añadir annex3_override ni cambiar nada
        assert resultado.get("annex3_override") is not True
        assert resultado["risk_level"] == "alto_riesgo"
        assert resultado["confidence"] == 0.91

    def test_best_level_incluido_si_faltaba_en_probabilities_originales(self):
        """Si best_level no estaba en el dict original, debe aparecer en el resultado."""
        from src.classifier.main import _annex3_override
        # Simula un dict de probabilities incompleto (sin alto_riesgo)
        resultado_incompleto = {
            "risk_level": "riesgo_minimo",
            "confidence": 0.62,
            "probabilities": {
                "inaceptable": 0.15,
                "riesgo_limitado": 0.13,
                "riesgo_minimo": 0.72,
                # alto_riesgo ausente intencionalmente
            },
        }
        resultado = _annex3_override(
            "evaluación del riesgo de recidiva para recomendar libertad condicional",
            resultado_incompleto,
        )
        assert "alto_riesgo" in resultado["probabilities"]
        assert resultado["probabilities"]["alto_riesgo"] == 0.85


# ---------------------------------------------------------------------------
# Helpers compartidos para tests BERT
# ---------------------------------------------------------------------------

_BERT_MODEL_DIR = (
    Path(__file__).parent.parent
    / "src/classifier/bert_pipeline/models/bert_model"
)
_BERT_AVAILABLE = _BERT_MODEL_DIR.exists() and any(
    (_BERT_MODEL_DIR / f).exists()
    for f in ("pytorch_model.bin", "model.safetensors", "tf_model.h5")
)

_FAKE_PROBS = {
    "alto_riesgo"   : 0.70,
    "inaceptable"   : 0.10,
    "riesgo_limitado": 0.15,
    "riesgo_minimo" : 0.05,
}
_FAKE_BERT_RESULT_ML = ("alto_riesgo", 0.70, _FAKE_PROBS)


# ---------------------------------------------------------------------------
# Grupo 6: Dispatch CLASSIFIER_BACKEND y fallback a XGBoost
# ---------------------------------------------------------------------------

class TestBertDispatch:
    """Verifica que predict_risk() enruta correctamente según CLASSIFIER_BACKEND.

    El backend se lee de la variable de entorno al importar el módulo,
    por lo que se parchea directamente la constante de módulo ``_CLASSIFIER_BACKEND``.
    """

    def test_backend_bert_delega_a_predict_risk_bert(self):
        """Con CLASSIFIER_BACKEND=bert, predict_risk() debe llamar predict_risk_bert()."""
        import src.classifier.main as m
        mock_result = {"risk_level": "alto_riesgo", "confidence": 0.70,
                       "probabilities": _FAKE_PROBS, "backend": "bert",
                       "shap_explanation": "Clasificación BERT."}
        with patch.object(m, "_CLASSIFIER_BACKEND", "bert"):
            with patch.object(m, "predict_risk_bert", return_value=mock_result) as mock_bert:
                result = predict_risk("sistema de reconocimiento facial en aeropuertos")
        mock_bert.assert_called_once()
        assert result == mock_result

    def test_backend_xgboost_no_llama_bert(self):
        """Con CLASSIFIER_BACKEND=xgboost (por defecto), predict_risk_bert() no se invoca."""
        import src.classifier.main as m
        with patch.object(m, "_CLASSIFIER_BACKEND", "xgboost"):
            with patch.object(m, "predict_risk_bert") as mock_bert:
                predict_risk("chatbot de atención al cliente para tienda online")
        mock_bert.assert_not_called()

    def test_bert_fallo_usa_xgboost_fallback(self):
        """Si predict_risk_bert() lanza una excepción, predict_risk() cae a XGBoost."""
        import src.classifier.main as m
        with patch.object(m, "_CLASSIFIER_BACKEND", "bert"):
            with patch.object(m, "predict_risk_bert", side_effect=RuntimeError("GPU no disponible")):
                result = predict_risk("chatbot de atención al cliente para tienda online")
        # El fallback XGBoost debe devolver un resultado válido
        assert result["risk_level"] in RISK_LEVELS
        assert result.get("backend") != "bert"  # XGBoost no añade campo backend

    def test_bert_fallo_fallback_devuelve_estructura_completa(self):
        """El fallback XGBoost mantiene el contrato de salida completo."""
        import src.classifier.main as m
        with patch.object(m, "_CLASSIFIER_BACKEND", "bert"):
            with patch.object(m, "predict_risk_bert", side_effect=RuntimeError("fallo")):
                result = predict_risk("chatbot de atención al cliente para tienda online")
        assert "risk_level" in result
        assert "confidence" in result
        assert "probabilities" in result


# ---------------------------------------------------------------------------
# Grupo 7: Estructura del resultado predict_risk_bert (con _predict_bert_raw mockeado)
# ---------------------------------------------------------------------------

class TestBertEstructuraRespuesta:
    """Verifica el contrato de salida de predict_risk_bert().

    Se mockea ``_predict_bert_raw`` para aislar la lógica de ensamblado
    del resultado de la carga real del modelo (que requiere artefactos en disco).
    """

    @pytest.fixture(scope="class")
    def resultado_bert(self):
        import src.classifier.main as m
        with patch.object(m, "_predict_bert_raw", return_value=_FAKE_BERT_RESULT_ML):
            return predict_risk_bert("sistema de reconocimiento facial en aeropuertos")

    def test_devuelve_dict(self, resultado_bert):
        assert isinstance(resultado_bert, dict)

    def test_contiene_backend_bert(self, resultado_bert):
        """predict_risk_bert debe incluir ``backend='bert'`` para distinguirlo de XGBoost."""
        assert resultado_bert.get("backend") == "bert"

    def test_contiene_risk_level(self, resultado_bert):
        assert "risk_level" in resultado_bert

    def test_risk_level_valido(self, resultado_bert):
        assert resultado_bert["risk_level"] in RISK_LEVELS

    def test_contiene_confidence(self, resultado_bert):
        assert "confidence" in resultado_bert

    def test_confidence_es_probabilidad(self, resultado_bert):
        c = resultado_bert["confidence"]
        assert isinstance(c, float)
        assert 0.0 <= c <= 1.0

    def test_contiene_probabilities(self, resultado_bert):
        assert "probabilities" in resultado_bert

    def test_probabilities_cubre_todas_las_clases(self, resultado_bert):
        assert set(resultado_bert["probabilities"].keys()) == RISK_LEVELS

    def test_probabilities_suman_uno(self, resultado_bert):
        total = sum(resultado_bert["probabilities"].values())
        assert abs(total - 1.0) < 0.02

    def test_contiene_shap_explanation(self, resultado_bert):
        """BERT no tiene SHAP; shap_explanation debe existir igualmente con descripción."""
        assert "shap_explanation" in resultado_bert
        assert len(resultado_bert["shap_explanation"]) > 0

    def test_shap_explanation_menciona_bert(self, resultado_bert):
        """shap_explanation BERT debe mencionar 'BERT' o la confianza, no features SHAP."""
        expl = resultado_bert["shap_explanation"]
        # Cuando no hay override, la explicación menciona "BERT" y la confianza
        if not resultado_bert.get("annex3_override"):
            assert "BERT" in expl or "%" in expl, (
                f"shap_explanation BERT debería mencionar 'BERT' o la confianza: '{expl}'"
            )

    def test_no_contiene_shap_top_features(self, resultado_bert):
        """BERT no calcula features SHAP individuales; shap_top_features no debe aparecer."""
        if not resultado_bert.get("annex3_override"):
            assert "shap_top_features" not in resultado_bert, (
                "BERT no genera shap_top_features — la explicación es semántica global"
            )


# ---------------------------------------------------------------------------
# Grupo 8: Validación de entrada en ruta BERT
# ---------------------------------------------------------------------------

class TestBertValidacionEntrada:
    """Pydantic debe rechazar entradas inválidas antes de llamar a _predict_bert_raw."""

    def test_texto_vacio_lanza_excepcion(self):
        from pydantic import ValidationError
        import src.classifier.main as m
        with patch.object(m, "_predict_bert_raw", return_value=_FAKE_BERT_RESULT_ML):
            with pytest.raises(ValidationError):
                predict_risk_bert("")

    def test_texto_demasiado_largo_lanza_excepcion(self):
        from pydantic import ValidationError
        import src.classifier.main as m
        with patch.object(m, "_predict_bert_raw", return_value=_FAKE_BERT_RESULT_ML):
            with pytest.raises(ValidationError):
                predict_risk_bert("a" * 5001)

    def test_texto_valido_no_lanza_excepcion(self):
        import src.classifier.main as m
        with patch.object(m, "_predict_bert_raw", return_value=_FAKE_BERT_RESULT_ML):
            result = predict_risk_bert("sistema de IA médica")
        assert result["risk_level"] in RISK_LEVELS


# ---------------------------------------------------------------------------
# Grupo 9: Override Anexo III en ruta BERT
# ---------------------------------------------------------------------------

class TestBertAnnex3Override:
    """Verifica que el override determinista del Anexo III funciona en la ruta BERT.

    Se mockea ``_predict_bert_raw`` para controlar qué predice BERT
    y verificar que _annex3_override actúa sobre ese resultado.
    """

    @pytest.fixture(scope="class")
    def override_bert_recidiva(self):
        """BERT predice riesgo_minimo; el override debe corregirlo a alto_riesgo."""
        import src.classifier.main as m
        fake_probs_minimo = {
            "inaceptable": 0.05, "alto_riesgo": 0.10,
            "riesgo_limitado": 0.20, "riesgo_minimo": 0.65,
        }
        with patch.object(m, "_predict_bert_raw", return_value=("riesgo_minimo", 0.65, fake_probs_minimo)):
            return predict_risk_bert(
                "evaluación del riesgo de recidiva para recomendar libertad condicional"
            )

    def test_override_activo(self, override_bert_recidiva):
        assert override_bert_recidiva.get("annex3_override") is True

    def test_risk_level_corregido(self, override_bert_recidiva):
        assert override_bert_recidiva["risk_level"] == "alto_riesgo"

    def test_backend_preservado_tras_override(self, override_bert_recidiva):
        """El campo backend='bert' debe sobrevivir al override."""
        assert override_bert_recidiva.get("backend") == "bert"

    def test_shap_explanation_es_referencia_legal(self, override_bert_recidiva):
        expl = override_bert_recidiva.get("shap_explanation", "")
        assert "EU AI Act" in expl

    def test_ml_prediction_preserva_prediccion_bert_original(self, override_bert_recidiva):
        ml = override_bert_recidiva.get("ml_prediction", {})
        assert ml.get("risk_level") == "riesgo_minimo"

    def test_probabilities_coherentes_tras_override(self, override_bert_recidiva):
        nivel = override_bert_recidiva["risk_level"]
        probs = override_bert_recidiva["probabilities"]
        assert probs[nivel] == max(probs.values())

    def test_llamadas_consecutivas_bert_consistentes(self):
        """Dos llamadas a predict_risk_bert con el mismo texto dan el mismo resultado."""
        import src.classifier.main as m
        with patch.object(m, "_predict_bert_raw", return_value=_FAKE_BERT_RESULT_ML):
            r1 = predict_risk_bert("chatbot de atención al cliente para tienda online")
            r2 = predict_risk_bert("chatbot de atención al cliente para tienda online")
        assert r1["risk_level"] == r2["risk_level"]
        assert r1["confidence"] == r2["confidence"]


# ---------------------------------------------------------------------------
# Grupo 10: Carga de artefactos BERT — errores sin modelo en disco
# ---------------------------------------------------------------------------

class TestBertLoadArtifacts:
    """Verifica el comportamiento de _load_bert_artifacts() sin el modelo en disco."""

    def test_filenotfounderror_si_directorio_no_existe(self, tmp_path):
        """_load_bert_artifacts lanza FileNotFoundError si el directorio BERT no existe."""
        import src.classifier.main as m
        original_dir   = m._BERT_DIR
        original_model = m._bert_model
        original_tok   = m._bert_tokenizer
        original_id2l  = m._bert_id2label

        m._bert_model     = None
        m._bert_tokenizer = None
        m._bert_id2label  = None
        m._BERT_DIR       = tmp_path / "modelo_inexistente"

        try:
            with pytest.raises(FileNotFoundError, match="Modelo BERT no encontrado"):
                m._load_bert_artifacts()
        finally:
            m._BERT_DIR       = original_dir
            m._bert_model     = original_model
            m._bert_tokenizer = original_tok
            m._bert_id2label  = original_id2l

    def test_singleton_none_tras_fallo_de_carga(self, tmp_path):
        """Si la carga falla, los singletons quedan en None (no half-loaded)."""
        import src.classifier.main as m
        original_dir   = m._BERT_DIR
        original_model = m._bert_model
        original_tok   = m._bert_tokenizer
        original_id2l  = m._bert_id2label

        m._bert_model     = None
        m._bert_tokenizer = None
        m._bert_id2label  = None
        m._BERT_DIR       = tmp_path / "no_existe"

        try:
            with pytest.raises(FileNotFoundError):
                m._load_bert_artifacts()
            assert m._bert_model     is None
            assert m._bert_tokenizer is None
            assert m._bert_id2label  is None
        finally:
            m._BERT_DIR       = original_dir
            m._bert_model     = original_model
            m._bert_tokenizer = original_tok
            m._bert_id2label  = original_id2l


# ---------------------------------------------------------------------------
# Grupo 11: Smoke tests BERT con modelo real (skip si no hay artefactos)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not _BERT_AVAILABLE,
    reason="Modelo BERT no disponible — ejecuta: python src/classifier/bert_pipeline/train.py",
)
class TestBertSmoke:
    """Smoke tests end-to-end con el modelo BERT real.

    Se saltan automáticamente si ``bert_pipeline/models/bert_model/`` no existe.
    En CI sin GPU estos tests no se ejecutan; en local (o CI con GPU) validan
    el pipeline completo incluyendo carga del modelo real.
    """

    @pytest.fixture(scope="class")
    def resultado_bert_real(self):
        return predict_risk_bert(
            "sistema de reconocimiento facial en aeropuertos para control de acceso"
        )

    def test_devuelve_dict(self, resultado_bert_real):
        assert isinstance(resultado_bert_real, dict)

    def test_risk_level_valido(self, resultado_bert_real):
        assert resultado_bert_real["risk_level"] in RISK_LEVELS

    def test_confidence_en_rango(self, resultado_bert_real):
        c = resultado_bert_real["confidence"]
        assert 0.0 <= c <= 1.0

    def test_backend_bert(self, resultado_bert_real):
        assert resultado_bert_real.get("backend") == "bert"

    def test_texto_corto(self):
        result = predict_risk_bert("IA médica")
        assert result["risk_level"] in RISK_LEVELS

    def test_texto_largo(self):
        texto = (
            "Sistema automatizado de vigilancia biométrica en espacios públicos "
            "que utiliza reconocimiento facial en tiempo real para identificar "
            "personas en listas de seguimiento policial, integrado con cámaras "
            "de circuito cerrado en estaciones de metro y aeropuertos."
        )
        result = predict_risk_bert(texto)
        assert result["risk_level"] in RISK_LEVELS

    def test_texto_sin_keywords_dominio(self):
        result = predict_risk_bert("software de gestión de inventario para almacenes")
        assert result["risk_level"] in RISK_LEVELS

    def test_llamadas_consecutivas_consistentes(self):
        texto = "chatbot de atención al cliente para tienda online"
        r1 = predict_risk_bert(texto)
        r2 = predict_risk_bert(texto)
        assert r1["risk_level"] == r2["risk_level"]
        assert r1["confidence"] == r2["confidence"]

    def test_probabilities_suman_uno(self, resultado_bert_real):
        total = sum(resultado_bert_real["probabilities"].values())
        assert abs(total - 1.0) < 0.02

    def test_predict_risk_con_backend_bert_env(self, monkeypatch):
        """predict_risk() con CLASSIFIER_BACKEND=bert usa BERT real sin fallback."""
        import src.classifier.main as m
        with patch.object(m, "_CLASSIFIER_BACKEND", "bert"):
            result = predict_risk(
                "sistema de reconocimiento facial en aeropuertos para control de acceso"
            )
        assert result["risk_level"] in RISK_LEVELS
        assert result.get("backend") == "bert"
