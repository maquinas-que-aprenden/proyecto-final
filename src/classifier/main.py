"""classifier/main.py — Servicio de clasificación de riesgo EU AI Act.

Carga el modelo ganador (según mejor_modelo_seleccion.json) y expone
predict_risk(text) para uso desde el orquestador.
"""

import json
import joblib
import numpy as np
from pathlib import Path
from scipy.sparse import csr_matrix

from .functions import limpiar_texto

_EXPERIMENT_DIR = Path(__file__).parent / "classifier_dataset_fusionado"
_LABEL_NAMES = ["inaceptable", "alto", "limitado", "minimo"]

_clf = None
_tfidf = None


def _cargar_si_necesario() -> None:
    """Carga el modelo y vectorizador la primera vez que se invocan (lazy loading)."""
    global _clf, _tfidf
    if _clf is not None:
        return
    meta = json.loads(
        (_EXPERIMENT_DIR / "model" / "mejor_modelo_seleccion.json").read_text(encoding="utf-8")
    )
    _clf = joblib.load(_EXPERIMENT_DIR / meta["model_file"])
    _tfidf = joblib.load(_EXPERIMENT_DIR / meta["tfidf_file"])


def _shap_top_features(X_sparse, label_idx: int, top_n: int = 5) -> list[dict]:
    """
    Devuelve las top_n features con mayor contribución SHAP para la clase predicha.
    Usa zero background (apropiado para TF-IDF: ausencia de término = 0).
    Fallback: coef * x, matemáticamente equivalente para modelos lineales con zero background.
    """
    try:
        import shap
        background = csr_matrix(np.zeros((1, X_sparse.shape[1])))
        explainer = shap.LinearExplainer(_clf, background)
        shap_vals = explainer.shap_values(X_sparse)
        vals = shap_vals[label_idx][0]
    except Exception:
        vals = _clf.coef_[label_idx] * X_sparse.toarray()[0]

    feature_names = _tfidf.get_feature_names_out()
    top_idx = np.argsort(np.abs(vals))[-top_n:][::-1]

    return [
        {"feature": feature_names[i], "contribucion": round(float(vals[i]), 4)}
        for i in top_idx
        if abs(vals[i]) > 1e-6
    ]


def predict_risk(text: str) -> dict:
    """Clasifica un sistema de IA en uno de los 4 niveles de riesgo del EU AI Act.

    Args:
        text: Descripción del sistema de IA a clasificar.

    Returns:
        dict con risk_level (0-3), risk_name, confidence, probabilities y shap_top_features.
        shap_top_features: lista de {feature, contribucion} donde contribucion > 0
        empuja hacia la clase predicha y < 0 la reduce.
    """
    _cargar_si_necesario()
    texto_limpio = limpiar_texto(text)
    X = _tfidf.transform([texto_limpio])
    label_idx = int(_clf.predict(X)[0])
    proba = _clf.predict_proba(X)[0]

    return {
        "risk_level": label_idx,
        "risk_name": _LABEL_NAMES[label_idx],
        "confidence": round(float(proba.max()), 4),
        "probabilities": {
            name: round(float(p), 4)
            for name, p in zip(_LABEL_NAMES, proba)
        },
        "shap_top_features": _shap_top_features(X, label_idx),
    }


if __name__ == "__main__":
    test_cases = [
        "Sistema de puntuación social de ciudadanos",
        "Reconocimiento facial en aeropuertos",
        "Chatbot de atención al cliente",
        "Filtro de spam de email",
    ]
    print("Predicciones:")
    for desc in test_cases:
        result = predict_risk(desc)
        top = result["shap_top_features"][:3]
        features_str = ", ".join(f"{f['feature']} ({f['contribucion']:+.3f})" for f in top)
        print(f"  {result['risk_name']:>13} ({result['confidence']:.0%}) ← {desc}")
        print(f"    Top features: {features_str}")

    print("\n✓ classifier/main.py OK")
