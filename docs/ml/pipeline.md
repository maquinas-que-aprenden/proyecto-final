# Pipeline ML — Clasificador de riesgo IA

## API de inferencia — `predict_risk()`

El clasificador se expone como servicio en `src/classifier/main.py`. Es la función que el orquestador ReAct invoca como tool.

```python
from src.classifier.main import predict_risk

resultado = predict_risk("Sistema de reconocimiento facial en aeropuertos")
# {
#   "risk_level": "alto_riesgo",
#   "confidence": 0.87,
#   "probabilities": {
#       "alto_riesgo": 0.87,
#       "inaceptable": 0.08,
#       "riesgo_limitado": 0.03,
#       "riesgo_minimo": 0.02
#   },
#   "shap_top_features": [
#       {"feature": "reconocimiento facial", "contribution": 0.42},
#       {"feature": "biométrico", "contribution": 0.31},
#       ...
#   ],
#   "shap_explanation": "Factores principales para 'alto_riesgo': reconocimiento facial, biométrico, aeropuerto."
# }
```

**Características del servicio:**
- Lazy loading thread-safe con double-check locking — el modelo se carga en el primer uso y se reutiliza
- Validación de input con Pydantic (`min_length=1`, `max_length=5000`)
- Fallback NLP: usa spaCy si está disponible, si no aplica regex
- Explicabilidad integrada: contribuciones lineales (`coef_ * feature_value`), top-5 features por clase predicha

**Modelo en producción:** LogisticRegression + TF-IDF (dataset artificial, F1-macro 0.9053). Ver [metricas.md](metricas.md) para la justificación de esta elección.

---

## Tres datasets, tres pipelines paralelos

El módulo `src/classifier/` contiene tres experimentos independientes para comparar el impacto del origen de los datos:

| Dataset | Carpeta | Muestras | Mejor modelo | F1-macro test |
|---------|---------|----------|--------------|:-------------:|
| **Artificial** (elaboración propia) | `classifier_dataset_artificial/` | 300 | LogReg + TF-IDF | **0.9053** |
| Real (EU AI Act oficial) | `classifier_dataset_real/` | ~90 | LogReg + TF-IDF + OHE | 0.8583 |
| Fusionado (artificial + real) | `classifier_dataset_fusionado/` | ~390 | XGBoost + SVD | 0.8822 |

El dataset artificial se usa en producción por tener las mejores métricas y por ser el más adecuado para inferencia libre (sin columnas estructuradas). Ver [metricas.md](metricas.md) para el análisis completo.

---

## Visión general

El clasificador asigna a un sistema de IA uno de los cuatro niveles de riesgo definidos por el EU AI Act:

| Nivel | Descripción |
|-------|-------------|
| `inaceptable` | Sistemas prohibidos: scoring social, manipulación subliminal, identificación biométrica en tiempo real |
| `alto_riesgo` | Sistemas de infraestructura crítica, educación, empleo, servicios esenciales, justicia |
| `riesgo_limitado` | Chatbots, sistemas generativos con obligación de transparencia |
| `riesgo_minimo` | Filtros de spam, IA en videojuegos, recomendadores sin impacto en derechos fundamentales |

Flujo de datos:

```
Texto crudo (descripción del sistema)
    ↓
1. Limpieza y lematización (limpiar_texto_preprocess)
    ↓
2. Vectorización TF-IDF (crear_tfidf)
    ↓
3. Entrenamiento / predicción (modelo baseline)
    ↓
4. Evaluación (evaluar_modelo)
    ↓
5. Explicabilidad SHAP (explicar_con_shap)
    ↓
6. Serialización (guardar_pipeline_completo)
    ↓
7. Registro MLflow (registrar_modelo_en_registry)
```

---

## Paso 1 — Preprocesado (`functions.limpiar_texto_preprocess`)

Se aplica sobre la columna `descripcion` del dataset:

1. Minúsculas y eliminación de puntuación
2. Eliminación de stopwords (`es_core_news_lg`)
3. **Lematización** con spaCy — reduce variantes morfológicas ("corriendo" → "correr")

La lematización es especialmente importante en datasets pequeños (≤ 500 muestras) porque reduce el vocabulario efectivo y mejora la generalización.

Resultado: columna `text_final` con texto normalizado.

---

## Paso 2 — Vectorización TF-IDF (`functions.crear_tfidf`)

```python
TfidfVectorizer(
    max_features=5000,
    ngram_range=(1, 2),   # unigramas + bigramas
    sublinear_tf=True,    # log(1 + tf), suaviza frecuencias altas
)
```

El vectorizador se ajusta **solo sobre train** y se transforma en val/test para evitar data leakage.

Resultado: matriz sparse `(n_muestras, N términos)` — N depende del dataset (ej. 3811 para `classifier_dataset_artificial`).

---

## Paso 3 — Features manuales opcionales (`functions.crear_features_manuales`)

Complementan el TF-IDF con señales del dominio:

| Feature | Descripción |
|---------|-------------|
| `num_palabras` | Longitud en palabras del texto |
| `num_caracteres` | Longitud en caracteres |
| `ner_PER` | Conteo de entidades de tipo persona |
| `ner_ORG` | Conteo de entidades de tipo organización |
| `ner_LOC` | Conteo de entidades de tipo lugar |
| `kw_inaceptable` | Presencia de palabras clave de clase prohibida (biométrico, vigilancia, scoring social...) |

Las matrices TF-IDF y features manuales se concatenan con `scipy.sparse.hstack` mediante `combinar_features()`.

> En los experimentos, añadir features manuales **empeoró** el rendimiento (F1-macro bajó de 0.9530 a 0.7330). Se mantiene en el código como opción experimental.

---

## Paso 4 — División del dataset (`functions.split_dataset`)

| Split | Proporción | Muestras (300 total) |
|-------|-----------|----------------------|
| Train | 70 % | 210 |
| Validation | 15 % | 45 |
| Test | 15 % | 45 |

Siempre con `stratify=y` para preservar la distribución de clases en cada partición.

Archivos generados: `data/processed/train.csv`, `validation.csv`, `test.csv`.

---

## Paso 5 — Entrenamiento

### Modelo baseline: `LogisticRegression`

```python
LogisticRegression(max_iter=1000, class_weight='balanced')
```

Entrenado sobre `train`, evaluado sobre `validation`.

### Modelos alternativos evaluados

| Notebook | Modelo | Features |
|----------|--------|----------|
| `3_entrenamiento.ipynb` | LogReg (Exp 0) | TF-IDF solo |
| `5_entrenamiento_v2.ipynb` | LogReg (Exp 1) | TF-IDF + manuales |
| `7_entrenamiento_v3.ipynb` | XGBoost + Grid Search + k-fold (Exp 2) | TF-IDF + manuales |

Grid Search de XGBoost: `StratifiedKFold(k=5)`, scoring `f1_macro`.

---

## Paso 6 — Evaluación (`functions.evaluar_modelo`)

Métricas calculadas sobre el conjunto de test:

- Classification report por clase
- F1-macro (métrica principal)
- Accuracy
- Matriz de confusión
- Curva ROC multiclase (OvR)

Ver resultados completos en [`metricas.md`](metricas.md).

---

## Paso 7 — Explicabilidad SHAP

Implementado en `9_shap_explicabilidad.ipynb` con `functions.explicar_con_shap`.

- **`shap.LinearExplainer`** para LogisticRegression (eficiente, no requiere muestreo de background)
- Genera beeswarm plots (top 20 features por clase) y waterfall plots (predicciones individuales)

Plots guardados en `model/`:
- `shap_beeswarm_{clase}.png`
- `shap_waterfall_idx{i}_{clase}.png`

---

## Paso 8 — Serialización (`functions.guardar_pipeline_completo`)

Artefactos guardados con joblib en `model/`:

| Archivo | Contenido |
|---------|-----------|
| `mejor_modelo.joblib` | Modelo entrenado (LogReg baseline) |
| `mejor_modelo_tfidf.joblib` | TF-IDF vectorizer ajustado sobre train |
| `label_encoder.joblib` | LabelEncoder para el XGBoost |
| `model_metadata.json` | Nombre, fecha, experimento origen, F1-macro test, features usadas |

---

## Paso 9 — Registro MLflow (`functions.registrar_modelo_en_registry`)

Servidor: configura `MLFLOW_TRACKING_URI` en tu `.env` (p. ej. `MLFLOW_TRACKING_URI=https://tu-servidor:5000`)
Experimento: `clasificador_riesgo_ia`
Nombre registrado: `clasificador_riesgo_ia`
Stage: `Production`

Todos los notebooks usan el helper `log_mlflow_safe()` con `try/except` para que un servidor caído no interrumpa el flujo de ejecución.

---

## Decisiones de diseño

### ¿Por qué LogReg baseline supera a XGBoost?

Con 300 muestras y texto TF-IDF de alta dimensionalidad (3811 términos sparse), LogReg tiene ventaja:

- TF-IDF produce features linealmente separables en la mayoría de clasificaciones de texto
- XGBoost está diseñado para features densas y con interacciones no lineales; no explota bien la sparsidad
- El dataset es demasiado pequeño para que Grid Search encuentre configuraciones de XGBoost robustas

### ¿Por qué bigramas y no unigramas?

Los bigramas capturan expresiones del dominio legal que los unigramas pierden: "alto riesgo", "sistema biométrico", "identificación automática". En el dominio legal, la colocación de palabras tiene alto valor semántico.

### ¿Por qué `LinearExplainer` y no `KernelExplainer` para SHAP?

`KernelExplainer` es model-agnostic pero requiere muestreo de background (~100+ muestras) y es lento. `LinearExplainer` es exacto para modelos lineales (LogReg) y no necesita muestreo. Al tener el mejor modelo como LogReg, `LinearExplainer` es la elección correcta.

---

## Reproducibilidad

Ejecutar los notebooks en orden dentro de `src/classifier/classifier_dataset_artificial/` o `classifier_dataset_real/`:

```
1_analisis_exploratorio.ipynb
2_preprocesado y división.ipynb
3_entrenamiento.ipynb         ← Exp 0 baseline
4_metricas.ipynb
5_entrenamiento_v2.ipynb      ← Exp 1 features manuales
6_metricas_v2.ipynb
7_entrenamiento_v3.ipynb      ← Exp 2 XGBoost
8_comparativa_final.ipynb
9_shap_explicabilidad.ipynb
10_modelo_final_y_registro.ipynb
11_preparacion_dataset_finetune.ipynb
12_finetune_qlora.ipynb       ← ejecutar en Google Colab T4
```

Dependencias: `pip install -r requirements/ml.txt`

Todos los notebooks incluyen en la primera celda:

```python
import sys, os
sys.path.insert(0, os.path.abspath('..'))  # accede a functions.py compartido
```
