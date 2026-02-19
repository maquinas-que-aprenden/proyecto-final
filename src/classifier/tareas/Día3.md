# Tareas Día 3 — XGBoost, Grid Search, k-fold y comparativa final

## Estado de partida
- **Exp 0 (Día 1)**: LogReg + TF-IDF baseline → F1-macro val: 0.87
- **Exp 1 (Día 2)**: LogReg + TF-IDF + features manuales → pendiente de ejecutar notebooks 5-6
- **Dataset**: 300 muestras (train 210 / val 45 / test 45), 4 clases
- **Notebooks existentes**: 1 (EDA), 2 (preprocesado), 3 (baseline), 4 (métricas baseline), 5 (entrenamiento v2), 6 (métricas v2)

## Notebooks nuevos (Día 3)
| Notebook | Contenido |
|---|---|
| `7_entrenamiento_v3.ipynb` | XGBoost + Grid Search + k-fold CV + MLflow Exp 2 |
| `8_comparativa_final.ipynb` | Comparativa de los 3 modelos + selección del mejor + conclusiones |

---

## Roadmap

### 1. Añadir XGBoost a requirements.txt → `requirements.txt`
- Añadir `xgboost` con versión pineada

### 2. Crear función de entrenamiento XGBoost → `functions.py`
- Implementar función `entrenar_xgboost(X_train, y_train, X_val, y_val, params)` que:
  - Entrene un `XGBClassifier` con los parámetros dados
  - Evalúe en validación y muestre classification report + F1-macro
  - Devuelva el modelo entrenado

### 3. Crear función de Grid Search con k-fold CV → `functions.py`
- Implementar función `grid_search_cv(modelo, param_grid, X_train, y_train, cv=5)` que:
  - Use `GridSearchCV` con `StratifiedKFold` (k=5) y scoring `f1_macro`
  - Devuelva el mejor modelo, mejores parámetros y resultados del CV
  - Imprima un resumen de los resultados (mejor score, mejores params)

### 4. Entrenar XGBoost con Grid Search + k-fold → `7_entrenamiento_v3.ipynb`
- Cargar train, validation y test desde `data/processed/`
- Vectorizar con TF-IDF (misma config) → `functions.py` (`crear_tfidf`)
- Generar features manuales → `functions.py` (`crear_features_manuales`)
- Concatenar TF-IDF + features manuales → `functions.py` (`combinar_features`)
- Definir grid de hiperparámetros para XGBoost:
  - `n_estimators`: [100, 200, 300]
  - `max_depth`: [3, 5, 7]
  - `learning_rate`: [0.01, 0.1, 0.2]
  - `subsample`: [0.8, 1.0]
- Ejecutar Grid Search con k-fold CV (k=5) sobre train
- Entrenar el mejor modelo sobre train completo
- Evaluar en validación
- Guardar artefactos en `model/` (modelo XGBoost, vectorizador)
- **Registrar Experimento 2 en MLflow** → `7_entrenamiento_v3.ipynb`:
  - Parámetros: mejores hiperparámetros del Grid Search, config TF-IDF, features manuales
  - Métricas: best CV score (f1_macro), val f1_macro, val accuracy
  - Artefactos: modelo, vectorizador

### 5. Comparativa final de los 3 modelos → `8_comparativa_final.ipynb`
- Cargar los 3 modelos (o sus métricas guardadas):
  - Exp 0: LogReg + TF-IDF (baseline) → desde notebook 4
  - Exp 1: LogReg + TF-IDF + features manuales → desde notebook 6
  - Exp 2: XGBoost + TF-IDF + features manuales + Grid Search → desde notebook 7
- Evaluar los 3 sobre test con las mismas métricas:
  - F1-macro, accuracy, precision macro, recall macro
  - ROC AUC macro
  - Matriz de confusión por modelo
- Tabla resumen comparativa → `8_comparativa_final.ipynb`
- Gráfico de barras comparando F1-macro por modelo → `8_comparativa_final.ipynb`
- Análisis de errores del mejor modelo → `8_comparativa_final.ipynb`
- **Seleccionar el mejor modelo** y documentar justificación → `8_comparativa_final.ipynb`
- Registrar comparativa en MLflow → `8_comparativa_final.ipynb`

---

## Orden de ejecución
1. `requirements.txt` — Añadir xgboost
2. `functions.py` — Crear `entrenar_xgboost()` y `grid_search_cv()`
3. `7_entrenamiento_v3.ipynb` — XGBoost + Grid Search + k-fold + guardar artefactos + MLflow Exp 2
4. `8_comparativa_final.ipynb` — Evaluar los 3 modelos en test + tabla comparativa + selección del mejor + MLflow
