# Tareas Día 2 — Mejora del modelo clasificador

## Estado de partida
- **Baseline**: LogisticRegression + TF-IDF (bigramas, 3811 términos)
- **F1-macro validación**: 0.87
- **Dataset**: 300 muestras (train 210 / val 45 / test 45), 4 clases
- **Artefactos guardados**: modelo + vectorizador en `model/`

## Notebooks actuales (Día 1 — baseline)
| Notebook | Contenido | Estado |
|---|---|---|
| `1_analisis_exploratorio.ipynb` | EDA del dataset | Terminado |
| `2_preprocesado y división.ipynb` | NER + lematización + split train/val/test | Terminado |
| `3_entrenamiento.ipynb` | TF-IDF + LogReg baseline | Terminado |
| `4_metricas.ipynb` | Métricas test + MLflow (solo métricas de test) | Terminado |

## Notebooks nuevos (Día 2 — modelo mejorado)
| Notebook | Contenido |
|---|---|
| `5_entrenamiento_v2.ipynb` | Features manuales + TF-IDF + re-entrenamiento + MLflow Exp 1 |
| `6_metricas_v2.ipynb` | Métricas test del modelo mejorado + comparativa con baseline + MLflow |

> **¿Por qué notebooks nuevos?** Para mantener el baseline (notebooks 3-4) como referencia
> y poder comparar la evolución entre experimentos sin perder trazabilidad.

---

## Roadmap

### 1. Crear funciones de features manuales → `functions.py`
- Implementar función `crear_features_manuales(X_texts)` que devuelva un DataFrame/matriz con:
  - Longitud del texto (n.º de palabras)
  - Longitud del texto (n.º de caracteres)
  - Conteo de entidades NER por tipo (PER, LOC, ORG, MISC)
  - Presencia de palabras clave del dominio (ej. "vigilancia", "biométrico", "chatbot", "scoring")
- Implementar función `combinar_features(X_tfidf, X_manual)` que concatene TF-IDF + features manuales con `scipy.sparse.hstack`

### 2. Entrenar modelo mejorado → `5_entrenamiento_v2.ipynb`
- Cargar train, validation y test desde `data/processed/`
- Vectorizar con TF-IDF (misma config que baseline para comparar)
- Generar features manuales con `crear_features_manuales()`
- Concatenar TF-IDF + features manuales con `combinar_features()`
- Entrenar LogisticRegression sobre las features combinadas
- Evaluar en validación y comparar con baseline (0.87 F1-macro)
- Guardar artefactos actualizados en `model/` (modelo, vectorizador, feature config)
- **Registrar Experimento 1 en MLflow** dentro del mismo notebook:
  - Parámetros: config TF-IDF, lista de features manuales, hiperparámetros del modelo
  - Métricas: accuracy y f1_macro en validación
  - Artefactos: modelo, vectorizador

### 3. Evaluar y comparar → `6_metricas_v2.ipynb`
- Cargar modelo mejorado y vectorizador desde `model/`
- Evaluar sobre test: classification report, F1-macro, matriz de confusión
- Curva ROC multiclase (con `predict_proba`)
- **Comparativa con baseline**: tabla resumen baseline vs modelo mejorado (F1-macro, accuracy, ROC AUC)
- Análisis de errores: revisar ejemplos mal clasificados, buscar patrones de mejora/empeoramiento respecto al baseline
- **Registrar métricas finales en MLflow**:
  - Métricas de test
  - Matriz de confusión y curva ROC como artefactos

---

## Orden de ejecución
1. `functions.py` — Crear `crear_features_manuales()` y `combinar_features()`
2. `5_entrenamiento_v2.ipynb` — Features manuales + TF-IDF + entrenar + evaluar validación + guardar artefactos + MLflow Exp 1
3. `6_metricas_v2.ipynb` — Métricas test + comparativa con baseline + análisis de errores + MLflow métricas finales
