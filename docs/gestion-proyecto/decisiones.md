# Registro de decisiones

## 001 | Primera reunión de equipo
*Fecha:* 2026-02-15

### Acuerdos
* Temática: [normabot specs](normabot-specs.html)
* División de tareas:
    * Data + RAG Engineer --> Dani (@danyocando-git)
    * ML + NLP Engineer --> Rubén (@Rcerezo-dev)
    * Agents + UI Lead --> Maru (@mariaeugenia-alvarez)
    * MLOps + Observabilidad --> Nati (@natgarea)
* Mantener reuniones aunque sean breves en el horario del bootcamp: 7PM Lunes, Martes y Jueves.
* Mantener comunicación regular asíncrona por grupo de Discord.

### Acciones pendientes

[x] Cada uno revisa sus tareas para organizarse, plantear dudas y cambios. => 2026-02-16
[x] Crear un requirements.txt para trabajar todos con el mismo. => 2026-02-18

---

## 002 | Inferencia auto-adaptativa en el clasificador
*Fecha:* 2026-02-26
*Autor:* Rubén (@Rcerezo-dev)
*Archivo afectado:* `src/classifier/main.py`
*Commit:* `0b9212f`

### Decisión

Reemplazar la lógica condicional manual en `predict_risk()` por un sistema de
auto-detección del pipeline basado en los artefactos presentes en disco y en la
metadata de `mejor_modelo_seleccion.json`.

### Motivación

Con varios experimentos activos (LogReg, LogReg+keywords, XGBoost+SVD), cambiar
de modelo seleccionado requería editar código manualmente. Cualquier inconsistencia
entre artefactos pasaba desapercibida hasta obtener predicciones silenciosamente
incorrectas.

### Cambios implementados

| Elemento | Descripción |
|----------|-------------|
| `_pipeline_type: str` | Global auto-detectado al cargar artefactos. Valores: `"tfidf_only"`, `"tfidf_svd"`, `"tfidf_svd_manual"` |
| `_validate_pipeline()` | Compara `modelo.n_features_in_` con el conteo calculado de los artefactos. Emite `warning` si difieren |
| `_build_features()` | Construye el vector de features dinámicamente según `_pipeline_type`. Lanza `ValueError` duro ante mismatch (sin padding ni truncado) |
| `predict_risk()` | Paso 2 simplificado a `X_final, feature_names = _build_features(cleaned)` |

### Alternativa descartada: padding/truncado de features

Se consideró rellenar con ceros o truncar el vector si `n_actual != n_expected`.
**Descartada** porque los pesos del modelo están ligados a posiciones concretas de
features: un padding silencioso produce predicciones incorrectas sin ningún error
visible. La solución correcta es fallar rápido con `ValueError` y exigir que todos
los artefactos provengan del mismo experimento.

### Extensibilidad

Añadir un nuevo tipo de pipeline (ej. `"bert_embeddings"`) solo requiere:
1. Un nuevo bloque en `_build_features()`
2. Actualizar `_validate_pipeline()` con la fórmula de features esperadas
3. El resto del código no cambia