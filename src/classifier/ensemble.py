"""ensemble.py — Ensemble XGBoost + BERT para clasificación de riesgo EU AI Act.

Estrategia: media ponderada de probabilidades
    P_ensemble = W_XGBOOST × P_xgboost + W_BERT × P_bert

Pesos asimétricos (XGBoost F1=0.8822 >> BERT F1=0.7289): XGBoost lleva más peso.

Comportamiento ante casos especiales
-------------------------------------
- Anexo III override: si XGBoost ya fue sobreescrito por regla legal determinista,
  el resultado se devuelve tal cual sin mezclar con BERT. La ley prevalece.
- BERT no disponible: degradación silenciosa a solo XGBoost (FileNotFoundError
  o cualquier excepción de carga del modelo).
- Etiquetas distintas entre modelos: la combinación de probabilidades
  normaliza automáticamente sobre la unión de etiquetas.

Uso
---
    from src.classifier.ensemble import predict_ensemble
    result = predict_ensemble("Sistema de reconocimiento facial en espacios públicos")
    print(result["risk_level"], result["ensemble_mode"])
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Pesos del ensemble — deben sumar 1.0
_W_XGBOOST: float = 0.7
_W_BERT: float = 0.3


def predict_ensemble(text: str) -> dict:
    """Clasifica un sistema de IA usando ensemble XGBoost + BERT.

    Parameters
    ----------
    text : str
        Descripción del sistema de IA en lenguaje natural.

    Returns
    -------
    dict
        Mismo formato que ``predict_risk()``:
        - risk_level    : str
        - confidence    : float
        - probabilities : dict[str, float]
        - shap_top_features : list[dict] (solo de XGBoost)
        - shap_explanation  : str
        - ensemble_mode : "xgboost_bert" | "xgboost_only" | "annex3_override"
        - ensemble_weights  : dict (solo cuando ensemble_mode == "xgboost_bert")
    """
    from src.classifier.main import predict_risk, _annex3_override

    # 1. Predicción XGBoost (siempre disponible, incluye Anexo III)
    xgb_result = predict_risk(text)

    # 2. Si Anexo III sobreescribió la predicción, el override legal no se mezcla.
    #    Las probabilidades en ese caso son recalibradas (no reales), así que
    #    devolvemos el resultado XGBoost directamente.
    if xgb_result.get("annex3_override"):
        xgb_result["ensemble_mode"] = "annex3_override"
        return xgb_result

    # 3. Intentar predicción BERT con degradación graceful
    bert_result = _try_bert(text)

    if bert_result is None:
        xgb_result["ensemble_mode"] = "xgboost_only"
        return xgb_result

    # 4. Combinar probabilidades con media ponderada
    ensemble_proba = _combine_probabilities(
        xgb_result["probabilities"],
        bert_result["probabilities"],
    )

    risk_level = max(ensemble_proba, key=ensemble_proba.get)
    confidence = ensemble_proba[risk_level]

    result: dict = {
        "risk_level": risk_level,
        "confidence": round(confidence, 4),
        "probabilities": {k: round(v, 4) for k, v in ensemble_proba.items()},
        "ensemble_mode": "xgboost_bert",
        "ensemble_weights": {"xgboost": _W_XGBOOST, "bert": _W_BERT},
    }

    # 5. Preservar SHAP de XGBoost — BERT no lo soporta
    if xgb_result.get("shap_top_features"):
        result["shap_top_features"] = xgb_result["shap_top_features"]
    if xgb_result.get("shap_explanation"):
        result["shap_explanation"] = xgb_result["shap_explanation"]

    # 6. Aplicar Anexo III sobre el resultado del ensemble
    result = _annex3_override(text, result)

    return result


def _try_bert(text: str) -> Optional[dict]:
    """Intenta predecir con BERT. Devuelve None si el modelo no está disponible."""
    try:
        from src.classifier.bert_pipeline.bert.predict import predict as bert_predict
        return bert_predict(text)
    except FileNotFoundError:
        logger.warning("Modelo BERT no encontrado — ensemble usando solo XGBoost")
        return None
    except Exception as exc:
        logger.warning("Error en predicción BERT (%s) — ensemble usando solo XGBoost", exc)
        return None


def _combine_probabilities(xgb_proba: dict, bert_proba: dict) -> dict:
    """Media ponderada de probabilidades entre XGBoost y BERT.

    Normaliza sobre la unión de etiquetas por si los label encoders
    de ambos modelos tienen clases en distinto orden o nombres distintos.
    """
    all_labels = set(xgb_proba) | set(bert_proba)
    combined = {
        label: _W_XGBOOST * xgb_proba.get(label, 0.0) + _W_BERT * bert_proba.get(label, 0.0)
        for label in all_labels
    }

    # Normalizar por si las etiquetas no coinciden perfectamente
    total = sum(combined.values())
    if total > 0:
        combined = {k: v / total for k, v in combined.items()}

    return combined


if __name__ == "__main__":
    test_cases = [
        "Sistema de puntuacion social de ciudadanos en la via publica",
        "Reconocimiento facial en aeropuertos para control de acceso",
        "Chatbot de atencion al cliente para una tienda online",
        "Filtro de spam de email corporativo",
        "Sistema de scoring crediticio para concesion de prestamos bancarios",
    ]
    for desc in test_cases:
        r = predict_ensemble(desc)
        mode = r.get("ensemble_mode", "?")
        print(f"  [{mode}] {r['risk_level']:>17} ({r['confidence']:.0%}) <- {desc}")
        if r.get("shap_explanation"):
            print(f"           Explicacion: {r['shap_explanation']}")
        print()

    print("classifier/ensemble.py OK")
