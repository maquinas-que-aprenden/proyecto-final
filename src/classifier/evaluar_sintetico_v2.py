"""
Evaluacion del clasificador de riesgo sobre dataset_sintetico_v2.csv.

Llama a predict_risk() (el pipeline de produccion, incluyendo override Anexo III)
por cada fila y comprueba si la prediccion coincide con la etiqueta.

Uso:
    python src/classifier/evaluar_sintetico_v2.py
"""

import sys
import os
from pathlib import Path
import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix, ConfusionMatrixDisplay
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# --- Importar predict_risk ---------------------------------------------------
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

# Silenciar Langfuse/MLflow que no son necesarios aqui
# Asignación directa para sobreescribir cualquier valor previo (setdefault no lo haría)
os.environ["LANGFUSE_PUBLIC_KEY"] = ""
os.environ["LANGFUSE_SECRET_KEY"] = ""

from src.classifier.main import predict_risk  # noqa: E402

# --- Cargar dataset ----------------------------------------------------------
DATASET = Path(__file__).parent / "dataset_sintetico_v2.csv"
df = pd.read_csv(DATASET)
print(f"Dataset: {DATASET.name}  |  {len(df)} filas")
print(f"Distribucion etiquetas:\n{df['etiqueta'].value_counts().to_string()}\n")

# --- Inferencia fila a fila --------------------------------------------------
print("Ejecutando predict_risk() por cada fila...")
resultados = []
for i, row in df.iterrows():
    try:
        res = predict_risk(str(row["descripcion"]))
        prediccion = res["risk_level"]
        confianza = res["confidence"]
        override = res.get("annex3_override", False)
    except Exception as e:
        prediccion = "ERROR"
        confianza = 0.0
        override = False
        print(f"  Error en fila {i}: {e}")

    acierto = prediccion == row["etiqueta"]
    resultados.append({
        "id": row.get("id", i),
        "descripcion": row["descripcion"],
        "etiqueta_real": row["etiqueta"],
        "prediccion": prediccion,
        "confianza": round(confianza, 3),
        "acierto": acierto,
        "override_anexo3": override,
    })

    if (i + 1) % 50 == 0:
        print(f"  Procesadas {i + 1}/{len(df)} filas...")

df_res = pd.DataFrame(resultados)

# --- Metricas ----------------------------------------------------------------
n_errors = (df_res["prediccion"] == "ERROR").sum()
validas = df_res[df_res["prediccion"] != "ERROR"]
y_true = validas["etiqueta_real"]
y_pred = validas["prediccion"]
clases = sorted(y_true.unique())

# Denominador incluye filas con error (cuentan como incorrectas)
n_total = len(df_res)
n_ok = validas["acierto"].sum()
accuracy = n_ok / n_total
overrides = validas["override_anexo3"].sum()

print(f"\n{'='*60}")
print(f"RESULTADOS — dataset_sintetico_v2.csv  ({n_total} muestras)")
if n_errors:
    print(f"  ⚠ Filas con error de pipeline: {n_errors} (cuentan como incorrectas)")
print(f"{'='*60}")
print(f"Accuracy          : {accuracy:.4f}  ({n_ok}/{n_total} correctas)")
print(f"Overrides Anexo III: {overrides} predicciones modificadas por reglas deterministas")
print()
print("--- Classification Report ---")
print(classification_report(y_true, y_pred, labels=clases, zero_division=0))

# --- Tabla de errores por clase ----------------------------------------------
print("--- Aciertos por clase ---")
for clase in clases:
    sub = validas[validas["etiqueta_real"] == clase]
    n_ok = sub["acierto"].sum()
    if len(sub) == 0:
        print(f"  {clase:<20}   0/  0  (N/A)")
    else:
        print(f"  {clase:<20} {n_ok:>3}/{len(sub):>3}  ({n_ok/len(sub)*100:.0f}%)")

# --- Confusiones frecuentes --------------------------------------------------
errores = validas[~validas["acierto"]]
if len(errores) > 0:
    print(f"\n--- Confusiones mas frecuentes ({len(errores)} errores) ---")
    pairs = errores.groupby(["etiqueta_real", "prediccion"]).size().sort_values(ascending=False)
    for (real, pred), count in pairs.items():
        print(f"  {real:<20} -> {pred:<20}  {count} casos")

    print("\n--- Muestra de errores (primeros 8) ---")
    for _, row in errores.head(8).iterrows():
        override_tag = " [ANEXO III]" if row["override_anexo3"] else ""
        print(f"  [{row['etiqueta_real']} -> {row['prediccion']} {row['confianza']:.0%}{override_tag}]")
        print(f"    {str(row['descripcion'])[:90]}")

# --- Guardar resultados en CSV -----------------------------------------------
out_csv = DATASET.parent / "resultados_sintetico_v2.csv"
df_res.to_csv(out_csv, index=False, encoding="utf-8")
print(f"\nResultados guardados en: {out_csv.name}")

# --- Matriz de confusion -----------------------------------------------------
try:
    cm = confusion_matrix(y_true, y_pred, labels=clases)
    fig, ax = plt.subplots(figsize=(7, 6))
    ConfusionMatrixDisplay(cm, display_labels=clases).plot(ax=ax, colorbar=True, cmap="Blues")
    ax.set_title("Matriz de confusion — dataset_sintetico_v2", fontsize=11)
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
    out_png = DATASET.parent / "matriz_confusion_sintetico_v2.png"
    plt.savefig(out_png, dpi=150)
    print(f"Matriz de confusion guardada en: {out_png.name}")
except Exception as e:
    print(f"No se pudo generar la matriz de confusion: {e}")

print("\nEvaluacion completada.")
