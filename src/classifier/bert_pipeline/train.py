"""
Fine-tuning BERT para clasificación de riesgo EU AI Act.
Modelo base: dccuchile/bert-base-spanish-wwm-cased

Prerequisito: haber ejecutado 03_preparacion_datos.ipynb
Uso: python src/classifier/bert_pipeline/train.py
"""
import os
import shutil
import sys
from pathlib import Path

# Fix conflicto OpenMP en Windows (Intel MKL vs LLVM OpenMP con torch+conda)
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"


import torch
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    DataCollatorWithPadding,
    EarlyStoppingCallback,
    Trainer,
    TrainingArguments,
)
from datasets import Dataset, DatasetDict
import joblib
import matplotlib.pyplot as plt
import mlflow
import numpy as np
from sklearn.metrics import accuracy_score, f1_score

# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PIPELINE_DIR = ROOT / "src/classifier/bert_pipeline"
MODEL_DIR = PIPELINE_DIR / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
MODEL_NAME    = "dccuchile/bert-base-spanish-wwm-cased"
EPOCHS        = 4
BATCH_SIZE    = 16
LEARNING_RATE = 2e-5
MAX_LENGTH    = 256
SEED          = 42

device = "CUDA" if torch.cuda.is_available() else "CPU"
print(f"Device : {device}")
print(f"Modelo : {MODEL_NAME}")
print(f"Epochs : {EPOCHS}, Batch: {BATCH_SIZE}, LR: {LEARNING_RATE}")

# ---------------------------------------------------------------------------
# 1. Cargar splits
# ---------------------------------------------------------------------------
print("\n[1/5] Cargando splits...")
for _fname in ["train_split.joblib", "val_split.joblib", "test_split.joblib", "label_encoder.joblib"]:
    if not (MODEL_DIR / _fname).exists():
        raise FileNotFoundError(
            f"Falta {_fname} en {MODEL_DIR}.\n"
            "Ejecuta primero: jupyter nbconvert --to notebook --execute "
            "src/classifier/bert_pipeline/notebooks/03_preparacion_datos.ipynb"
        )
df_train = joblib.load(MODEL_DIR / "train_split.joblib")
df_val   = joblib.load(MODEL_DIR / "val_split.joblib")
df_test  = joblib.load(MODEL_DIR / "test_split.joblib")
le       = joblib.load(MODEL_DIR / "label_encoder.joblib")

# LABELS derivado del LabelEncoder para garantizar que el orden de índices coincide
# con los enteros usados como etiquetas en los splits (orden alfabético de sklearn)
LABELS = le.classes_.tolist()

print(f"  Train: {len(df_train)} | Val: {len(df_val)} | Test: {len(df_test)}")
print(f"  Clases (orden LabelEncoder): {LABELS}")

# ---------------------------------------------------------------------------
# 2. Tokenización
# ---------------------------------------------------------------------------
print(f"\n[2/5] Cargando tokenizer: {MODEL_NAME}...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

def make_hf_dataset(df):
    return Dataset.from_dict({
        "text" : df["descripcion"].tolist(),
        "label": df["label"].tolist(),
    })

def tokenize_fn(batch):
    return tokenizer(batch["text"], truncation=True, max_length=MAX_LENGTH)

print("  Tokenizando splits...")
ds = DatasetDict({
    "train"     : make_hf_dataset(df_train).map(tokenize_fn, batched=True),
    "validation": make_hf_dataset(df_val).map(tokenize_fn, batched=True),
    "test"      : make_hf_dataset(df_test).map(tokenize_fn, batched=True),
})
print(f"  {ds}")

# ---------------------------------------------------------------------------
# 3. Inicializar modelo
# ---------------------------------------------------------------------------
print(f"\n[3/5] Cargando modelo: {MODEL_NAME}...")
model = AutoModelForSequenceClassification.from_pretrained(
    MODEL_NAME,
    num_labels=len(LABELS),
    id2label={i: lbl for i, lbl in enumerate(LABELS)},
    label2id={lbl: i for i, lbl in enumerate(LABELS)},
)
n_params    = sum(p.numel() for p in model.parameters())
n_trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
print(f"  Parámetros totales    : {n_params:,}")
print(f"  Parámetros entrenables: {n_trainable:,}")

# ---------------------------------------------------------------------------
# 4. Métricas
# ---------------------------------------------------------------------------
def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    return {
        "f1"      : f1_score(labels, preds, average="macro"),
        "accuracy": accuracy_score(labels, preds),
    }

# ---------------------------------------------------------------------------
# 5. Entrenamiento con MLflow
# ---------------------------------------------------------------------------
print("\n[4/5] Iniciando entrenamiento...")
mlflow_uri = os.getenv("MLFLOW_TRACKING_URI")
if mlflow_uri:
    mlflow.set_tracking_uri(mlflow_uri)
    print(f"  MLflow URI: {mlflow_uri}")
else:
    print("  MLflow tracking local (sin MLFLOW_TRACKING_URI)")

mlflow.set_experiment("bert_clasificador_riesgo_ia")

CHECKPOINTS_DIR = MODEL_DIR / "checkpoints"
# Limpiar checkpoints anteriores para evitar que trainer_state.json quede
# contaminado con runs previos (el notebook 06 lee el último checkpoint).
if CHECKPOINTS_DIR.exists():
    shutil.rmtree(CHECKPOINTS_DIR)
CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)

training_args = TrainingArguments(
    output_dir                  = str(CHECKPOINTS_DIR),
    num_train_epochs            = EPOCHS,
    per_device_train_batch_size = BATCH_SIZE,
    per_device_eval_batch_size  = BATCH_SIZE,
    learning_rate               = LEARNING_RATE,
    weight_decay                = 0.01,
    warmup_ratio                = 0.1,
    eval_strategy               = "epoch",
    save_strategy               = "epoch",
    load_best_model_at_end      = True,
    metric_for_best_model       = "f1",
    greater_is_better           = True,
    seed                        = SEED,
    report_to                   = "none",
    logging_steps               = 50,
    fp16                        = torch.cuda.is_available(),
)

trainer = Trainer(
    model            = model,
    args             = training_args,
    train_dataset    = ds["train"],
    eval_dataset     = ds["validation"],
    processing_class = tokenizer,
    data_collator    = DataCollatorWithPadding(tokenizer),
    compute_metrics  = compute_metrics,
    callbacks        = [EarlyStoppingCallback(early_stopping_patience=2)],
)

with mlflow.start_run(run_name=f"bert_{MODEL_NAME.split('/')[-1]}") as run:
    mlflow.log_params({
        "model_name"   : MODEL_NAME,
        "epochs"       : EPOCHS,
        "batch_size"   : BATCH_SIZE,
        "learning_rate": LEARNING_RATE,
        "max_length"   : MAX_LENGTH,
        "train_size"   : len(df_train),
        "val_size"     : len(df_val),
        "test_size"    : len(df_test),
    })

    trainer.train()

    # Evaluar en test
    print("\n=== Test metrics ===")
    test_metrics = trainer.evaluate(ds["test"])
    for k, v in test_metrics.items():
        if isinstance(v, float):
            print(f"  {k}: {v:.4f}")

    mlflow.log_metrics({
        k.replace("eval_", "test_"): v
        for k, v in test_metrics.items()
        if isinstance(v, float)
    })

    # Guardar modelo + tokenizer
    BERT_MODEL_PATH = MODEL_DIR / "bert_model"
    trainer.save_model(str(BERT_MODEL_PATH))
    tokenizer.save_pretrained(str(BERT_MODEL_PATH))
    mlflow.log_artifact(str(MODEL_DIR / "label_encoder.joblib"))

    print(f"\nModelo guardado en : {BERT_MODEL_PATH}")
    print(f"MLflow run ID      : {run.info.run_id}")

# ---------------------------------------------------------------------------
# 6. Curvas de entrenamiento
# ---------------------------------------------------------------------------
print("\n[5/5] Guardando curvas de entrenamiento...")
log_history = trainer.state.log_history
train_logs  = [entry for entry in log_history if "loss" in entry and "eval_loss" not in entry]
eval_logs   = [entry for entry in log_history if "eval_loss" in entry]

if eval_logs:
    epochs_eval = [entry["epoch"] for entry in eval_logs]
    f1_vals     = [entry.get("eval_f1") for entry in eval_logs]
    val_losses  = [entry["eval_loss"] for entry in eval_logs]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))

    ax1.plot(epochs_eval, val_losses, marker="o", color="steelblue", label="Val loss")
    if train_logs:
        ax1.plot(
            [entry["epoch"] for entry in train_logs],
            [entry["loss"] for entry in train_logs],
            alpha=0.4, color="orange", label="Train loss",
        )
    ax1.set_xlabel("Epoch")
    ax1.set_ylabel("Loss")
    ax1.set_title("Loss")
    ax1.legend()

    if any(f1_vals):
        ax2.plot(epochs_eval, f1_vals, marker="o", color="green")
        ax2.set_xlabel("Epoch")
        ax2.set_ylabel("F1 Macro")
        ax2.set_title("F1 Macro (validation)")

    plt.suptitle("Curvas de entrenamiento BERT")
    plt.tight_layout()
    out_path = MODEL_DIR / "training_curves.png"
    plt.savefig(out_path, dpi=120, bbox_inches="tight")
    print(f"  Curvas guardadas en: {out_path}")
else:
    print("  No hay logs de evaluación disponibles.")

print("\nEntrenamiento completado.")
