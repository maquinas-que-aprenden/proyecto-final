# Tareas Día 2 — Mejora del modelo clasificador

## Estado de partida
- **Baseline**: LogisticRegression + TF-IDF (bigramas, 3811 términos)
- **F1-macro validación**: 0.87
- **Dataset**: 300 muestras (train 210 / val 45 / test 45), 4 clases
- **Artefactos guardados**: modelo + vectorizador en `model/`

---

## Roadmap

### 1. Features manuales
- Crear nuevas features numéricas a partir del texto:
  - Longitud del texto (n.º de palabras y caracteres)
  - Conteo de entidades NER por tipo (PER, LOC, ORG, MISC)
  - Presencia de palabras clave del dominio (ej. "vigilancia", "biométrico", "chatbot", "scoring")
- Concatenar con la matriz TF-IDF usando `scipy.sparse.hstack`
- Implementar en `functions.py` para reutilizar en inferencia

### 2. Re-entrenar LogReg con features combinadas
- Entrenar LogisticRegression con TF-IDF + features manuales
- Evaluar en validación y comparar con baseline (0.87 F1-macro)
- Documentar si las features manuales mejoran o no el rendimiento

### 3. Registrar Experimento 1 en MLflow
- Conectar al servidor remoto (`http://34.240.189.163:5000`)
- Loggear parámetros: config TF-IDF, features usadas, hiperparámetros del modelo
- Loggear métricas: accuracy, f1_macro (validación)
- Loggear artefactos: modelo, vectorizador

### 4. Notebook 4 — Métricas sobre test
- Cargar modelo y vectorizador desde `model/`
- Evaluar sobre test: classification report, matriz de confusión, F1-macro
- Curva ROC multiclase (con `predict_proba`)
- Análisis de errores: revisar ejemplos mal clasificados, buscar patrones
- Registrar métricas finales y matriz de confusión en MLflow

---

## Orden de ejecución
1. Features manuales (notebook 3 + functions.py)
2. Re-entrenar y evaluar en validación
3. Guardar artefactos actualizados
4. MLflow — log Experimento 1
5. Notebook 4 — métricas sobre test + análisis de errores
6. MLflow — log métricas finales de test
