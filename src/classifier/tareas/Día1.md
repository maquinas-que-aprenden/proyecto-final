# Tareas Día 1 — Clasificador de riesgo IA (AI Act)

## Estado actual del proyecto
- **Dataset**: 300 muestras, 4 clases (inaceptable ~77, alto_riesgo ~90, riesgo_limitado ~67, riesgo_minimo ~66)
- **Notebook 1 (EDA)**: Terminado
- **Notebook 2 (Preprocesado)**: Parcialmente hecho (falta NER, falta validation set, falta lematización)
- **Notebook 3 (Entrenamiento)**: Vacío
- **Notebook 4 (Métricas)**: Vacío
- **functions.py**: Tiene funciones de limpieza, NER, n-grams, split (pero sin validation)

---

## Notebook 2: Preprocesado de datos

### 2.1 Aplicar NER al dataset (columna `descripcion`)
- Usar `extraer_entidades(df, "descripcion")` de functions.py
- Explorar las entidades extraídas: frecuencia por tipo (PER, LOC, ORG, MISC) y por clase de riesgo
- Valorar si las entidades NER aportan señal discriminativa para el modelo o si son solo exploratorias
  - Si aportan: crear features adicionales (ej. conteo de entidades por tipo por fila)
  - Si no: documentar la conclusión y seguir solo con texto limpio

### 2.2 Preprocesado del texto con lematización
- **Problema actual**: `preparar_dataset()` usa `limpiar_texto` (sin lematización)
- **Acción**: Cambiar a `limpiar_texto_preprocess` (con lematización) en `preparar_dataset()`, o crear la columna `text_final` directamente en el notebook usando `limpiar_texto_preprocess`
- La lematización reduce dimensionalidad del vocabulario y mejora generalización en datasets pequeños

### 2.3 División train / test / validation
- **Problema actual**: Solo se divide en train/test (80/20). No hay validation set
- **Acción**: Dividir en 3 conjuntos con stratify:
  - Train: 70% (210 muestras)
  - Validation: 15% (45 muestras)
  - Test: 15% (45 muestras)
- Guardar los 3 ficheros en `src/classifier/data/processed/`:
  - `train.csv`
  - `validation.csv`
  - `test.csv`
- Actualizar `split_dataset()` en functions.py o hacerlo directamente en el notebook

### 2.4 Consideraciones sobre el dataset pequeño
- 300 muestras con 4 clases es poco. Tenerlo en cuenta al interpretar métricas
- Usar stratify en todas las divisiones para mantener el balance
- Considerar cross-validation en el entrenamiento para obtener métricas más robustas

---

## Notebook 3: Entrenamiento

### 3.1 Carga de datos
- Cargar `train.csv` y `validation.csv` desde `data/processed/`

### 3.2 TF-IDF
- Vectorizar `text_final` con `TfidfVectorizer` de sklearn
- Probar parámetros razonables: `max_features=5000`, `ngram_range=(1,2)`, `sublinear_tf=True`
- Ajustar (fit) solo sobre train, transformar validation y test

### 3.3 Modelo baseline
- Empezar con `LogisticRegression(max_iter=1000)` o `LinearSVC` — ambos funcionan bien con TF-IDF en texto corto
- Entrenar sobre train, evaluar sobre validation
- Si el rendimiento es bajo, probar alternativas: `MultinomialNB`, `SGDClassifier`, `RandomForestClassifier`

### 3.4 Guardar artefactos
- Crear carpeta `src/classifier/model/`
- Guardar con joblib:
  - El modelo entrenado (`modelo_clasificador.joblib`)
  - El vectorizador TF-IDF (`tfidf_vectorizer.joblib`)
  - El LabelEncoder si se usa (`label_encoder.joblib`)

### 3.5 Registro en MLflow
```python
remote_server_uri = "http://34.240.189.163:5000"
mlflow.set_tracking_uri(remote_server_uri)
```
- Registrar:
  - Parámetros del modelo y del TF-IDF
  - Métricas de validation (accuracy, f1_macro)
  - Artefactos (modelo, vectorizador)

---

## Notebook 4: Métricas

### 4.1 Evaluación sobre el conjunto de test
- Cargar modelo y vectorizador desde `model/`
- Cargar `test.csv`
- Generar predicciones

### 4.2 Métricas a calcular
- **Classification report**: precision, recall, f1-score por clase y macro/weighted
- **Matriz de confusión**: con `ConfusionMatrixDisplay` de sklearn
- **F1-score macro**: métrica principal (trata todas las clases por igual)
- **Curva ROC multiclase**: usar `OneVsRestClassifier` o `predict_proba` + `roc_auc_score(multi_class='ovr')`
  - Nota: Si se usa LinearSVC, no tiene `predict_proba` nativo. Usar `CalibratedClassifierCV` para envolverlo, o usar LogisticRegression directamente

### 4.3 Análisis de errores
- Revisar los ejemplos mal clasificados: buscar patrones (ej. confusiones frecuentes entre alto_riesgo y riesgo_limitado)
- Documentar conclusiones

### 4.4 Registro de métricas en MLflow
- Loggear las métricas finales de test
- Loggear la matriz de confusión como artefacto (imagen)

---

## Orden de ejecución recomendado
1. Corregir `preparar_dataset` para usar lematización
2. Notebook 2: NER + preprocesado + split en 3 conjuntos
3. Notebook 3: TF-IDF + modelo baseline + guardar + MLflow
4. Notebook 4: Métricas sobre test + análisis de errores + MLflow
