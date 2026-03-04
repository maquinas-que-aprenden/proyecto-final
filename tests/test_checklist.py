"""test_checklist.py — Tests del modulo de checklist de cumplimiento.

Tests unitarios puros: el modulo es determinista (sin LLM, sin mocks).

Ejecutar:
    pytest tests/test_checklist.py -v
"""

from src.checklist.main import (
    build_compliance_checklist,
    _detect_borderline,
    _build_shap_recommendations,
    DISCLAIMER,
)


# ---------------------------------------------------------------------------
# Helpers: predicciones mock para cada nivel de riesgo
# ---------------------------------------------------------------------------

def _prediction(
    risk_level: str,
    confidence: float = 0.85,
    probabilities: dict | None = None,
    shap_top_features: list | None = None,
    **kwargs,
) -> dict:
    """Crea un dict de prediccion simulando la salida de predict_risk."""
    return {
        "risk_level": risk_level,
        "confidence": confidence,
        "probabilities": probabilities or {},
        "shap_top_features": shap_top_features or [],
        **kwargs,
    }


# ---------------------------------------------------------------------------
# Grupo 1: Obligaciones por nivel de riesgo
# ---------------------------------------------------------------------------

class TestObligacionesPorNivel:
    """Cada nivel de riesgo devuelve las obligaciones correctas."""

    def test_alto_riesgo_devuelve_8_obligaciones(self):
        pred = _prediction("alto_riesgo")
        checklist = build_compliance_checklist(pred, "sistema X")
        assert len(checklist["obligations"]) == 8

    def test_alto_riesgo_obligaciones_son_mandatory(self):
        pred = _prediction("alto_riesgo")
        checklist = build_compliance_checklist(pred, "sistema X")
        assert all(ob["mandatory"] for ob in checklist["obligations"])

    def test_alto_riesgo_incluye_art_9_a_15_y_43(self):
        pred = _prediction("alto_riesgo")
        checklist = build_compliance_checklist(pred, "sistema X")
        articles = {ob["article"] for ob in checklist["obligations"]}
        for art in ["Art. 9", "Art. 10", "Art. 11", "Art. 12", "Art. 13", "Art. 14", "Art. 15", "Art. 43"]:
            assert any(art in a for a in articles), f"Falta {art}"

    def test_inaceptable_devuelve_prohibicion(self):
        pred = _prediction("inaceptable")
        checklist = build_compliance_checklist(pred, "sistema X")
        assert len(checklist["obligations"]) == 1
        assert "Art. 5" in checklist["obligations"][0]["article"]
        assert checklist["obligations"][0]["mandatory"] is True

    def test_riesgo_limitado_devuelve_transparencia(self):
        pred = _prediction("riesgo_limitado")
        checklist = build_compliance_checklist(pred, "sistema X")
        assert len(checklist["obligations"]) == 1
        assert "Art. 50" in checklist["obligations"][0]["article"]

    def test_riesgo_minimo_devuelve_voluntario(self):
        pred = _prediction("riesgo_minimo")
        checklist = build_compliance_checklist(pred, "sistema X")
        assert len(checklist["obligations"]) == 1
        assert checklist["obligations"][0]["mandatory"] is False
        assert "Art. 95" in checklist["obligations"][0]["article"]


# ---------------------------------------------------------------------------
# Grupo 2: Deteccion de borderline
# ---------------------------------------------------------------------------

class TestBorderlineDetection:
    """Deteccion de casos borderline via distribucion de probabilidades."""

    def test_borderline_alto_a_inaceptable(self):
        """Probabilidad significativa de inaceptable genera advertencia."""
        warning = _detect_borderline("alto_riesgo", {
            "alto_riesgo": 0.70,
            "inaceptable": 0.25,
            "riesgo_limitado": 0.03,
            "riesgo_minimo": 0.02,
        })
        assert warning is not None
        assert "Art. 5" in warning

    def test_sin_borderline_confianza_alta(self):
        """Clasificacion clara no genera advertencia."""
        warning = _detect_borderline("alto_riesgo", {
            "alto_riesgo": 0.90,
            "inaceptable": 0.05,
            "riesgo_limitado": 0.03,
            "riesgo_minimo": 0.02,
        })
        assert warning is None

    def test_borderline_minimo_a_alto(self):
        """Minimo con probabilidad de alto riesgo genera advertencia."""
        warning = _detect_borderline("riesgo_minimo", {
            "riesgo_minimo": 0.55,
            "alto_riesgo": 0.30,
            "riesgo_limitado": 0.10,
            "inaceptable": 0.05,
        })
        assert warning is not None
        assert "alto_riesgo" in warning

    def test_borderline_sin_probabilidades(self):
        """Sin probabilidades no genera advertencia."""
        warning = _detect_borderline("alto_riesgo", {})
        assert warning is None

    def test_borderline_prioriza_severidad(self):
        """Con dos clases borderline, prioriza la mas restrictiva."""
        warning = _detect_borderline("riesgo_minimo", {
            "riesgo_minimo": 0.50,
            "riesgo_limitado": 0.25,
            "alto_riesgo": 0.20,
            "inaceptable": 0.05,
        })
        assert warning is not None
        # Debe priorizar alto_riesgo sobre riesgo_limitado por severidad
        assert "alto_riesgo" in warning


# ---------------------------------------------------------------------------
# Grupo 3: SHAP features → recomendaciones
# ---------------------------------------------------------------------------

class TestShapRecommendations:
    """Mapping de SHAP top features a recomendaciones legales."""

    def test_crediticio_mapea_a_anexo3_5b(self):
        recs = _build_shap_recommendations([
            {"feature": "crediticio", "contribution": 0.42},
        ])
        assert len(recs) == 1
        assert recs[0]["annex_ref"] == "Anexo III cat. 5.b"

    def test_facial_mapea_a_art5_anexo3(self):
        recs = _build_shap_recommendations([
            {"feature": "facial", "contribution": 0.5},
        ])
        assert len(recs) == 1
        assert "Art. 5" in recs[0]["annex_ref"]

    def test_svd_features_excluidas(self):
        """Features SVD no interpretables no generan recomendaciones."""
        recs = _build_shap_recommendations([
            {"feature": "svd_0", "contribution": 0.8},
            {"feature": "svd_1", "contribution": 0.6},
            {"feature": "svd_42", "contribution": 0.3},
        ])
        assert recs == []

    def test_num_palabras_excluida(self):
        """Features de longitud no generan recomendaciones."""
        recs = _build_shap_recommendations([
            {"feature": "num_palabras", "contribution": 0.5},
            {"feature": "num_caracteres", "contribution": 0.3},
        ])
        assert recs == []

    def test_dedup_por_annex_ref(self):
        """Dos features del mismo Anexo III no duplican recomendaciones."""
        recs = _build_shap_recommendations([
            {"feature": "crediticio", "contribution": 0.5},
            {"feature": "solvencia", "contribution": 0.3},
        ])
        # Ambas mapean a Anexo III cat. 5.b — solo una recomendacion
        assert len(recs) == 1

    def test_maximo_3_recomendaciones(self):
        """El cap es de 3 recomendaciones."""
        recs = _build_shap_recommendations([
            {"feature": "crediticio", "contribution": 0.5},
            {"feature": "facial", "contribution": 0.4},
            {"feature": "diagnóstico", "contribution": 0.3},
            {"feature": "reincidencia", "contribution": 0.2},
        ])
        assert len(recs) <= 3

    def test_feature_desconocida_no_genera_rec(self):
        """Features no mapeadas se ignoran."""
        recs = _build_shap_recommendations([
            {"feature": "palabra_rara", "contribution": 0.5},
        ])
        assert recs == []

    def test_normaliza_tildes_y_case(self):
        """Features con variaciones de tildes/mayusculas se resuelven correctamente."""
        recs = _build_shap_recommendations([
            {"feature": "DIAGNOSTICO", "contribution": 0.4},
        ])
        assert len(recs) == 1
        assert recs[0]["annex_ref"] == "Anexo III cat. 5.a"

    def test_normaliza_crediticio_mayusculas(self):
        """'CrEditicio' normalizado mapea a Anexo III cat. 5.b."""
        recs = _build_shap_recommendations([
            {"feature": "CrEditicio", "contribution": 0.5},
        ])
        assert len(recs) == 1
        assert recs[0]["annex_ref"] == "Anexo III cat. 5.b"

    def test_payload_shap_incompleto_se_ignora(self):
        """Features sin clave 'feature' se ignoran sin error."""
        recs = _build_shap_recommendations([
            {"contribution": 0.7},
        ])
        assert recs == []

    def test_payload_shap_feature_none_se_ignora(self):
        """Feature con valor None se ignora sin error."""
        recs = _build_shap_recommendations([
            {"feature": None, "contribution": 0.5},
        ])
        assert recs == []


# ---------------------------------------------------------------------------
# Grupo 4: Checklist completo
# ---------------------------------------------------------------------------

class TestBuildComplianceChecklist:
    """build_compliance_checklist integra clasificacion + checklist + SHAP."""

    def test_disclaimer_siempre_presente(self):
        pred = _prediction("alto_riesgo")
        checklist = build_compliance_checklist(pred, "sistema X")
        assert checklist["disclaimer"] == DISCLAIMER

    def test_incluye_system_description(self):
        pred = _prediction("alto_riesgo")
        checklist = build_compliance_checklist(pred, "mi sistema de scoring")
        assert checklist["system_description"] == "mi sistema de scoring"

    def test_incluye_annex3_override(self):
        pred = _prediction(
            "alto_riesgo",
            annex3_override=True,
            annex3_ref="Anexo III cat. 5.b",
        )
        checklist = build_compliance_checklist(pred, "sistema X")
        assert checklist["annex3_override"] is True
        assert checklist["annex3_ref"] == "Anexo III cat. 5.b"

    def test_sin_annex3_override(self):
        pred = _prediction("riesgo_minimo")
        checklist = build_compliance_checklist(pred, "sistema X")
        assert checklist["annex3_override"] is False
        assert checklist["annex3_ref"] is None

    def test_checklist_con_shap_y_borderline(self):
        """Checklist completo con SHAP features y caso borderline."""
        pred = _prediction(
            "alto_riesgo",
            confidence=0.72,
            probabilities={
                "alto_riesgo": 0.72,
                "inaceptable": 0.22,
                "riesgo_limitado": 0.04,
                "riesgo_minimo": 0.02,
            },
            shap_top_features=[
                {"feature": "crediticio", "contribution": 0.5},
                {"feature": "svd_0", "contribution": 0.3},
            ],
        )
        checklist = build_compliance_checklist(pred, "scoring crediticio")
        assert checklist["borderline_warning"] is not None
        assert len(checklist["specific_recommendations"]) == 1
        assert checklist["specific_recommendations"][0]["feature"] == "crediticio"
