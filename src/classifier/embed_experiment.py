"""embed_experiment.py — XGBoost con embeddings e5-base como features.

Experimento: reemplazar TF-IDF + SVD por embeddings multilingual-e5-base
(768 dims → PCA 100 dims) + features manuales de keywords.

Hipótesis: los embeddings semánticos capturan mejor el significado legal
que los bigramas TF-IDF, especialmente para textos cortos con vocabulario
especializado poco visto en entrenamiento.

Baseline a superar: F1-macro 0.8780 (XGBoost + TF-IDF + SVD + calibrado)

Criterio de promoción: mejora ≥ 0.005 en F1-macro test.

Nota macOS: OMP_NUM_THREADS=1 y TOKENIZERS_PARALLELISM=false se fijan
al inicio para evitar segfault por conflicto OpenMP entre PyTorch y XGBoost.

Uso
---
    python -m src.classifier.embed_experiment

Artefactos generados (siempre, para análisis posterior)
---------------------------------------------------------
    classifier_dataset_fusionado/model/modelo_e5_xgboost.joblib
    classifier_dataset_fusionado/model/pca_e5.joblib
"""

from __future__ import annotations

import gc
import json
import logging
import os
import re
from pathlib import Path

# Fijar ANTES de importar PyTorch o XGBoost para evitar conflicto OpenMP en macOS
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import joblib
import numpy as np
from sklearn.decomposition import PCA
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import GridSearchCV, StratifiedKFold
from xgboost import XGBClassifier

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_HERE = Path(__file__).parent
_MODEL_DIR = _HERE / "classifier_dataset_fusionado" / "model"
_DATA_DIR = _HERE / "classifier_dataset_fusionado" / "data" / "finetune"

_E5_MODEL = "intfloat/multilingual-e5-base"
_PCA_COMPONENTS = 100
_BASELINE_F1 = 0.8780
_UMBRAL_MEJORA = 0.005

_RE_DESC = re.compile(
    r"###\s*Descripci[oó]n:\s*\n(.*?)\n\n###\s*Clasificaci[oó]n:",
    re.DOTALL,
)


def _extraer_descripcion(text: str) -> str:
    match = _RE_DESC.search(text)
    return match.group(1).strip() if match else text.strip()


def _cargar_jsonl(path: Path) -> tuple[list[str], list[str]]:
    textos, etiquetas = [], []
    with open(path, encoding="utf-8") as f:
        for line in f:
            obj = json.loads(line.strip())
            textos.append(_extraer_descripcion(obj["text"]))
            etiquetas.append(obj["etiqueta"])
    return textos, etiquetas


def _features_manuales(textos: list[str]) -> np.ndarray:
    """Features de keywords — mismas 7 que usa el pipeline TF-IDF actual."""
    from src.classifier._constants import (
        KEYWORDS_DOMINIO as _KW_DOM,
        PALABRAS_SUPERVISION as _KW_SUP,
    )
    from src.classifier.main import _limpiar_texto

    rows = []
    for texto in textos:
        cleaned = _limpiar_texto(texto)
        words = cleaned.split()
        feats = [len(words), len(cleaned)]
        for keywords in _KW_DOM.values():
            feats.append(sum(1 for kw in keywords if kw in words))
        feats.append(sum(1 for kw in _KW_SUP if kw in words))
        rows.append(feats)
    return np.array(rows, dtype=float)


def _generar_embeddings(textos: list[str], model) -> np.ndarray:
    """Genera embeddings e5 con prefijo 'query:' para clasificación."""
    prefixed = [f"query: {t}" for t in textos]
    return model.encode(
        prefixed,
        batch_size=32,
        show_progress_bar=True,
        normalize_embeddings=True,
    ).astype(np.float32)


def experimento() -> None:
    # 1. Cargar datos
    logger.info("Cargando datasets...")
    train_textos, train_etiquetas = _cargar_jsonl(_DATA_DIR / "train.jsonl")
    test_textos, test_etiquetas = _cargar_jsonl(_DATA_DIR / "test.jsonl")
    logger.info("Train: %d | Test: %d", len(train_textos), len(test_textos))

    label_encoder = joblib.load(_MODEL_DIR / "label_encoder.joblib")
    y_train = label_encoder.transform(train_etiquetas)
    y_test = label_encoder.transform(test_etiquetas)

    # 2. Features manuales PRIMERO — antes de cargar PyTorch (evita conflicto OpenMP macOS)
    logger.info("Calculando features manuales (spaCy) antes de cargar PyTorch...")
    manual_train = _features_manuales(train_textos)
    manual_test = _features_manuales(test_textos)
    logger.info("Features manuales: %d columnas", manual_train.shape[1])

    # 3. Cargar e5 y generar embeddings
    logger.info("Cargando modelo e5-base...")
    from sentence_transformers import SentenceTransformer
    e5 = SentenceTransformer(_E5_MODEL)

    logger.info("Generando embeddings train...")
    emb_train = _generar_embeddings(train_textos, e5)
    logger.info("Generando embeddings test...")
    emb_test = _generar_embeddings(test_textos, e5)
    logger.info("Shape embeddings: %s", emb_train.shape)

    # 4. Liberar PyTorch ANTES de XGBoost
    del e5
    gc.collect()
    logger.info("Modelo e5 liberado de memoria")

    # 5. PCA 768 → 100
    logger.info("Aplicando PCA (%d componentes)...", _PCA_COMPONENTS)
    pca = PCA(n_components=_PCA_COMPONENTS, random_state=42)
    X_train = np.hstack([pca.fit_transform(emb_train), manual_train])
    X_test = np.hstack([pca.transform(emb_test), manual_test])
    varianza = pca.explained_variance_ratio_.sum()
    logger.info("Varianza PCA: %.1f%% | Features totales: %d", varianza * 100, X_train.shape[1])

    # 6. Grid Search XGBoost (secuencial — evita segfault macOS)
    logger.info("Grid Search XGBoost (5-fold, secuencial)...")
    param_grid = {
        "n_estimators": [100, 200],
        "max_depth": [3, 5],
        "learning_rate": [0.05, 0.1],
    }
    xgb = XGBClassifier(
        eval_metric="mlogloss",
        random_state=42,
        nthread=1,
    )
    gs = GridSearchCV(
        xgb, param_grid,
        scoring="f1_macro",
        cv=StratifiedKFold(n_splits=5, shuffle=True, random_state=42),
        n_jobs=1,
        verbose=1,
    )
    gs.fit(X_train, y_train)
    logger.info("Mejores params: %s | F1-macro CV: %.4f", gs.best_params_, gs.best_score_)

    # 7. Evaluar en test
    best_model = gs.best_estimator_
    y_pred = best_model.predict(X_test)
    f1_test = f1_score(y_test, y_pred, average="macro")
    logger.info("F1-macro TEST: %.4f (baseline=%.4f)", f1_test, _BASELINE_F1)

    print("\n" + classification_report(y_test, y_pred, target_names=label_encoder.classes_))

    # 8. Guardar artefactos
    model_out = _MODEL_DIR / "modelo_e5_xgboost.joblib"
    pca_out = _MODEL_DIR / "pca_e5.joblib"
    joblib.dump(best_model, model_out)
    joblib.dump(pca, pca_out)
    logger.info("Guardado: %s | %s", model_out, pca_out)

    # 9. Resumen
    mejora = f1_test - _BASELINE_F1
    print("=" * 55)
    print("COMPARACIÓN CON BASELINE")
    print("=" * 55)
    print(f"  Baseline (TF-IDF+SVD+calibrado)  : {_BASELINE_F1:.4f}")
    print(f"  Experimento (e5+PCA+manual)       : {f1_test:.4f}")
    print(f"  Varianza PCA explicada            : {varianza:.1%}")
    print(f"  Mejora                            : {mejora:+.4f}  {'✓ MEJOR' if mejora >= _UMBRAL_MEJORA else '✗ No supera umbral'}")
    print("=" * 55)

    if mejora >= _UMBRAL_MEJORA:
        print("\n✓ Supera el baseline. Integrar como tercer modelo del ensemble")
        print("  o adaptar main.py para pipeline e5+PCA.")
    else:
        print(f"\n[!] Mejora ({mejora:+.4f}) < umbral ({_UMBRAL_MEJORA}).")
        print("    El modelo TF-IDF+calibrado sigue siendo el mejor.")


if __name__ == "__main__":
    experimento()
