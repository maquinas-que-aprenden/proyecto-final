"""calibrate.py — Calibración de probabilidades del clasificador XGBoost.

Aplica calibración isotónica (one-vs-rest) sobre el modelo XGBoost ya entrenado,
usando el conjunto de test como held-out set.

Por qué calibrar
----------------
XGBoost tiende a producir probabilidades extremas (muy altas o muy bajas)
que no reflejan la incertidumbre real del modelo. La calibración isotónica
ajusta las probabilidades para que, cuando el modelo dice "85% de confianza",
el sistema acierte aproximadamente el 85% de las veces.

Esto es especialmente importante para el ensemble XGBoost + BERT:
los pesos 0.7/0.3 asumen que ambas probabilidades están en la misma escala.
Si XGBoost está mal calibrado, el ensemble hereda ese sesgo.

Mejora esperada
---------------
- Brier score más bajo (menor error cuadrático en probabilidades)
- Confianzas del ensemble más fiables

Uso
---
    python -m src.classifier.calibrate

Artefactos generados
--------------------
    classifier_dataset_fusionado/model/modelo_xgboost_calibrated.joblib

Actualizar mejor_modelo_seleccion.json para apuntar al modelo calibrado
si el Brier score mejora ≥ 0.005.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import joblib
import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss, f1_score
from sklearn.model_selection import train_test_split
from src.classifier._calibrated_model import IsotonicCalibratedXGB  # noqa: F401 (re-export para pickle)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_HERE = Path(__file__).parent
_MODEL_DIR = _HERE / "classifier_dataset_fusionado" / "model"
_DATA_DIR = _HERE / "classifier_dataset_fusionado" / "data" / "finetune"

_RE_DESC = re.compile(
    r"###\s*Descripci[oó]n:\s*\n(.*?)\n\n###\s*Clasificaci[oó]n:",
    re.DOTALL,
)



def _extraer_descripcion(text: str) -> str:
    match = _RE_DESC.search(text)
    if match:
        return match.group(1).strip()
    return text.strip()


def _cargar_test_set() -> tuple[list[str], list[str]]:
    path = _DATA_DIR / "test.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"Test set no encontrado: {path}")

    textos, etiquetas = [], []
    with open(path, encoding="utf-8") as f:
        for line in f:
            obj = json.loads(line.strip())
            textos.append(_extraer_descripcion(obj["text"]))
            etiquetas.append(obj["etiqueta"])

    logger.info("Test set cargado: %d ejemplos", len(textos))
    return textos, etiquetas


def _build_X(textos: list[str], tfidf, svd) -> np.ndarray:
    from src.classifier.main import _limpiar_texto
    from src.classifier._constants import (
        KEYWORDS_DOMINIO as _KW_DOM,
        PALABRAS_SUPERVISION as _KW_SUP,
    )

    Xs = []
    for texto in textos:
        cleaned = _limpiar_texto(texto)
        X_svd = svd.transform(tfidf.transform([cleaned]))
        words = cleaned.split()
        manual = [len(words), len(cleaned)]
        for keywords in _KW_DOM.values():
            manual.append(sum(1 for kw in keywords if kw in words))
        manual.append(sum(1 for kw in _KW_SUP if kw in words))
        Xs.append(np.hstack([X_svd, np.array(manual, dtype=float).reshape(1, -1)]))

    return np.vstack(Xs)


def _brier_multiclass(y_enc: np.ndarray, proba: np.ndarray, n_classes: int) -> float:
    scores = [
        brier_score_loss((y_enc == i).astype(float), proba[:, i])
        for i in range(n_classes)
    ]
    return float(np.mean(scores))


def calibrar() -> None:
    # 1. Cargar artefactos
    logger.info("Cargando artefactos del modelo...")
    modelo = joblib.load(_MODEL_DIR / "modelo_xgboost.joblib")
    tfidf = joblib.load(_MODEL_DIR / "tfidf_vectorizer.joblib")
    svd = joblib.load(_MODEL_DIR / "svd_transformer.joblib")
    label_encoder = joblib.load(_MODEL_DIR / "label_encoder.joblib")

    # 2. Cargar y preparar test set
    textos, etiquetas_str = _cargar_test_set()
    logger.info("Construyendo features del test set...")
    X_all = _build_X(textos, tfidf, svd)
    y_all = label_encoder.transform(etiquetas_str)

    # Validar que cada clase tenga al menos 2 muestras para el split estratificado
    from collections import Counter
    counts_cal = Counter(y_all.tolist())
    min_count_cal = min(counts_cal.values())
    _MIN_STRAT = 2
    if min_count_cal < _MIN_STRAT:
        clases_escasas = [label_encoder.classes_[i] for i, c in counts_cal.items() if c < _MIN_STRAT]
        logger.warning(
            "Clases con pocas muestras en test set (%s). "
            "Se usará split NO estratificado para el calibrador.",
            clases_escasas,
        )
        stratify_cal = None
    else:
        stratify_cal = y_all

    # Split calibration/evaluation para evitar data leakage:
    # los calibradores se ajustan en X_cal y las métricas post-calibración
    # se miden en X_eval (datos no vistos durante el ajuste).
    # Con dataset pequeño (60 ej.) usamos 2/3 cal / 1/3 eval estratificado.
    X_cal, X_eval, y_cal, y_eval = train_test_split(
        X_all, y_all, test_size=0.33, stratify=stratify_cal, random_state=42
    )
    logger.info(
        "Split calibración/evaluación — cal: %d, eval: %d", len(y_cal), len(y_eval)
    )

    # 3. Probabilidades crudas del XGBoost (evaluadas en eval set)
    proba_raw_eval = modelo.predict_proba(X_eval)
    y_pred_raw = modelo.predict(X_eval)
    brier_antes = _brier_multiclass(y_eval, proba_raw_eval, len(label_encoder.classes_))
    f1_antes = f1_score(y_eval, y_pred_raw, average="macro")
    logger.info("ANTES calibración — Brier: %.4f | F1-macro: %.4f", brier_antes, f1_antes)

    # 4. Ajustar calibración isotónica one-vs-rest sobre el split de calibración
    logger.info("Ajustando calibración isotónica (one-vs-rest) sobre X_cal...")
    n_classes = len(label_encoder.classes_)
    proba_raw_cal = modelo.predict_proba(X_cal)
    calibrators = []
    for i in range(n_classes):
        y_bin = (y_cal == i).astype(float)
        ir = IsotonicRegression(out_of_bounds="clip")
        ir.fit(proba_raw_cal[:, i], y_bin)
        calibrators.append(ir)

    # 5. Modelo calibrado final
    calibrado = IsotonicCalibratedXGB(modelo, calibrators, modelo.classes_)

    # 6. Métricas post-calibración en el eval set (no visto durante ajuste)
    proba_cal = calibrado.predict_proba(X_eval)
    y_pred_cal = calibrado.predict(X_eval)
    brier_despues = _brier_multiclass(y_eval, proba_cal, n_classes)
    f1_despues = f1_score(y_eval, y_pred_cal, average="macro")
    logger.info("DESPUÉS calibración — Brier: %.4f | F1-macro: %.4f", brier_despues, f1_despues)

    mejora = brier_antes - brier_despues
    _UMBRAL = 0.005

    # 7. Guardar: modelo de producción si supera umbral, candidato si no
    if mejora >= _UMBRAL:
        output_path = _MODEL_DIR / "modelo_xgboost_calibrated.joblib"
    else:
        output_path = _MODEL_DIR / "modelo_xgboost_calibrated_candidate.joblib"
        logger.warning(
            "Mejora Brier (%+.4f) < umbral (%.3f). "
            "Guardado como candidato, NO como modelo de producción: %s",
            mejora, _UMBRAL, output_path.name,
        )

    joblib.dump(calibrado, output_path)
    logger.info("Modelo calibrado guardado: %s", output_path)

    # 8. Resumen
    print("\n" + "=" * 55)
    print("RESUMEN CALIBRACIÓN")
    print("=" * 55)
    print(f"  Ejemplos total       : {len(textos)} (cal={len(y_cal)}, eval={len(y_eval)})")
    print(f"  Clases               : {list(label_encoder.classes_)}")
    print(f"  Brier score ANTES    : {brier_antes:.4f}")
    print(f"  Brier score DESPUÉS  : {brier_despues:.4f}")
    print(f"  Mejora               : {mejora:+.4f}  {'✓ MEJOR' if mejora > 0 else '✗ PEOR'}")
    print(f"  F1-macro ANTES       : {f1_antes:.4f}")
    print(f"  F1-macro DESPUÉS     : {f1_despues:.4f}")
    print(f"  Modelo guardado en   : {output_path.name}")
    print("=" * 55)

    if mejora >= _UMBRAL:
        print("\nPara activar en producción:")
        print('  Edita mejor_modelo_seleccion.json:')
        print('  "model_file": "model/modelo_xgboost_calibrated.joblib"')
    else:
        print(f"\n[!] Mejora Brier ({mejora:+.4f}) < umbral ({_UMBRAL}).")
        print(f"    Guardado como candidato: {output_path.name}")
        print("    No sobreescribe el modelo de producción. Revisar manualmente.")


if __name__ == "__main__":
    calibrar()
