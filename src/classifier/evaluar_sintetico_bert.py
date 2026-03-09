"""
Evaluacion del clasificador BERT sobre dataset_sintetico_v2.csv.

Equivalente a evaluar_sintetico_v2.py pero usando el modelo BERT fine-tuneado
en lugar del pipeline XGBoost de produccion.

Uso:
    python src/classifier/evaluar_sintetico_bert.py
"""

import os
import sys
from pathlib import Path

# Fix conflicto OpenMP en Windows — debe ir antes de import torch
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

# torch y transformers primero para evitar conflictos de DLL
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    ConfusionMatrixDisplay,
)

# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

BERT_PATH = ROOT / "src/classifier/bert_pipeline/models/bert_model"
DATASET   = ROOT / "src/classifier/dataset_sintetico_v2.csv"

if not BERT_PATH.exists():
    raise FileNotFoundError(
        f"Modelo BERT no encontrado en {BERT_PATH}.\n"
        "Ejecuta primero: python src/classifier/bert_pipeline/train.py"
    )

# ---------------------------------------------------------------------------
# Cargar modelo BERT
# ---------------------------------------------------------------------------
print(f"Cargando modelo BERT desde: {BERT_PATH}")
tokenizer = AutoTokenizer.from_pretrained(str(BERT_PATH))
model = AutoModelForSequenceClassification.from_pretrained(str(BERT_PATH))
model.eval()

device = "cuda" if torch.cuda.is_available() else "cpu"
model.to(device)
print(f"Device: {device.upper()}")

# Mapa id -> etiqueta desde el modelo (guardado durante el entrenamiento)
id2label = model.config.id2label

# ---------------------------------------------------------------------------
# Cargar dataset
# ---------------------------------------------------------------------------
df = pd.read_csv(DATASET)
print(f"\nDataset: {DATASET.name}  |  {len(df)} filas")
print(f"Distribucion etiquetas:\n{df['etiqueta'].value_counts().to_string()}\n")

# ---------------------------------------------------------------------------
# Inferencia
# ---------------------------------------------------------------------------
print("Ejecutando inferencia BERT por cada fila...")
resultados = []

for i, row in df.iterrows():
    try:
        inputs = tokenizer(
            str(row["descripcion"]),
            truncation=True,
            max_length=256,
            return_tensors="pt",
        ).to(device)

        with torch.no_grad():
            logits = model(**inputs).logits

        proba     = torch.softmax(logits, dim=-1)[0]
        pred_id   = int(logits.argmax(-1).item())
        prediccion = id2label[pred_id]
        confianza  = float(proba[pred_id].item())

    except Exception as e:
        prediccion = "ERROR"
        confianza  = 0.0
        print(f"  Error en fila {i}: {e}")

    acierto = prediccion == row["etiqueta"]
    resultados.append({
        "id"           : row.get("id", i),
        "descripcion"  : row["descripcion"],
        "etiqueta_real": row["etiqueta"],
        "prediccion"   : prediccion,
        "confianza"    : round(confianza, 3),
        "acierto"      : acierto,
    })

    if (i + 1) % 50 == 0:
        print(f"  Procesadas {i + 1}/{len(df)} filas...")

df_res = pd.DataFrame(resultados)

# ---------------------------------------------------------------------------
# Métricas
# ---------------------------------------------------------------------------
validas  = df_res[df_res["prediccion"] != "ERROR"]
y_true   = validas["etiqueta_real"]
y_pred   = validas["prediccion"]
clases   = sorted(y_true.unique())
accuracy = validas["acierto"].sum() / len(validas)

print(f"\n{'='*60}")
print(f"RESULTADOS BERT — dataset_sintetico_v2.csv  ({len(validas)} muestras)")
print(f"{'='*60}")
print(f"Accuracy : {accuracy:.4f}  ({validas['acierto'].sum()}/{len(validas)} correctas)")
print()
print("--- Classification Report ---")
print(classification_report(y_true, y_pred, labels=clases, zero_division=0))

print("--- Aciertos por clase ---")
for clase in clases:
    sub  = validas[validas["etiqueta_real"] == clase]
    n_ok = sub["acierto"].sum()
    print(f"  {clase:<25} {n_ok:>3}/{len(sub):>3}  ({n_ok/len(sub)*100:.0f}%)")

# ---------------------------------------------------------------------------
# Errores
# ---------------------------------------------------------------------------
errores = validas[~validas["acierto"]]
if len(errores) > 0:
    print(f"\n--- Confusiones mas frecuentes ({len(errores)} errores) ---")
    pairs = errores.groupby(["etiqueta_real", "prediccion"]).size().sort_values(ascending=False)
    for (real, pred), count in pairs.items():
        print(f"  {real:<25} -> {pred:<25}  {count} casos")

    print("\n--- Muestra de errores (primeros 8) ---")
    for _, row in errores.head(8).iterrows():
        print(f"  [{row['etiqueta_real']} -> {row['prediccion']} {row['confianza']:.0%}]")
        print(f"    {str(row['descripcion'])[:90]}")

# ---------------------------------------------------------------------------
# Guardar CSV
# ---------------------------------------------------------------------------
out_csv = DATASET.parent / "resultados_sintetico_bert.csv"
df_res.to_csv(out_csv, index=False, encoding="utf-8")
print(f"\nResultados guardados en: {out_csv.name}")

# ---------------------------------------------------------------------------
# Matriz de confusión
# ---------------------------------------------------------------------------
try:
    cm  = confusion_matrix(y_true, y_pred, labels=clases)
    fig, ax = plt.subplots(figsize=(7, 6))
    ConfusionMatrixDisplay(cm, display_labels=clases).plot(ax=ax, colorbar=True, cmap="Blues")
    ax.set_title("Matriz de confusion BERT — dataset_sintetico_v2", fontsize=11)
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
    out_png = DATASET.parent / "matriz_confusion_sintetico_bert.png"
    plt.savefig(out_png, dpi=150)
    print(f"Matriz de confusion guardada en: {out_png.name}")
except Exception as e:
    print(f"No se pudo generar la matriz de confusion: {e}")

print("\nEvaluacion completada.")
