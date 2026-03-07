"""Evaluación del modelo BERT fine-tuneado.

Carga el test split guardado por train.py y genera:
- Classification report completo (precision / recall / F1 por clase)
- F1 macro
- Matriz de confusión guardada en models/confusion_matrix_bert.png

Requiere haber ejecutado train.py primero.

Uso:
    python -m src.classifier.bert_pipeline.bert.evaluate
"""

from __future__ import annotations

import logging
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
import torch
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from transformers import AutoModelForSequenceClassification, AutoTokenizer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_HERE = Path(__file__).parent
_PIPELINE_DIR = _HERE.parent

MODEL_PATH = _PIPELINE_DIR / "models" / "bert_model"
LE_PATH = _PIPELINE_DIR / "models" / "label_encoder.joblib"
TEST_PATH = _PIPELINE_DIR / "models" / "test_split.joblib"
MATRIX_PATH = _PIPELINE_DIR / "models" / "confusion_matrix_bert.png"


def evaluate() -> dict:
    """Evalúa el modelo BERT en el test split y devuelve métricas.

    Returns
    -------
    dict con claves: f1_macro, classification_report (str)
    """
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Modelo no encontrado en {MODEL_PATH}. Ejecuta train.py primero:\n"
            "  python -m src.classifier.bert_pipeline.bert.train"
        )

    le = joblib.load(LE_PATH)
    df_test = joblib.load(TEST_PATH)

    tokenizer = AutoTokenizer.from_pretrained(str(MODEL_PATH))
    model = AutoModelForSequenceClassification.from_pretrained(str(MODEL_PATH))
    model.eval()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    logger.info("Evaluando en %s (%d ejemplos de test)", device, len(df_test))

    y_true = df_test["label"].tolist()
    y_pred = []

    for text in df_test["descripcion"].tolist():
        inputs = tokenizer(
            text, truncation=True, max_length=512, return_tensors="pt"
        ).to(device)
        with torch.no_grad():
            logits = model(**inputs).logits
        y_pred.append(int(logits.argmax(-1).item()))

    target_names = le.classes_.tolist()
    report = classification_report(y_true, y_pred, target_names=target_names)
    f1_macro = f1_score(y_true, y_pred, average="macro")

    print("\n=== Resultados BERT (test set) ===")
    print(report)
    print(f"F1 Macro: {f1_macro:.4f}")

    # Matriz de confusión
    cm = confusion_matrix(y_true, y_pred)
    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(cm, interpolation="nearest", cmap=plt.cm.Blues)
    plt.colorbar(im, ax=ax)
    ax.set(
        xticks=np.arange(len(target_names)),
        yticks=np.arange(len(target_names)),
        xticklabels=target_names,
        yticklabels=target_names,
        xlabel="Predicho",
        ylabel="Real",
        title="Matriz de Confusión — BERT",
    )
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
    for i in range(len(target_names)):
        for j in range(len(target_names)):
            ax.text(
                j, i, str(cm[i, j]),
                ha="center", va="center",
                color="white" if cm[i, j] > cm.max() / 2 else "black",
            )
    fig.tight_layout()
    fig.savefig(str(MATRIX_PATH), dpi=150)
    plt.close(fig)
    logger.info("Matriz de confusión guardada en %s", MATRIX_PATH)

    return {"f1_macro": f1_macro, "classification_report": report}


if __name__ == "__main__":
    evaluate()
