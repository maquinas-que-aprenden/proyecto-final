"""classifier/main.py — Servicio de clasificacion de riesgo EU AI Act.

Carga el modelo serializado (LogisticRegression + TF-IDF + OHE) entrenado
en el dataset fusionado y expone ``predict_risk(text) -> dict`` para que
el orquestador lo invoque como tool.

Artefactos requeridos en ``classifier_dataset_fusionado/model/``:
- mejor_modelo.joblib       (LogisticRegression, 5024 features)
- mejor_modelo_tfidf.joblib (TfidfVectorizer, vocab 5000)
- ohe_encoder.joblib        (OneHotEncoder: category + context)
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

import joblib
import numpy as np
from pydantic import BaseModel, Field
from scipy.sparse import csr_matrix, hstack

logger = logging.getLogger(__name__)


class _TextInput(BaseModel):
    text: str = Field(min_length=1, max_length=5000)


# Ruta al mejor modelo (dataset fusionado, F1-macro test: 0.8583)
_MODEL_DIR = Path(__file__).parent / "classifier_dataset_fusionado" / "model"

# Singletons — se cargan en el primer uso (thread-safe)
_modelo = None
_tfidf = None
_ohe = None
_lock = threading.Lock()


def _load_artifacts():
    """Carga lazy de modelo, TF-IDF y OHE encoder (thread-safe, double-check locking)."""
    global _modelo, _tfidf, _ohe
    if _modelo is not None and _tfidf is not None and _ohe is not None:
        return
    with _lock:
        if _modelo is not None and _tfidf is not None and _ohe is not None:
            return

        meta_path = _MODEL_DIR / "mejor_modelo_seleccion.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            model_file = _MODEL_DIR.parent / meta["model_file"]
            tfidf_file = _MODEL_DIR.parent / meta["tfidf_file"]
            logger.info("Cargando modelo desde metadata: %s", meta.get("nombre", ""))
        else:
            model_file = _MODEL_DIR / "mejor_modelo.joblib"
            tfidf_file = _MODEL_DIR / "mejor_modelo_tfidf.joblib"

        try:
            _modelo = joblib.load(model_file)
            _tfidf = joblib.load(tfidf_file)
            _ohe = joblib.load(_MODEL_DIR / "ohe_encoder.joblib")
        except Exception:
            _modelo = _tfidf = _ohe = None
            raise
        logger.info(
            "Clasificador cargado: %s (%d features) desde %s",
            type(_modelo).__name__,
            _modelo.n_features_in_,
            _MODEL_DIR,
        )


def _limpiar_texto_fallback(texto: str) -> str:
    """Limpieza basica con regex (misma logica que functions._limpiar_texto_fallback)."""
    import re

    if not texto or not isinstance(texto, str):
        return ""

    _stopwords = {
        "a", "al", "algo", "algunas", "algunos", "ante", "antes", "como",
        "con", "contra", "cual", "cuando", "de", "del", "desde", "donde",
        "durante", "e", "el", "ella", "ellos", "en", "entre", "era", "es",
        "esa", "esas", "ese", "eso", "esos", "esta", "estas", "este", "esto",
        "estos", "fue", "ha", "han", "hasta", "hay", "he", "la", "las", "le",
        "les", "lo", "los", "me", "mi", "mis", "muy", "ni", "no", "nos",
        "o", "os", "otro", "para", "pero", "por", "que", "quien", "quienes",
        "se", "si", "sin", "sobre", "son", "su", "sus", "también", "tanto",
        "te", "todo", "todos", "tu", "tus", "un", "una", "unas", "uno",
        "unos", "ya", "yo",
    }
    tokens = re.findall(r"\b[a-záéíóúüñ]{3,}\b", texto.lower())
    return " ".join(t for t in tokens if t not in _stopwords)


def _limpiar_texto(texto: str) -> str:
    """Limpia texto para inferencia, usando spaCy si esta disponible."""
    try:
        from src.classifier.functions import limpiar_texto
        return limpiar_texto(texto)
    except ImportError:
        return _limpiar_texto_fallback(texto)


def predict_risk(text: str) -> dict:
    """Clasifica un sistema de IA por nivel de riesgo EU AI Act.

    Parameters
    ----------
    text : str
        Descripcion del sistema de IA en lenguaje natural.

    Returns
    -------
    dict
        risk_level: str (alto_riesgo | inaceptable | riesgo_limitado | riesgo_minimo)
        confidence: float (0-1)
        shap_top_features: list[dict] (top 5 features por contribucion)
        shap_explanation: str (resumen textual)
    """
    _TextInput(text=text)
    _load_artifacts()

    # 1. Limpiar texto (mismo preprocesado que en entrenamiento)
    cleaned = _limpiar_texto(text)

    # 2. TF-IDF
    X_tfidf = _tfidf.transform([cleaned])

    # 3. OHE — en inferencia libre no tenemos category/context estructurados,
    #    asi que pasamos vectores zero (handle_unknown="ignore" en entrenamiento).
    #    El TF-IDF (5000 features) lleva la mayor parte de la senal.
    n_ohe = sum(len(c) for c in _ohe.categories_)
    X_ohe = csr_matrix((1, n_ohe))

    # 4. Features numericas: longitud y num_articles
    #    Sin metadata estructurada, usamos 0 para evitar sesgos por escala.
    X_num = csr_matrix((1, 2), dtype=float)

    # 5. Combinar (mismo orden que en entrenamiento: tfidf + ohe + num)
    X_final = hstack([X_tfidf, X_ohe, X_num])

    # 6. Prediccion
    risk_level = _modelo.predict(X_final)[0]
    proba = _modelo.predict_proba(X_final)[0]
    confidence = float(proba.max())

    result = {
        "risk_level": risk_level,
        "confidence": confidence,
        "probabilities": {
            cls: round(float(p), 4)
            for cls, p in zip(_modelo.classes_, proba)
        },
    }

    # 7. Explicabilidad — contribuciones lineales (coef * feature_value)
    try:
        pred_idx = list(_modelo.classes_).index(risk_level)
        coefs = _modelo.coef_[pred_idx]
        X_dense = X_final.toarray().flatten()
        contributions = coefs * X_dense

        tfidf_names = _tfidf.get_feature_names_out().tolist()
        ohe_names = _ohe.get_feature_names_out().tolist()
        num_names = ["longitud", "num_articles"]
        feature_names = tfidf_names + ohe_names + num_names

        top_idx = np.argsort(np.abs(contributions))[::-1][:5]
        shap_top = [
            {"feature": feature_names[i], "contribution": float(contributions[i])}
            for i in top_idx
            if contributions[i] != 0
        ]

        if shap_top:
            result["shap_top_features"] = shap_top
            top_words = ", ".join(f["feature"] for f in shap_top[:3])
            result["shap_explanation"] = (
                f"Factores principales para '{risk_level}': {top_words}."
            )
    except Exception as e:
        logger.warning("No se pudo calcular explicabilidad: %s", e)

    return result


if __name__ == "__main__":
    test_cases = [
        "Sistema de puntuacion social de ciudadanos",
        "Reconocimiento facial en aeropuertos para control de acceso",
        "Chatbot de atencion al cliente para una tienda online",
        "Filtro de spam de email corporativo",
        "Sistema de scoring crediticio para concesion de prestamos bancarios",
    ]
    for desc in test_cases:
        r = predict_risk(desc)
        print(f"  {r['risk_level']:>17} ({r['confidence']:.0%}) <- {desc}")
        if r.get("shap_top_features"):
            top = ", ".join(f["feature"] for f in r["shap_top_features"][:3])
            print(f"                    Factores: {top}")
        print()

    print("classifier/main.py OK")
