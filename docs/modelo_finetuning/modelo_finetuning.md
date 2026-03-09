# RAG Grader Fine-tuning — Documentación del modelo

## Descripción

Modelo de **clasificación binaria de relevancia documental** para el pipeline RAG de NormaBot.
Determina si un documento recuperado de ChromaDB contiene información útil para responder
una consulta sobre regulación de IA (EU AI Act, BOE, normativa española).

**Clasificación de salida:** `relevante` | `no relevante`

**Arquitectura:** Qwen 2.5 3B-Instruct + adaptador **QLoRA** (4-bit NF4)

---

## Por qué este modelo

### Qwen 2.5 3B vs alternativas

| Modelo | Soporte español | Tamaño | Razonamiento legal |
|--------|----------------|--------|-------------------|
| **Qwen 2.5 3B** | ✓ Excelente | 3B | ✓ Bueno |
| Llama 3.2 3B | Moderado | 3B | Moderado |
| Gemma 2 2B | Moderado | 2B | Limitado |

Qwen 2.5 3B fue seleccionado sobre Llama 3.2 3B y Gemma 2 2B por su **superior
comprensión del español** y razonamiento en contextos legales. El tamaño 3B es
suficiente para grading binario (sí/no), evitando la latencia y coste de modelos mayores.

### Por qué fine-tuning sobre Ollama base

El grading de relevancia legal requiere distinguir documentos del EU AI Act/BOE de
documentos de otros dominios del derecho (Código Civil, etc.) que comparten vocabulario
jurídico pero no son relevantes. El modelo base sin fine-tuning tiende a considerar
relevantes documentos legales en general, no solo los de regulación IA.

---

## Dataset de entrenamiento

| Atributo | Valor |
|----------|-------|
| **Fuente** | `data/processed/grading_dataset.jsonl` |
| **Total ejemplos** | 634 |
| **Relevantes** | 283 (44.6%) |
| **No relevantes** | 351 (55.4%) |
| **Test set** | 96 ejemplos (estratificado) |
| **Formato** | `{query, document, label}` |

Los ejemplos se construyeron a partir del corpus legal indexado en ChromaDB,
emparejando consultas reales con documentos del EU AI Act/BOE (positivos)
y documentos de otras áreas del derecho (negativos).

---

## Configuración del entrenamiento

| Parámetro | Valor |
|-----------|-------|
| Modelo base | `Qwen/Qwen2.5-3B-Instruct` |
| Técnica | QLoRA (4-bit NF4 + adaptador LoRA) |
| Max seq length | 512 tokens |
| Adaptador | `src/finetuning/output/qwen-grader-lora/adapter_final` |
| Plataforma | NVIDIA RTX 4070 Super (12.9 GB VRAM) |

---

## Métricas de evaluación (test set, 96 ejemplos)

### Comparativa global

| Modelo | Accuracy | F1 Macro |
|--------|----------|----------|
| Baseline (Qwen 2.5 3B sin FT) | ~0.85 | 0.85 |
| **Fine-tuned (QLoRA)** | **0.90** | **0.905** |
| **Mejora** | **+5pp** | **+5.5pp** |

### Por clase

| Clase | Métrica | Baseline | Fine-tuned | Δ |
|-------|---------|----------|------------|---|
| `relevante` | Precision | 0.89 | 0.87 | -0.02 |
| `relevante` | Recall | 0.77 | **0.93** | **+0.16** |
| `relevante` | F1 | 0.82 | **0.90** | **+0.08** |
| `no relevante` | Precision | 0.83 | **0.94** | **+0.11** |
| `no relevante` | Recall | 0.92 | 0.89 | -0.03 |
| `no relevante` | F1 | 0.88 | **0.91** | **+0.03** |

**Interpretación clave:**
- El fine-tuning mejora sobre todo el **recall de `relevante` (+0.16)**: el modelo
  recupera más documentos relevantes del EU AI Act que sin fine-tuning. En un sistema RAG,
  un falso negativo (documento relevante descartado) es el error más costoso.
- La **precision de `no relevante` mejora +0.11**: filtra mejor los documentos
  de otros dominios jurídicos que el modelo base acepta erróneamente.

---

## Integración en el pipeline RAG

El grader fine-tuned está integrado en `src/rag/main.py` con fallback automático:

```
grade(query, docs)
    │
    ├── ¿Adaptador LoRA disponible?  →  SÍ  →  _grade_with_finetuned()
    │                                              · predict_relevance() [grader.py]
    │                                              · Qwen 2.5 3B + QLoRA
    │
    └──────────────────────────────  →  NO  →  _grade_with_ollama()
                                               · ChatOllama("qwen2.5:3b")
                                               · Modelo base via Ollama
```

### Activar el modelo fine-tuned

El adaptador se carga automáticamente si existe en disco. Para verificar disponibilidad:

```python
from src.finetuning.grader import is_available
print(is_available())  # True si adapter_model.safetensors existe
```

### Usar el grader directamente

```python
from src.finetuning.grader import predict_relevance

resultado = predict_relevance(
    query="¿Qué prácticas de IA están prohibidas por el EU AI Act?",
    document="El artículo 5 prohíbe sistemas que usen técnicas subliminales..."
)
# → "relevante"
```

---

## Artefactos

```
src/finetuning/
├── grader.py                              ← wrapper de inferencia con lazy loading
├── model/                                 ← directorio del adaptador (gitignored si >100MB)
│   └── adapter_model.safetensors         ← pesos LoRA
├── output/qwen-grader-lora/
│   └── adapter_final/                    ← adaptador final guardado post-entrenamiento
└── docs/
    └── modelo_finetuning.md              ← este archivo

Notebooks:
├── 01_dataset_creacion.ipynb             ← construcción del dataset de grading
├── 02_entrenamiento.ipynb                ← fine-tuning QLoRA
├── 03_pruebas.ipynb                      ← evaluación y comparativa baseline vs FT
└── 04_metricas_mlflow.ipynb             ← registro en MLflow
```

---

## Tests unitarios

El módulo de fine-tuning cuenta con una suite de tests en `tests/test_finetuning.py`
que no requieren GPU ni descargar los artefactos del modelo. Se ejecutan con:

```bash
pytest tests/test_finetuning.py -v
```

**Resultado:** 45 tests passing (~9s, sin GPU).

### Cobertura por área

| Clase de test | Nº tests | Qué verifica |
|---|---|---|
| `TestConstants` | 4 | Valores de `LABEL_RELEVANTE`/`LABEL_NO_RELEVANTE`, `LABELS`, `GRADING_SYSTEM_PROMPT`, `MLFLOW_EXPERIMENT_NAME`; coherencia entre `grader.py` y `functions.py` |
| `TestLoadGradingDataset` | 4 | Carga de JSONL válido, error si falta el fichero (`AssertionError`), ignora líneas vacías, conteo correcto de etiquetas |
| `TestSplitDataset` | 5 | Proporciones 70/15/15, ausencia de solapamiento entre splits, total conservado, estratificación balanceada (±10%), reproducibilidad con misma seed |
| `TestBuildGradingMessages` | 5 | Estructura system/user del chat template, query y document presentes en el mensaje de usuario, inputs vacíos no fallan |
| `TestFormatTrainingPrompt` | 3 | El prompt de entrenamiento termina en `label + eos_token`, incluye el template del tokenizador, llama a `apply_chat_template` con `add_generation_prompt=True` |
| `TestPredictRelevanceFunctions` | 5 | Parseo de respuestas del LLM en `functions.py`: "relevante", "no relevante", "no es relevante", respuesta ambigua → conservador (`no relevante`), prioridad `no relevante` sobre `relevante` en texto mixto |
| `TestPrintComparison` | 4 | Cálculo correcto de deltas, delta negativo, delta cero, tabla impresa en stdout |
| `TestGetMlflowPassword` | 2 | Lectura desde variable de entorno, `EnvironmentError` si no está definida |
| `TestGraderIsAvailable` | 3 | `False` si el directorio del adaptador no existe, `False` si existe el directorio pero falta `adapter_model.safetensors`, `True` si el fichero está presente |
| `TestGraderPredictRelevanceParsing` | 6 | Parseo de respuestas en `grader.py` (con `_load_model` mockeado): "relevante", "no relevante", "no es relevante", ambigua → conservadora, mayúsculas normalizadas con `.lower()`, texto extra tras la etiqueta |
| `TestGraderLoadModelErrors` | 2 | `FileNotFoundError` cuando el adaptador no existe en disco, `ImportError` cuando `transformers`/`peft` no están instalados |
| `TestDatasetStructure` | 2 | Campos obligatorios (`query`, `document`, `label`) y valores no vacíos en el JSONL real; se saltan automáticamente si no hay `dvc pull` |

### Decisiones de diseño

- **Sin GPU ni modelo real:** todos los tests de inferencia usan `unittest.mock` para aislar
  la lógica de parseo del peso del modelo (>6 GB). Esto permite ejecutarlos en CI sin coste.
- **`@pytest.mark.skipif` para artefactos DVC:** los tests de `TestDatasetStructure` se
  saltan si `data/processed/grading_dataset.jsonl` no existe, evitando fallos en entornos
  sin DVC configurado.
- **Fixtures de `tmp_path`:** los tests de carga de dataset usan el directorio temporal de
  pytest para no dejar ficheros en el repositorio.
- **Singleton reset en `TestGraderLoadModelErrors`:** los tests que prueban la carga del
  modelo restauran `_model`/`_tokenizer`/`_ADAPTER_PATH` a sus valores originales en el
  bloque `finally`, evitando contaminación entre tests.

---

## Experimento MLflow

- **Nombre del experimento**: `grader_relevancia_qwen25_3b` (valor de `MLFLOW_EXPERIMENT_NAME` en `04_metricas_mlflow.ipynb`)
- **Tracking URI**: variable de entorno `MLFLOW_TRACKING_URI` (definida en `.env`)
- **Registro**: `mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)` → `mlflow.set_experiment("grader_relevancia_qwen25_3b")`
- **Referencia código**: celda `mlflow-log-27` de `04_metricas_mlflow.ipynb`
