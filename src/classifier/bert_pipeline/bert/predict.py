"""Inferencia BERT — misma interfaz que src.classifier.main.predict_risk().

predict(text) → {risk_level, confidence, probabilities}

Carga el modelo con lazy initialization (singleton thread-safe).
El modelo se descarga en el primer uso; las llamadas siguientes reutilizan
los artefactos ya en memoria.

Uso:
    from src.classifier.bert_pipeline.bert.predict import predict
    result = predict("Sistema de reconocimiento facial en tiempo real")

    # O desde línea de comandos:
    python -m src.classifier.bert_pipeline.bert.predict --query "..."
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

import joblib
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

logger = logging.getLogger(__name__)

_HERE = Path(__file__).parent
_PIPELINE_DIR = _HERE.parent

MODEL_PATH = _PIPELINE_DIR / "models" / "bert_model"
LE_PATH = _PIPELINE_DIR / "models" / "label_encoder.joblib"

_tokenizer = None
_model = None
_le = None
_device: str = "cpu"
_lock = threading.Lock()


def _load() -> None:
    global _tokenizer, _model, _le, _device
    if _model is not None:
        return
    with _lock:
        if _model is not None:
            return
        if not MODEL_PATH.exists():
            raise FileNotFoundError(
                f"Modelo BERT no encontrado en {MODEL_PATH}.\n"
                "Ejecuta primero:\n"
                "  python -m src.classifier.bert_pipeline.bert.train"
            )
        if not LE_PATH.exists():
            raise FileNotFoundError(
                f"Label encoder no encontrado en {LE_PATH}.\n"
                "Ejecuta primero: python -m src.classifier.bert_pipeline.bert.train"
            )
        _tokenizer = AutoTokenizer.from_pretrained(str(MODEL_PATH))
        _model = AutoModelForSequenceClassification.from_pretrained(str(MODEL_PATH))
        _model.eval()
        _device = "cuda" if torch.cuda.is_available() else "cpu"
        _model.to(_device)
        _le = joblib.load(LE_PATH)
        logger.info("Modelo BERT cargado desde %s (device=%s)", MODEL_PATH, _device)


def predict(text: str) -> dict:
    """Clasifica el texto y devuelve nivel de riesgo con confianza.

    Parameters
    ----------
    text : str
        Descripción del sistema de IA en lenguaje natural.

    Returns
    -------
    dict
        risk_level    : str   — nivel de riesgo EU AI Act
        confidence    : float — probabilidad de la clase predicha (0-1)
        probabilities : dict  — probabilidades para las 4 clases
    """
    _load()

    inputs = _tokenizer(
        text, truncation=True, max_length=256, return_tensors="pt"
    ).to(_device)

    with torch.no_grad():
        logits = _model(**inputs).logits

    proba = torch.softmax(logits, dim=-1)[0].tolist()
    pred_idx = int(logits.argmax(-1).item())
    labels: list[str] = _le.classes_.tolist()

    return {
        "risk_level": labels[pred_idx],
        "confidence": round(proba[pred_idx], 4),
        "probabilities": {label: round(p, 4) for label, p in zip(labels, proba)},
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Inferencia clasificador BERT EU AI Act")
    parser.add_argument("--query", required=True, help="Descripción del sistema de IA")
    args = parser.parse_args()

    result = predict(args.query)
    print(f"Nivel de riesgo : {result['risk_level']}")
    print(f"Confianza       : {result['confidence']:.0%}")
    print("Probabilidades  :")
    for label, prob in sorted(result["probabilities"].items(), key=lambda x: -x[1]):
        print(f"  {label:<20} {prob:.1%}")
