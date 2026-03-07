"""Fine-tuning de BERT para clasificación de riesgo EU AI Act (4 clases).

Modelo base: dccuchile/bert-base-spanish-wwm-cased
Dataset:
  1. bert_pipeline/data/dataset_augmented.jsonl  (generado por run_augmentation.py)
  2. Fallback al CSV original si el JSONL no existe.

Tracking: MLflow (MLFLOW_TRACKING_URI).

Uso:
    python -m src.classifier.bert_pipeline.bert.train
    python -m src.classifier.bert_pipeline.bert.train --epochs 4 --batch-size 16
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import joblib
import mlflow
import numpy as np
import pandas as pd
from datasets import Dataset, DatasetDict
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.utils.class_weight import compute_class_weight
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    DataCollatorWithPadding,
    Trainer,
    TrainingArguments,
)
from sklearn.metrics import f1_score, accuracy_score

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_HERE = Path(__file__).parent
_PIPELINE_DIR = _HERE.parent

DATA_JSONL = _PIPELINE_DIR / "data" / "dataset_augmented.jsonl"
DATA_CSV_FALLBACK = (
    _PIPELINE_DIR.parent
    / "classifier_dataset_fusionado"
    / "datasets"
    / "eu_ai_act_flagged_es_limpio.csv"
)
MODEL_DIR = _PIPELINE_DIR / "models"

MODEL_NAME = "dccuchile/bert-base-spanish-wwm-cased"
MLFLOW_EXPERIMENT = "bert_clasificador_riesgo_ia"
LABELS = ["inaceptable", "alto_riesgo", "riesgo_limitado", "riesgo_minimo"]
SEED = 42


def _load_data() -> pd.DataFrame:
    if DATA_JSONL.exists():
        logger.info("Cargando dataset aumentado desde %s", DATA_JSONL)
        records = [
            json.loads(line)
            for line in DATA_JSONL.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        df = pd.DataFrame(records).rename(columns={"etiqueta": "etiqueta_normalizada"})
    else:
        logger.warning(
            "JSONL no encontrado — usando CSV original como fallback: %s", DATA_CSV_FALLBACK
        )
        df = pd.read_csv(DATA_CSV_FALLBACK)[["descripcion", "etiqueta_normalizada"]].dropna()

    df = df[df["etiqueta_normalizada"].isin(LABELS)].reset_index(drop=True)
    logger.info(
        "Dataset cargado: %d ejemplos\nDistribución:\n%s",
        len(df),
        df["etiqueta_normalizada"].value_counts().to_string(),
    )
    return df


def _compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    return {
        "f1": f1_score(labels, preds, average="macro"),
        "accuracy": accuracy_score(labels, preds),
    }


def train(
    model_name: str = MODEL_NAME,
    epochs: int = 4,
    batch_size: int = 16,
    learning_rate: float = 2e-5,
) -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    df = _load_data()

    le = LabelEncoder()
    le.fit(LABELS)
    df["label"] = le.transform(df["etiqueta_normalizada"])

    # Split estratificado: 80% train, 10% val, 10% test
    df_train, df_temp = train_test_split(
        df, test_size=0.2, stratify=df["label"], random_state=SEED
    )
    df_val, df_test = train_test_split(
        df_temp, test_size=0.5, stratify=df_temp["label"], random_state=SEED
    )
    logger.info(
        "Split — train: %d, val: %d, test: %d", len(df_train), len(df_val), len(df_test)
    )

    tokenizer = AutoTokenizer.from_pretrained(model_name)

    def _make_dataset(df_split: pd.DataFrame) -> Dataset:
        return Dataset.from_dict(
            {
                "text": df_split["descripcion"].tolist(),
                "label": df_split["label"].tolist(),
            }
        )

    def _tokenize(batch):
        return tokenizer(batch["text"], truncation=True, max_length=512)

    ds = DatasetDict(
        {
            "train": _make_dataset(df_train).map(_tokenize, batched=True),
            "validation": _make_dataset(df_val).map(_tokenize, batched=True),
            "test": _make_dataset(df_test).map(_tokenize, batched=True),
        }
    )

    model = AutoModelForSequenceClassification.from_pretrained(
        model_name,
        num_labels=len(LABELS),
        id2label={i: lbl for i, lbl in enumerate(LABELS)},
        label2id={lbl: i for i, lbl in enumerate(LABELS)},
    )

    # Pesos de clase para manejar el desbalanceo
    class_weights = compute_class_weight(
        "balanced", classes=np.arange(len(LABELS)), y=df_train["label"].values
    )
    logger.info("Class weights: %s", dict(zip(LABELS, class_weights.round(3))))

    # MLflow
    mlflow_uri = os.getenv("MLFLOW_TRACKING_URI")
    if mlflow_uri:
        mlflow.set_tracking_uri(mlflow_uri)
    mlflow.set_experiment(MLFLOW_EXPERIMENT)

    with mlflow.start_run(run_name=f"bert_{model_name.split('/')[-1]}"):
        mlflow.log_params(
            {
                "model_name": model_name,
                "epochs": epochs,
                "batch_size": batch_size,
                "learning_rate": learning_rate,
                "train_size": len(df_train),
                "val_size": len(df_val),
                "test_size": len(df_test),
                "dataset_source": "augmented" if DATA_JSONL.exists() else "original_csv",
            }
        )

        training_args = TrainingArguments(
            output_dir=str(MODEL_DIR / "checkpoints"),
            num_train_epochs=epochs,
            per_device_train_batch_size=batch_size,
            per_device_eval_batch_size=batch_size,
            learning_rate=learning_rate,
            weight_decay=0.01,
            eval_strategy="epoch",
            save_strategy="epoch",
            load_best_model_at_end=True,
            metric_for_best_model="f1",
            seed=SEED,
            report_to="none",
            logging_steps=50,
        )

        trainer = Trainer(
            model=model,
            args=training_args,
            train_dataset=ds["train"],
            eval_dataset=ds["validation"],
            tokenizer=tokenizer,
            data_collator=DataCollatorWithPadding(tokenizer),
            compute_metrics=_compute_metrics,
        )

        trainer.train()

        # Evaluación final en test
        test_metrics = trainer.evaluate(ds["test"])
        logger.info("Test metrics: %s", test_metrics)
        mlflow.log_metrics(
            {k.replace("eval_", "test_"): v for k, v in test_metrics.items() if isinstance(v, float)}
        )

        # Guardar modelo, tokenizer y artefactos de inferencia
        bert_model_path = MODEL_DIR / "bert_model"
        trainer.save_model(str(bert_model_path))
        tokenizer.save_pretrained(str(bert_model_path))
        joblib.dump(le, MODEL_DIR / "label_encoder.joblib")
        # Guardar test split para evaluate.py
        joblib.dump(
            df_test[["descripcion", "etiqueta_normalizada", "label"]].reset_index(drop=True),
            MODEL_DIR / "test_split.joblib",
        )

        mlflow.log_artifact(str(MODEL_DIR / "label_encoder.joblib"))
        logger.info("Modelo guardado en %s", bert_model_path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Fine-tuning BERT clasificador EU AI Act")
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--model", default=MODEL_NAME)
    args = parser.parse_args()

    train(
        model_name=args.model,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
    )
