"""eval_ensemble.py — Benchmark formal del ensemble XGBoost + BERT.

Evalúa predict_ensemble() sobre el test set del dataset fusionado y guarda
las métricas en ensemble_metrics.json para comparar con los modelos individuales.

Baseline a superar:
    XGBoost calibrado: F1-macro 0.8780, Brier 0.0305

Uso
---
    python -m src.classifier.eval_ensemble
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

_TEST_JSONL = Path(__file__).parent / "classifier_dataset_fusionado/data/finetune/test.jsonl"
_METRICS_OUT = Path(__file__).parent / "classifier_dataset_fusionado/model/ensemble_metrics.json"

# Regex para extraer la descripción del campo text del jsonl
_DESC_RE = re.compile(r"### Descripción:\n(.*?)\n\n### Clasificación:", re.DOTALL)


def _extraer_descripcion(text: str) -> str:
    """Extrae la descripción del sistema de IA del campo text del jsonl."""
    match = _DESC_RE.search(text)
    if not match:
        raise ValueError(f"Formato inesperado en text: {text[:80]!r}")
    return match.group(1).strip()


def evaluar() -> dict:
    """Corre el ensemble sobre el test set y devuelve las métricas."""
    import joblib
    import numpy as np
    from sklearn.metrics import f1_score, brier_score_loss
    from src.classifier.ensemble import predict_ensemble

    logger.info("Cargando test set: %s", _TEST_JSONL)
    ejemplos = [json.loads(l) for l in _TEST_JSONL.read_text().splitlines() if l.strip()]
    logger.info("Ejemplos en test set: %d", len(ejemplos))

    _le_path = Path(__file__).parent / "classifier_dataset_fusionado/model/label_encoder.joblib"
    le = joblib.load(_le_path)
    clases = le.classes_.tolist()

    y_true, y_pred, y_proba = [], [], []
    errores = 0

    for i, ej in enumerate(ejemplos):
        try:
            descripcion = _extraer_descripcion(ej["text"])
            etiqueta_real = ej["etiqueta"]
            resultado = predict_ensemble(descripcion)

            y_true.append(etiqueta_real)
            y_pred.append(resultado["risk_level"])

            # Probabilidades ordenadas por clases del label encoder
            proba = [resultado["probabilities"].get(c, 0.0) for c in clases]
            y_proba.append(proba)

            modo = resultado.get("ensemble_mode", "?")
            logger.debug("[%d/%d] real=%-20s pred=%-20s modo=%s", i + 1, len(ejemplos), etiqueta_real, resultado["risk_level"], modo)

        except Exception as exc:
            logger.warning("Error en ejemplo %d: %s", i, exc)
            errores += 1

    if not y_true:
        raise RuntimeError("No se pudo evaluar ningún ejemplo.")

    f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)
    accuracy = sum(t == p for t, p in zip(y_true, y_pred)) / len(y_true)

    # Brier score multiclase — promedio de brier por clase
    y_proba_arr = np.array(y_proba)
    brier_scores = []
    for j, clase in enumerate(clases):
        y_bin = [1 if t == clase else 0 for t in y_true]
        brier_scores.append(brier_score_loss(y_bin, y_proba_arr[:, j]))
    brier = float(np.mean(brier_scores))

    # Distribución de modos del ensemble
    resultados_modo = {}
    for ej in ejemplos:
        try:
            desc = _extraer_descripcion(ej["text"])
            r = predict_ensemble(desc)
            modo = r.get("ensemble_mode", "?")
            resultados_modo[modo] = resultados_modo.get(modo, 0) + 1
        except Exception:
            pass

    metricas = {
        "modelo": "ensemble_xgboost_bert",
        "test_f1_macro": round(f1, 4),
        "test_accuracy": round(accuracy, 4),
        "test_brier_score": round(brier, 4),
        "n_ejemplos": len(y_true),
        "n_errores": errores,
        "distribucion_modos": resultados_modo,
        "baseline_xgboost_calibrado": {
            "test_f1_macro": 0.8780,
            "test_brier_score": 0.0305,
        },
        "mejora_f1": round(f1 - 0.8780, 4),
        "mejora_brier": round(0.0305 - brier, 4),
    }

    _METRICS_OUT.write_text(json.dumps(metricas, indent=2, ensure_ascii=False))
    logger.info("Métricas guardadas en: %s", _METRICS_OUT)

    return metricas


if __name__ == "__main__":
    metricas = evaluar()

    print("\n" + "=" * 55)
    print("  BENCHMARK ENSEMBLE XGBoost + BERT")
    print("=" * 55)
    print(f"  F1-macro        : {metricas['test_f1_macro']:.4f}  (baseline: 0.8780  mejora: {metricas['mejora_f1']:+.4f})")
    print(f"  Accuracy        : {metricas['test_accuracy']:.4f}")
    print(f"  Brier score     : {metricas['test_brier_score']:.4f}  (baseline: 0.0305  mejora: {metricas['mejora_brier']:+.4f})")
    print(f"  Ejemplos test   : {metricas['n_ejemplos']}")
    print(f"  Modos ensemble  : {metricas['distribucion_modos']}")
    print("=" * 55)

    f1 = metricas["test_f1_macro"]
    if metricas["mejora_f1"] >= 0.005:
        print(f"\n✓ El ensemble SUPERA el baseline en F1 ({f1:.4f} > 0.8780).")
        print("  Considera actualizar mejor_modelo_seleccion.json.")
    elif metricas["mejora_f1"] >= 0:
        print(f"\n~ El ensemble es SIMILAR al baseline en F1 ({f1:.4f} ≈ 0.8780).")
        print("  No justifica el cambio — mantener XGBoost calibrado como producción.")
    else:
        print(f"\n✗ El ensemble es PEOR que el baseline en F1 ({f1:.4f} < 0.8780).")
        print("  Mantener XGBoost calibrado como producción.")
