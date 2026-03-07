# Clasificador BERT — Documentación del modelo

## Descripción

Modelo de clasificación de sistemas de IA por nivel de riesgo según el **EU AI Act**,
basado en fine-tuning de `dccuchile/bert-base-spanish-wwm-cased` (BERT base entrenado
sobre corpus en español).

**4 categorías de salida:**
- `inaceptable` — Práctica prohibida (Art. 5 EU AI Act)
- `alto_riesgo` — Sistema de alto riesgo (Anexo III EU AI Act)
- `riesgo_limitado` — Obligaciones de transparencia
- `riesgo_minimo` — Sin obligaciones regulatorias específicas

---

## Por qué BERT sobre XGBoost

El clasificador XGBoost actual (F1 macro = 0.8822) se basa en **TF-IDF + SVD**:
representa el texto como frecuencias de palabras sin considerar el orden ni el contexto.
Para textos legales, esto es una limitación crítica:

| Aspecto | XGBoost + TF-IDF | BERT |
|---------|-----------------|------|
| Representación | Bag of words (frecuencias) | Embeddings contextuales |
| Contexto | No captura | Captura dependencias a largo plazo |
| Ambigüedad | No resuelve | Resuelve por contexto |
| Nuevas palabras | OOV → ignoradas | Subword tokenization |
| Ejemplo | "sistema de puntuación" = igual en todos los contextos | Distingue "puntuación escolar" de "puntuación social ciudadana" |

**Ejemplo concreto:** La frase *"sistema que puntúa a los ciudadanos según su comportamiento"*
requiere entender la relación semántica entre "puntúa", "ciudadanos" y "comportamiento"
para clasificarla como `inaceptable` (Art. 5.1.c). TF-IDF puede fallar si esas palabras
aparecen en otros contextos; BERT las evalúa conjuntamente.

---

## Arquitectura del pipeline

```
texto original
     │
     ▼
limpiar_texto()          ← spaCy: stopwords, lematización (mismo que XGBoost)
     │
     ▼
BertTokenizer            ← tokenización subword, max_length=256
     │
     ▼
BertForSequenceClassification  ← 12 capas transformer, 109M parámetros
     │
     ▼
softmax → 4 clases
     │
     ▼
_annex3_override()       ← override determinista Anexo III (mismas reglas que XGBoost)
     │
     ▼
predict_risk_bert() → dict
```

---

## Métricas de evaluación

### Entrenamiento (dataset sintético aumentado, ~4.000 ejemplos)

| Epoch | F1 Macro (val) | Loss (val) |
|-------|---------------|------------|
| 1     | 0.6314        | 0.8821     |
| 2     | 0.6822        | 0.7462     |
| 3     | 0.7228        | 0.7142     |
| 4     | 0.7289        | 0.6999     |

**Mejor F1 macro (validación): 0.7289**

### Evaluación externa (dataset_sintetico_v2, 285 ejemplos balanceados)

> Nota: los resultados completos se generan ejecutando `evaluar_sintetico_bert.py`
> y el notebook `07_pruebas_datasetv2.ipynb`.

### Comparativa con XGBoost

| Modelo | F1 Macro | Dataset evaluación | Observaciones |
|--------|----------|-------------------|---------------|
| XGBoost + TF-IDF + SVD | 0.8822 | Real (~300 ejemplos) | Optimizado con Grid Search + CV |
| BERT (este experimento) | 0.7289 | Sintético validación | Entrenado en sintético, 4 epochs |

**Nota sobre la comparativa:** los datasets de entrenamiento son distintos y de tamaño
diferente. La comparación directa de F1 no es conclusiva. Con un dataset real suficiente,
BERT tiene capacidad de superar a XGBoost por su comprensión semántica.

---

## Limitaciones conocidas

1. **Dataset sintético**: entrenado en ~4.000 ejemplos generados automáticamente,
   no en casos reales anotados por juristas.
2. **Tamaño de evaluación**: dataset_sintetico_v2 tiene 285 ejemplos balanceados
   artificialmente — no representa la distribución real de sistemas de IA.
3. **Sin SHAP**: BERT no expone importancias de features interpretables directamente.
   La explicabilidad se limita a la confianza del modelo.
4. **Recursos**: requiere ~420MB en disco y GPU recomendada para inferencia en producción.

---

## Uso en producción

### Activar backend BERT

```bash
export CLASSIFIER_BACKEND=bert
```

`predict_risk()` despachará automáticamente a BERT con fallback a XGBoost.

### Llamada directa

```python
from src.classifier.main import predict_risk_bert

result = predict_risk_bert("Sistema de reconocimiento facial en aeropuertos")
# → {"risk_level": "alto_riesgo", "confidence": 0.89, "backend": "bert", ...}
```

### Artefactos requeridos

```
src/classifier/bert_pipeline/models/bert_model/
├── config.json              ← arquitectura + id2label
├── model.safetensors        ← pesos (~420MB, excluido de git)
├── tokenizer.json           ← vocabulario subword
└── tokenizer_config.json    ← configuración tokenizer
```

Los pesos del modelo no se versionan en git. Para reproducir el entrenamiento:

```bash
python src/classifier/bert_pipeline/train.py
```

---

## Experimento MLflow

- **Experimento**: `bert_clasificador_riesgo_ia`
- **Registro**: ejecutar `notebooks/06_mlflow_registro.ipynb`
- **URI**: configurada en `src/classifier/.env` → `MLFLOW_TRACKING_URI`
