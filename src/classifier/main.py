"""classifier/main.py — Servicio de clasificacion de riesgo EU AI Act.

Carga el modelo serializado entrenado en el dataset fusionado y expone
``predict_risk(text) -> dict`` para que el orquestador lo invoque como tool.

Seleccion de modelo: Se entrenaron y evaluaron tres variantes (LogReg,
LogReg+features manuales, XGBoost+SVD) con Grid Search + StratifiedKFold.
Los tres experimentos estan registrados en MLflow. El modelo seleccionado
se determina por ``mejor_modelo_seleccion.json``. Actualmente:
Exp 2 (XGBoost + SVD + GS) con F1-macro test 0.8822.

Pipeline de inferencia: texto → TF-IDF → SVD(100) + 7 keywords → XGBoost.

Artefactos requeridos en ``classifier_dataset_fusionado/model/``:
- mejor_modelo.joblib / modelo_xgboost.joblib  (modelo seleccionado)
- mejor_modelo_tfidf.joblib / tfidf_vectorizer.joblib (TfidfVectorizer)
- svd_transformer.joblib    (TruncatedSVD, 100 componentes)
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

import joblib
import numpy as np
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class _TextInput(BaseModel):
    text: str = Field(min_length=1, max_length=5000)


# Keywords de dominio (replica de functions.py para inferencia sin spaCy)
_KEYWORDS_DOMINIO = {
    "inaceptable": [
        "inferir", "vender", "manipular", "subconsciente", "biométrico",
        "facial", "vigilancia", "sindical", "racial", "etnia",
        "religioso", "discriminar", "coerción", "prohibido",
    ],
    "alto_riesgo": [
        "penitenciario", "juez", "reincidencia", "crediticio",
        "diagnóstico", "sanitario", "migración", "asilo",
        "policial", "empleabilidad", "infraestructura", "vinculante",
        "medicación", "autónomamente",
        "reclamación", "subsidio", "escolar", "triage",
        "urgencia", "aeronave", "piloto", "laboral",
    ],
    "riesgo_limitado": [
        "chatbot", "revelar", "transparencia", "deepfake",
        "sintético", "notificar", "asesoramiento", "asistente",
        "informar", "advertir", "indicar",
    ],
    "riesgo_minimo": [
        "sugerir", "borrador", "juego", "spam", "entretenimiento",
        "filtro", "aficionado", "hobby", "receta",
        "avería", "maquinaria", "logística", "mantenimiento",
        "sensor", "industrial", "gestión",
    ],
}
_PALABRAS_SUPERVISION = [
    "supervisión", "supervisar", "revisar", "revisión", "garantía",
    "confirmación", "criterio", "auditoría", "humano",
    "pediatra", "médico", "piloto", "pedagógico",
]

# Ruta al mejor modelo (dataset fusionado)
_MODEL_DIR = Path(__file__).parent / "classifier_dataset_fusionado" / "model"

# Singletons — se cargan en el primer uso (thread-safe)
_modelo = None
_tfidf = None
_svd = None
_label_encoder = None
_needs_svd = False
_lock = threading.Lock()


def _load_artifacts():
    """Carga lazy de modelo, TF-IDF y SVD (thread-safe, double-check locking)."""
    global _modelo, _tfidf, _svd, _label_encoder, _needs_svd
    if _modelo is not None and _tfidf is not None:
        return
    with _lock:
        if _modelo is not None and _tfidf is not None:
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
            # SVD solo se necesita para el pipeline XGBoost
            svd_path = _MODEL_DIR / "svd_transformer.joblib"
            if svd_path.exists():
                _svd = joblib.load(svd_path)
                _needs_svd = True
            # Label encoder para decodificar predicciones numericas
            le_path = _MODEL_DIR / "label_encoder.joblib"
            if le_path.exists():
                _label_encoder = joblib.load(le_path)
        except Exception:
            _modelo = _tfidf = _svd = _label_encoder = None
            _needs_svd = False
            raise
        logger.info(
            "Clasificador cargado: %s (%d features, SVD=%s) desde %s",
            type(_modelo).__name__,
            _modelo.n_features_in_,
            _needs_svd,
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


def _crear_features_manuales(text: str) -> np.ndarray:
    """Genera las 7 features de keywords para el pipeline XGBoost+SVD."""
    words = text.split()
    features = [
        len(words),   # num_palabras
        len(text),    # num_caracteres
    ]
    for keywords in _KEYWORDS_DOMINIO.values():
        features.append(sum(1 for kw in keywords if kw in words))
    features.append(sum(1 for kw in _PALABRAS_SUPERVISION if kw in words))
    return np.array(features, dtype=float).reshape(1, -1)


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

    # 3. Construir features segun pipeline del modelo
    if _needs_svd:
        # Pipeline XGBoost: TF-IDF → SVD(100) + 7 keyword features = 107
        X_svd = _svd.transform(X_tfidf)
        X_manual = _crear_features_manuales(cleaned)
        X_final = np.hstack([X_svd, X_manual])
        feature_names = (
            [f"svd_{i}" for i in range(_svd.n_components)]
            + ["num_palabras", "num_caracteres"]
            + [f"kw_{c}" for c in _KEYWORDS_DOMINIO]
            + ["kw_salvaguarda"]
        )
    else:
        # Pipeline LogReg: TF-IDF directo (sparse)
        X_final = X_tfidf
        feature_names = _tfidf.get_feature_names_out().tolist()

    # 4. Prediccion
    raw_pred = _modelo.predict(X_final)[0]
    proba = _modelo.predict_proba(X_final)[0]
    confidence = float(proba.max())

    # Decodificar etiqueta numerica a string si hay label encoder
    if _label_encoder is not None and not isinstance(raw_pred, str):
        risk_level = _label_encoder.inverse_transform([raw_pred])[0]
        class_names = _label_encoder.inverse_transform(_modelo.classes_)
    else:
        risk_level = str(raw_pred)
        class_names = _modelo.classes_

    result = {
        "risk_level": risk_level,
        "confidence": confidence,
        "probabilities": {
            str(cls): round(float(p), 4)
            for cls, p in zip(class_names, proba)
        },
    }

    # 5. Explicabilidad — top features por contribucion
    try:
        if hasattr(_modelo, "coef_"):
            # LogReg: contribuciones lineales
            pred_idx = list(_modelo.classes_).index(risk_level)
            coefs = _modelo.coef_[pred_idx]
            X_dense = X_final.toarray().flatten() if hasattr(X_final, "toarray") else X_final.flatten()
            contributions = coefs * X_dense
        elif hasattr(_modelo, "feature_importances_"):
            # XGBoost: feature importances globales
            contributions = _modelo.feature_importances_
        else:
            contributions = None

        if contributions is not None:
            top_idx = np.argsort(np.abs(contributions))[::-1][:5]
            shap_top = [
                {"feature": feature_names[i], "contribution": float(contributions[i])}
                for i in top_idx
                if i < len(feature_names) and contributions[i] != 0
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
