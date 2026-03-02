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

import pytest

from src.classifier.main import predict_risk

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
