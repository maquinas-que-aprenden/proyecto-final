"""checklist/main.py — Checklist de cumplimiento EU AI Act.

Modulo determinista (sin LLM) que genera un checklist de obligaciones
legales a partir de la prediccion del clasificador de riesgo.

Usa las SHAP top features y la distribucion de probabilidades para
generar recomendaciones especificas y detectar casos borderline.
"""

from __future__ import annotations

import unicodedata

# ---------------------------------------------------------------------------
# Obligaciones por nivel de riesgo (EU AI Act)
# ---------------------------------------------------------------------------

_OBLIGATIONS_BY_RISK_LEVEL: dict[str, list[dict]] = {
    "inaceptable": [
        {
            "article": "Art. 5 EU AI Act",
            "title": "Prohibicion",
            "description": (
                "Este sistema esta prohibido por el Art. 5 del Reglamento (UE) 2024/1689. "
                "Debe cesar su desarrollo, despliegue y uso."
            ),
            "mandatory": True,
        },
    ],
    "alto_riesgo": [
        {
            "article": "Art. 9 EU AI Act",
            "title": "Sistema de gestion de riesgos",
            "description": (
                "Establecer, aplicar, documentar y mantener un sistema de gestion de riesgos "
                "durante todo el ciclo de vida del sistema de IA."
            ),
            "mandatory": True,
        },
        {
            "article": "Art. 10 EU AI Act",
            "title": "Gobernanza de datos",
            "description": (
                "Los conjuntos de datos de entrenamiento, validacion y prueba deben cumplir "
                "criterios de calidad: representatividad, ausencia de errores, completitud."
            ),
            "mandatory": True,
        },
        {
            "article": "Art. 11 EU AI Act",
            "title": "Documentacion tecnica",
            "description": (
                "Elaborar documentacion tecnica antes de la comercializacion o puesta en servicio, "
                "manteniendola actualizada."
            ),
            "mandatory": True,
        },
        {
            "article": "Art. 12 EU AI Act",
            "title": "Registro de actividades",
            "description": (
                "El sistema debe permitir el registro automatico de eventos (logs) durante "
                "su funcionamiento, con trazabilidad adecuada."
            ),
            "mandatory": True,
        },
        {
            "article": "Art. 13 EU AI Act",
            "title": "Transparencia",
            "description": (
                "Disenar el sistema para que su funcionamiento sea suficientemente transparente "
                "y permita a los responsables interpretar y usar correctamente sus resultados."
            ),
            "mandatory": True,
        },
        {
            "article": "Art. 14 EU AI Act",
            "title": "Supervision humana",
            "description": (
                "Disenar el sistema para que pueda ser supervisado eficazmente por personas "
                "fisicas durante su uso, incluyendo la posibilidad de intervenir o detenerlo."
            ),
            "mandatory": True,
        },
        {
            "article": "Art. 15 EU AI Act",
            "title": "Precision, solidez y ciberseguridad",
            "description": (
                "El sistema debe alcanzar niveles adecuados de precision, solidez y "
                "ciberseguridad, y funcionar de forma coherente a lo largo de su ciclo de vida."
            ),
            "mandatory": True,
        },
        {
            "article": "Art. 43 EU AI Act",
            "title": "Evaluacion de conformidad",
            "description": (
                "Someterse a una evaluacion de conformidad antes de su comercializacion "
                "o puesta en servicio, segun el procedimiento aplicable."
            ),
            "mandatory": True,
        },
    ],
    "riesgo_limitado": [
        {
            "article": "Art. 50 EU AI Act",
            "title": "Obligaciones de transparencia",
            "description": (
                "Informar a las personas de que interactuan con un sistema de IA, "
                "salvo que sea evidente. Para deepfakes o contenido sintetico, "
                "etiquetar como generado por IA."
            ),
            "mandatory": True,
        },
    ],
    "riesgo_minimo": [
        {
            "article": "Art. 95 EU AI Act",
            "title": "Codigos de conducta voluntarios",
            "description": (
                "No existen obligaciones especificas. Se anima a adherirse a codigos de conducta "
                "voluntarios que promuevan la aplicacion de los requisitos de los sistemas de alto riesgo."
            ),
            "mandatory": False,
        },
    ],
}


# ---------------------------------------------------------------------------
# SHAP features → recomendaciones especificas del Anexo III
# ---------------------------------------------------------------------------

_SHAP_FEATURE_RECOMMENDATIONS: dict[str, dict] = {
    # Anexo III cat. 5.b — Evaluacion crediticia
    "crediticio": {
        "annex_ref": "Anexo III cat. 5.b",
        "recommendation": (
            "Sistema de evaluacion crediticia. Garantizar no discriminacion en el acceso "
            "al credito, documentar variables de puntuacion, supervision humana en "
            "decisiones de concesion o denegacion."
        ),
    },
    "solvencia": {
        "annex_ref": "Anexo III cat. 5.b",
        "recommendation": (
            "Evaluacion de solvencia financiera. Transparencia en criterios de evaluacion "
            "y derecho del afectado a obtener explicacion."
        ),
    },
    "crédito": {
        "annex_ref": "Anexo III cat. 5.b",
        "recommendation": (
            "Sistema de credito. Cumplir requisitos sobre no discriminacion "
            "y acceso equitativo a servicios financieros esenciales."
        ),
    },
    "hipoteca": {
        "annex_ref": "Anexo III cat. 5.b",
        "recommendation": (
            "Evaluacion hipotecaria. Transparencia y supervision humana en decisiones "
            "que afectan al acceso a la vivienda."
        ),
    },
    # Art. 5 / Anexo III cat. 1 — Biometria
    "facial": {
        "annex_ref": "Art. 5.1.d / Anexo III cat. 1",
        "recommendation": (
            "Reconocimiento facial. Si opera en espacios publicos en tiempo real, "
            "esta prohibido (Art. 5.1.d). En otros contextos, Anexo III cat. 1: "
            "evaluacion de impacto sobre derechos fundamentales."
        ),
    },
    "biométrico": {
        "annex_ref": "Art. 5.1.d / Anexo III cat. 1",
        "recommendation": (
            "Sistema biometrico. Verificar si opera en tiempo real en espacios publicos "
            "(prohibido, Art. 5.1.d). Si no, Anexo III cat. 1: minimizacion de datos, "
            "supervision humana reforzada."
        ),
    },
    # Anexo III cat. 5.a — Sanidad
    "diagnóstico": {
        "annex_ref": "Anexo III cat. 5.a",
        "recommendation": (
            "Sistema de diagnostico. Validacion clinica conforme a normativa de productos "
            "sanitarios (MDR), supervision por profesional sanitario cualificado."
        ),
    },
    "sanitario": {
        "annex_ref": "Anexo III cat. 5.a",
        "recommendation": (
            "Sistema sanitario. Cumplir regulacion de dispositivos medicos, garantizar "
            "supervision humana clinica, validar en poblacion representativa."
        ),
    },
    "triage": {
        "annex_ref": "Anexo III cat. 5.a",
        "recommendation": (
            "Sistema de triage. Garantizar revision por profesional sanitario, "
            "documentar precision por grupo demografico."
        ),
    },
    # Anexo III cat. 4 — Empleo y seleccion
    "curricular": {
        "annex_ref": "Anexo III cat. 4.a",
        "recommendation": (
            "Evaluacion curricular. Transparencia en criterios de seleccion, "
            "auditoria de sesgo por genero/edad/origen, supervision humana en "
            "decisiones de contratacion."
        ),
    },
    "candidato": {
        "annex_ref": "Anexo III cat. 4.a",
        "recommendation": (
            "Evaluacion de candidatos. Documentar criterios, garantizar no discriminacion, "
            "revision humana de decisiones automatizadas."
        ),
    },
    "reclutamiento": {
        "annex_ref": "Anexo III cat. 4.a",
        "recommendation": (
            "Sistema de reclutamiento. Auditar sesgo, transparencia sobre el uso de IA, "
            "supervision humana."
        ),
    },
    # Anexo III cat. 6 — Justicia penal
    "reincidencia": {
        "annex_ref": "Anexo III cat. 6",
        "recommendation": (
            "Prediccion de reincidencia. Prohibido como unica base para decisiones "
            "judiciales, requiere supervision judicial, documentar limitaciones."
        ),
    },
    "policial": {
        "annex_ref": "Anexo III cat. 6",
        "recommendation": (
            "Sistema policial. Supervision humana reforzada, prohibicion de perfilado "
            "discriminatorio, documentacion tecnica exhaustiva."
        ),
    },
    # Anexo III cat. 8 — Administracion de justicia
    "juez": {
        "annex_ref": "Anexo III cat. 8",
        "recommendation": (
            "Apoyo judicial. No sustituye al juez, solo asistencia. "
            "Documentar limitaciones y tasa de error."
        ),
    },
    "sentencia": {
        "annex_ref": "Anexo III cat. 8",
        "recommendation": (
            "Sistema de sentencias. Asistencia unicamente, supervision judicial "
            "obligatoria, no vinculante."
        ),
    },
    # Anexo III cat. 7 — Migracion
    "migración": {
        "annex_ref": "Anexo III cat. 7",
        "recommendation": (
            "Sistema migratorio. Evaluacion de impacto sobre derechos fundamentales, "
            "no discriminacion por nacionalidad o etnia, supervision humana."
        ),
    },
    "asilo": {
        "annex_ref": "Anexo III cat. 7",
        "recommendation": (
            "Sistema de asilo. No puede ser unico criterio de decision, "
            "revision humana cualificada de cada solicitud."
        ),
    },
    # Anexo III cat. 3 — Educacion
    "escolar": {
        "annex_ref": "Anexo III cat. 3",
        "recommendation": (
            "Sistema escolar. No discriminacion en acceso educativo, supervision "
            "por personal docente, documentar criterios de evaluacion."
        ),
    },
    "admisión": {
        "annex_ref": "Anexo III cat. 3",
        "recommendation": (
            "Sistema de admision. Transparencia en criterios, auditoria de sesgo, "
            "revision humana de decisiones."
        ),
    },
    # Art. 5 — Prohibiciones
    "manipular": {
        "annex_ref": "Art. 5.1.a EU AI Act",
        "recommendation": (
            "Tecnica manipulativa. PROHIBIDO: los sistemas que emplean tecnicas "
            "subliminales o manipulativas estan prohibidos."
        ),
    },
    "vigilancia": {
        "annex_ref": "Art. 5 EU AI Act",
        "recommendation": (
            "Sistema de vigilancia. Verificar si constituye vigilancia masiva "
            "indiscriminada (prohibida, Art. 5). Si es acotada, Anexo III cat. 1 o 6."
        ),
    },
}


# ---------------------------------------------------------------------------
# Deteccion de casos borderline
# ---------------------------------------------------------------------------

_BORDERLINE_THRESHOLD = 0.20

_SEVERITY: dict[str, int] = {
    "inaceptable": 3,
    "alto_riesgo": 2,
    "riesgo_limitado": 1,
    "riesgo_minimo": 0,
}

_ESCALATION_PAIRS: dict[tuple[str, str], str] = {
    ("alto_riesgo", "inaceptable"): (
        "La probabilidad de 'inaceptable' ({prob:.0%}) es significativa. "
        "Revisar si el sistema incurre en practicas prohibidas del Art. 5."
    ),
    ("riesgo_limitado", "alto_riesgo"): (
        "La probabilidad de 'alto_riesgo' ({prob:.0%}) es significativa. "
        "Revisar si el sistema encaja en alguna categoria del Anexo III."
    ),
    ("riesgo_minimo", "riesgo_limitado"): (
        "La probabilidad de 'riesgo_limitado' ({prob:.0%}) es significativa. "
        "Considerar aplicar las obligaciones de transparencia del Art. 50."
    ),
    ("riesgo_minimo", "alto_riesgo"): (
        "La probabilidad de 'alto_riesgo' ({prob:.0%}) es significativa. "
        "Se recomienda revision detallada frente al Anexo III."
    ),
}


def _detect_borderline(risk_level: str, probabilities: dict[str, float]) -> str | None:
    """Detecta si la clasificacion es borderline via distribucion de probabilidades.

    Un caso es borderline cuando una clase distinta a la predicha tiene
    probabilidad >= _BORDERLINE_THRESHOLD. Se prioriza la escalacion a
    niveles mas restrictivos.
    """
    if not probabilities:
        return None

    other_classes = [
        (cls, prob) for cls, prob in probabilities.items()
        if cls != risk_level and prob >= _BORDERLINE_THRESHOLD
    ]

    if not other_classes:
        return None

    # Priorizar por severidad (más restrictivo primero), luego por probabilidad
    other_classes.sort(
        key=lambda x: (_SEVERITY.get(x[0], 0), x[1]),
        reverse=True,
    )
    concern_class, concern_prob = other_classes[0]

    pair_key = (risk_level, concern_class)
    if pair_key in _ESCALATION_PAIRS:
        return _ESCALATION_PAIRS[pair_key].format(prob=concern_prob)

    return (
        f"Caso borderline: {probabilities.get(risk_level, 0):.0%} {risk_level}, "
        f"{concern_prob:.0%} {concern_class}. Se recomienda revision manual."
    )


# ---------------------------------------------------------------------------
# SHAP features → recomendaciones
# ---------------------------------------------------------------------------

_NO_INTERPRETAR = {"num_palabras", "num_caracteres"}


def _normalize_feature_name(name: str) -> str:
    """Normaliza nombre de feature: quita tildes, minusculas, strip."""
    base = unicodedata.normalize("NFKD", name)
    return "".join(ch for ch in base if not unicodedata.combining(ch)).casefold().strip()


_SHAP_RECS_NORMALIZED: dict[str, dict] = {
    _normalize_feature_name(k): v
    for k, v in _SHAP_FEATURE_RECOMMENDATIONS.items()
}

_NO_INTERPRETAR_NORMALIZED = {_normalize_feature_name(n) for n in _NO_INTERPRETAR}


def _build_shap_recommendations(shap_features: list[dict]) -> list[dict]:
    """Convierte SHAP top features en recomendaciones legales especificas.

    Filtra features no interpretables (svd_N, num_palabras, etc.),
    busca coincidencias en _SHAP_FEATURE_RECOMMENDATIONS y deduplica
    por annex_ref. Normaliza nombres (tildes, mayusculas).
    """
    results = []
    seen_annex_refs: set[str] = set()

    for feat in shap_features:
        raw_name = feat.get("feature")
        if not isinstance(raw_name, str):
            continue

        name = _normalize_feature_name(raw_name)

        if name.startswith("svd_") or name in _NO_INTERPRETAR_NORMALIZED:
            continue

        if name in _SHAP_RECS_NORMALIZED:
            rec = _SHAP_RECS_NORMALIZED[name]
            if rec["annex_ref"] not in seen_annex_refs:
                results.append({
                    "feature": raw_name,
                    "annex_ref": rec["annex_ref"],
                    "recommendation": rec["recommendation"],
                })
                seen_annex_refs.add(rec["annex_ref"])

        if len(results) >= 3:
            break

    return results


# ---------------------------------------------------------------------------
# Funcion principal
# ---------------------------------------------------------------------------

DISCLAIMER = "Informe preliminar generado por IA. Consulte profesional juridico."


def build_compliance_checklist(prediction: dict, system_description: str) -> dict:
    """Construye un checklist de cumplimiento a partir de la prediccion del clasificador.

    Parameters
    ----------
    prediction : dict
        Resultado de predict_risk(): risk_level, confidence, probabilities,
        shap_top_features, annex3_override, annex3_ref, etc.
    system_description : str
        Descripcion original del sistema.

    Returns
    -------
    dict
        Checklist estructurado con obligaciones, recomendaciones y advertencias.
    """
    risk_level = prediction["risk_level"]

    return {
        "system_description": system_description,
        "risk_level": risk_level,
        "confidence": prediction["confidence"],
        "borderline_warning": _detect_borderline(
            risk_level, prediction.get("probabilities", {}),
        ),
        "obligations": _OBLIGATIONS_BY_RISK_LEVEL.get(risk_level, []),
        "specific_recommendations": _build_shap_recommendations(
            prediction.get("shap_top_features", []),
        ),
        "annex3_override": prediction.get("annex3_override", False),
        "annex3_ref": prediction.get("annex3_ref"),
        "disclaimer": DISCLAIMER,
    }
