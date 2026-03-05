"""retrain.py — Reentrenamiento del clasificador con datos aumentados del Anexo III.

Replica el pipeline del notebook 7 (experimento 2: XGBoost + SVD + features manuales)
añadiendo los ejemplos de annex3_aumentacion.csv al conjunto de entrenamiento.

Uso (desde la raíz del proyecto):
    python -m src.classifier.retrain

Dependencias: pandas, numpy, scikit-learn, xgboost, joblib
No requiere spaCy ni MLflow para ejecutarse.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import classification_report, f1_score
from sklearn.preprocessing import LabelEncoder
from sklearn.utils.class_weight import compute_sample_weight
from src.classifier._constants import (
    KEYWORDS_DOMINIO as _KEYWORDS_DOMINIO,
    PALABRAS_SUPERVISION as _PALABRAS_SUPERVISION,
    STOPWORDS_ES as _STOPWORDS_ES,
)
try:
    from xgboost import XGBClassifier
except ImportError:  # pragma: no cover
    XGBClassifier = None  # type: ignore[assignment,misc]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── Rutas ──────────────────────────────────────────────────────────────────────
_HERE = Path(__file__).parent
_FUSIONADO = _HERE / "classifier_dataset_fusionado"
_DATA_DIR = _FUSIONADO / "data"
_MODEL_DIR = _FUSIONADO / "model"

_TRAIN_JSONL = _DATA_DIR / "finetune" / "train.jsonl"
_TEST_JSONL = _DATA_DIR / "finetune" / "test.jsonl"
_AUGMENT_CSV = _DATA_DIR / "annex3_aumentacion.csv"
# Ejemplos contrastivos inaceptable/alto_riesgo (cargados si existen)
_CONTRASTIVA_CSV = _DATA_DIR / "aumentacion_contrastiva.csv"

# ── Dimensionalidad SVD ───────────────────────────────────────────────────────
# Centralizado aquí para que el JSON de selección y el código usen el mismo valor.
# Si se cambia, main.py lo leerá desde svd_transformer.joblib via _svd.n_components.
_SVD_N_COMPONENTS = 100

# ── Hiperparámetros (best_params del experimento 2) ───────────────────────────
_BEST_PARAMS = {
    "n_estimators": 300,
    "max_depth": 3,
    "learning_rate": 0.1,
    "subsample": 0.8,
    "random_state": 42,
    "eval_metric": "mlogloss",
}

# ── Helpers ────────────────────────────────────────────────────────────────────

def _limpiar_texto(texto: str) -> str:
    """Limpieza básica con regex (fallback sin spaCy)."""
    if not texto or not isinstance(texto, str):
        return ""
    tokens = re.findall(r"\b[a-záéíóúüñ]{3,}\b", texto.lower())
    return " ".join(t for t in tokens if t not in _STOPWORDS_ES)


def _extraer_descripcion(text: str) -> str:
    """Extrae el fragmento entre '### Descripción:' y '### Clasificación:' del JSONL."""
    match = re.search(
        r"###\s*Descripci[oó]n:\s*(.*?)\s*###\s*Clasificaci[oó]n:",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if match:
        return match.group(1).strip()
    return text


def _cargar_jsonl(path: Path) -> pd.DataFrame:
    """Carga un fichero JSONL con campos 'text' y 'etiqueta'."""
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            descripcion = _extraer_descripcion(obj.get("text", ""))
            etiqueta = obj.get("etiqueta", "")
            rows.append({"descripcion": descripcion, "etiqueta": etiqueta})
    return pd.DataFrame(rows)


def _crear_features_manuales(texts: pd.Series) -> np.ndarray:
    """Genera features de keywords: num_palabras, num_chars, kw_* por clase, kw_salvaguarda."""
    result = []
    for t in texts:
        words = t.split()
        row = [len(words), len(t)]
        for keywords in _KEYWORDS_DOMINIO.values():
            row.append(sum(1 for kw in keywords if kw in words))
        row.append(sum(1 for kw in _PALABRAS_SUPERVISION if kw in words))
        result.append(row)
    return np.array(result, dtype=float)


# ── Pipeline principal ─────────────────────────────────────────────────────────

_PROMOTE_DELTA = 0.005  # margen mínimo de mejora sobre F1 anterior para promover artefactos


def main(*, force_promote: bool = False) -> None:
    logger.info("=== Reentrenamiento clasificador EU AI Act (Anexo III augmented) ===")

    # 1. Leer train.jsonl
    if not _TRAIN_JSONL.exists():
        logger.error("No se encuentra train.jsonl: %s", _TRAIN_JSONL)
        sys.exit(1)
    df_train = _cargar_jsonl(_TRAIN_JSONL)
    logger.info("train.jsonl: %d ejemplos", len(df_train))

    # 2. Leer ficheros de augmentación (ambos opcionales)
    dfs_aug = []
    if _AUGMENT_CSV.exists():
        df_aug = pd.read_csv(_AUGMENT_CSV)
        dfs_aug.append(df_aug)
        logger.info("annex3_aumentacion.csv: %d ejemplos", len(df_aug))
    else:
        logger.warning("annex3_aumentacion.csv no encontrado, se omite: %s", _AUGMENT_CSV)

    if _CONTRASTIVA_CSV.exists():
        df_contrastiva = pd.read_csv(_CONTRASTIVA_CSV)
        dfs_aug.append(df_contrastiva)
        logger.info("aumentacion_contrastiva.csv: %d ejemplos", len(df_contrastiva))
    else:
        logger.warning("aumentacion_contrastiva.csv no encontrado, se omite: %s", _CONTRASTIVA_CSV)

    # 3. Concatenar y limpiar
    df_all = pd.concat([df_train, *dfs_aug], ignore_index=True)
    df_all = df_all.dropna(subset=["descripcion", "etiqueta"])
    df_all["texto_limpio"] = df_all["descripcion"].apply(_limpiar_texto)
    logger.info("Dataset augmentado total: %d ejemplos", len(df_all))
    logger.info("Distribución de clases:\n%s", df_all["etiqueta"].value_counts().to_string())

    # 4. Leer test.jsonl
    if not _TEST_JSONL.exists():
        logger.error("No se encuentra test.jsonl: %s", _TEST_JSONL)
        sys.exit(1)
    df_test = _cargar_jsonl(_TEST_JSONL)
    df_test["texto_limpio"] = df_test["descripcion"].apply(_limpiar_texto)
    logger.info("test.jsonl: %d ejemplos", len(df_test))

    X_train_text = df_all["texto_limpio"]
    y_train = df_all["etiqueta"]
    X_test_text = df_test["texto_limpio"]
    y_test = df_test["etiqueta"]

    # 5. TF-IDF (fit solo sobre train augmentado)
    tfidf = TfidfVectorizer(
        max_features=5000,
        ngram_range=(1, 2),
        sublinear_tf=True,
        min_df=1,
        token_pattern=r"(?u)\b[a-zA-ZáéíóúüñÁÉÍÓÚÜÑ]{3,}\b",
    )
    X_train_tfidf = tfidf.fit_transform(X_train_text)
    X_test_tfidf = tfidf.transform(X_test_text)
    logger.info("TF-IDF vocabulario: %d términos", len(tfidf.vocabulary_))

    # 6. SVD(100)
    svd = TruncatedSVD(n_components=_SVD_N_COMPONENTS, random_state=42)
    X_train_svd = svd.fit_transform(X_train_tfidf)
    X_test_svd = svd.transform(X_test_tfidf)
    logger.info(
        "SVD(%d): varianza explicada acumulada = %.3f",
        _SVD_N_COMPONENTS,
        svd.explained_variance_ratio_.sum(),
    )

    # 7. Features manuales
    X_train_manual = _crear_features_manuales(X_train_text)
    X_test_manual = _crear_features_manuales(X_test_text)

    X_train_final = np.hstack([X_train_svd, X_train_manual])
    X_test_final = np.hstack([X_test_svd, X_test_manual])
    logger.info("Features totales: %d", X_train_final.shape[1])

    # 8. Label encoder + XGBoost
    if XGBClassifier is None:
        raise ImportError("xgboost no está instalado. Ejecuta: pip install xgboost")

    le = LabelEncoder()
    y_train_enc = le.fit_transform(y_train)

    sample_weight = compute_sample_weight(class_weight="balanced", y=y_train_enc)

    modelo = XGBClassifier(**_BEST_PARAMS)
    modelo.fit(X_train_final, y_train_enc, sample_weight=sample_weight)
    logger.info("XGBoost entrenado con %d ejemplos", len(y_train_enc))

    # 9. Evaluar en test
    y_pred_enc = modelo.predict(X_test_final)
    y_pred = le.inverse_transform(y_pred_enc)

    print("\n=== Resultados en TEST (augmented) ===\n")
    print(classification_report(y_test, y_pred))
    f1_macro = f1_score(y_test, y_pred, average="macro")
    logger.info("F1-macro test: %.4f", f1_macro)

    # 10. Guardar artefactos solo si mejora el score anterior
    _MODEL_DIR.mkdir(parents=True, exist_ok=True)
    seleccion_path = _MODEL_DIR / "mejor_modelo_seleccion.json"
    meta: dict = {}
    if seleccion_path.exists():
        meta = json.loads(seleccion_path.read_text(encoding="utf-8"))
    prev_f1 = meta.get("test_f1_macro", 0.0)

    if f1_macro > prev_f1 + _PROMOTE_DELTA or force_promote:
        joblib.dump(modelo, _MODEL_DIR / "modelo_xgboost.joblib")
        joblib.dump(tfidf, _MODEL_DIR / "tfidf_vectorizer.joblib")
        joblib.dump(svd, _MODEL_DIR / "svd_transformer.joblib")
        joblib.dump(le, _MODEL_DIR / "label_encoder.joblib")
        logger.info("Artefactos guardados en %s (F1: %.4f → %.4f)", _MODEL_DIR, prev_f1, f1_macro)

        meta.update({
            "nombre": "Exp 2: XGBoost + SVD + GS (augmented Anexo III)",
            "model_file": "model/modelo_xgboost.joblib",
            "tfidf_file": "model/tfidf_vectorizer.joblib",
            "model_type": "XGBClassifier",
            "pipeline_type": "tfidf_svd_manual",
            "experimento": "2",
            "needs_manual_features": True,
            "test_f1_macro": round(f1_macro, 4),
            "augmented_examples": sum(len(d) for d in dfs_aug),
            "augmented": bool(sum(len(d) for d in dfs_aug)),
            "fecha_reentrenamiento": datetime.now().isoformat(),
        })
        seleccion_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("mejor_modelo_seleccion.json actualizado")
        print("\n✓ Reentrenamiento completado. F1-macro test:", round(f1_macro, 4))
    else:
        logger.warning(
            "Promoción abortada: nuevo F1 (%.4f) no supera anterior (%.4f) + delta (%.3f)",
            f1_macro, prev_f1, _PROMOTE_DELTA,
        )
        print(f"\n⚠ Modelo NO promovido. F1 nuevo ({f1_macro:.4f}) ≤ F1 anterior ({prev_f1:.4f})")


if __name__ == "__main__":
    main()
