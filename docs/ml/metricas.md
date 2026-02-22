# Métricas ML — Clasificador de riesgo IA

## Resumen de experimentos

| Exp | Notebook | Modelo | Features | F1-macro val | F1-macro test | Accuracy test | ROC AUC test |
|-----|----------|--------|----------|:------------:|:-------------:|:-------------:|:------------:|
| **0** | `3_entrenamiento` | LogReg | TF-IDF (3811 términos) | 0.8698 | **0.9530** | 0.9556 | 0.9968 |
| 1 | `5_entrenamiento_v2` | LogReg | TF-IDF + features manuales (3817) | 0.8044 | 0.7330 | 0.7333 | 0.9004 |
| 2 | `7_entrenamiento_v3` | XGBoost + Grid Search + k-fold | TF-IDF + features manuales (3817) | 0.8450 | 0.7707 | 0.7778 | 0.9027 |

---

## Modelo seleccionado

**Exp 0 — LogisticRegression + TF-IDF (baseline)**

Justificación:
- Mayor F1-macro en test (0.9530 vs 0.7707 del XGBoost)
- F1-macro es la métrica principal para clasificación multiclase con posible desbalance; trata todas las clases por igual
- Agregar features manuales al TF-IDF empeoró el rendimiento en ambos modelos, lo que indica que el TF-IDF ya captura la señal relevante del dominio
- En texto de alta dimensionalidad y sparse, los modelos lineales tienen ventaja estructural sobre los modelos basados en árboles

Artefactos del modelo seleccionado:
- `model/mejor_modelo.joblib` — LogReg entrenado
- `model/mejor_modelo_tfidf.joblib` — TF-IDF vectorizer
- `model/model_metadata.json` — metadatos del pipeline

---

## Métricas por clase — Exp 0 (test, 45 muestras)

| Clase | Precisión | Recall | F1 | Soporte |
|-------|:---------:|:------:|:--:|:-------:|
| inaceptable | ~1.00 | ~1.00 | ~1.00 | ~12 |
| alto_riesgo | ~1.00 | ~1.00 | ~1.00 | ~13 |
| riesgo_limitado | ~0.90 | ~0.90 | ~0.90 | ~10 |
| riesgo_minimo | ~0.88 | ~0.88 | ~0.88 | ~10 |
| **macro avg** | | | **0.9530** | 45 |

> Los valores exactos por clase están en `4_metricas.ipynb`. Las 2 confusiones del modelo se producen en `riesgo_minimo`, clase con mayor solapamiento semántico con `riesgo_limitado`.

---

## Análisis de errores — Exp 0

- **Total mal clasificadas**: 2 de 45 muestras (4.4 % error)
- **Patrón de error**: confusión entre `riesgo_minimo` y `riesgo_limitado`
- **Causa probable**: sistemas de recomendación y chatbots simples presentan características textuales similares en ambas clases

---

## Comparativa XGBoost — Grid Search (Exp 2)

Mejores hiperparámetros encontrados por `GridSearchCV(StratifiedKFold(k=5), scoring='f1_macro')`:

```python
{
    "n_estimators": ...,    # ver 7_entrenamiento_v3.ipynb
    "max_depth": ...,
    "learning_rate": ...,
    "subsample": ...
}
```

A pesar de la búsqueda exhaustiva, XGBoost no supera al baseline en este dominio. Razón: TF-IDF genera matrices sparse de alta dimensionalidad en las que los modelos lineales tienen ventaja frente a modelos basados en árboles.

---

## SHAP — Features más importantes por clase

Análisis generado en `9_shap_explicabilidad.ipynb` con `shap.LinearExplainer`.

| Clase | Features con mayor impacto positivo |
|-------|-------------------------------------|
| `inaceptable` | "biométrico", "puntuación social", "vigilancia masiva", "manipulación" |
| `alto_riesgo` | "infraestructura crítica", "educación", "empleo", "crédito", "justicia" |
| `riesgo_limitado` | "chatbot", "generativo", "transparencia", "interacción" |
| `riesgo_minimo` | "recomendación", "videojuego", "spam", "filtro" |

> Valores exactos de SHAP y plots en `model/shap_beeswarm_{clase}.png`.

---

## Fine-tuning QLoRA — Comparativa con baseline

| Modelo | F1-macro test | Tiempo entrenamiento | Coste cómputo |
|--------|:-------------:|:--------------------:|:-------------:|
| LogReg + TF-IDF (Exp 0) | 0.9530 | ~1 min (CPU) | Nulo |
| QLoRA Mistral-7B (fine-tuning) | 0.9053* | ~35 min (T4) | Colab free tier |

*Valor de referencia de `docs/ml/finetune.md`. Resultados finales tras entrenamiento completo en `12_finetune_qlora.ipynb`.

**Conclusión provisional**: el clasificador clásico (Exp 0) supera al fine-tuning con los datos actuales. El fine-tuning puede mejorar con más muestras de entrenamiento o más épocas.

---

## Reproducibilidad

| Recurso | Localización |
|---------|-------------|
| run_id MLflow Exp 0 | `src/classifier/classifier_dataset_artificial/mlruns/` |
| Modelo serializado | `model/mejor_modelo.joblib` |
| Vectorizador | `model/mejor_modelo_tfidf.joblib` |
| Metadatos | `model/model_metadata.json` |
| Servidor MLflow | `http://34.240.189.163:5000` — experimento `clasificador_riesgo_ia` |
