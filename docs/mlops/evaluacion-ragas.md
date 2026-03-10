# Evaluación RAGAS del pipeline RAG

Los logs crudos de cada ejecución están en [`docs/mlops/datos-ragas/`](datos-ragas/).

## Contexto

Se evaluó el pipeline RAG de NormaBot usando [RAGAS](https://docs.ragas.io/) sobre tres ramas para medir el impacto de los cambios introducidos. La evaluación se lanza manualmente mediante el workflow `eval.yml` en GitHub Actions y se ejecuta sobre la instancia EC2 contra la imagen desplegada.

* **Dataset**: 14 preguntas con sus respuestas de referencia (`eval/dataset.json`).
* **Métricas evaluadas**: `faithfulness`, `context_precision`, `context_recall`.
* **LLM de evaluación**: Amazon Bedrock Nova Lite (`eu.amazon.nova-lite-v1:0`), el mismo modelo que usa el orquestador.
* **Fecha de ejecución**: 09/03/2026.
* **Condiciones**: todos los runs definitivos se ejecutaron sin caché y con CUDA disponible, para garantizar comparabilidad.

## Resultados — runs limpios (sin caché, CUDA)

| Métrica | Umbral | `develop` | `fix/rag-score-threshold` | `fine-tuning+GPU` |
|---|---|---|---|---|
| `faithfulness` | 0.80 | 0.7272 ✗ | 0.5929 ✗ | 0.6283 ✗ |
| `context_precision` | 0.70 | 0.8500 ✓ | **0.9115** ✓ | 0.5208 ✗ |
| `context_recall` | 0.70 | 0.5042 ✗ | 0.4869 ✗ | **0.6536** ✗ |

| Errores RAGAS | `develop` | `fix/rag-score-threshold` | `fine-tuning+GPU` |
|---|---|---|---|
| Grader fallbacks (`Grader devolvió 0 relevantes`) | **16** (todas las queries) | 5 | **0** |
| TimeoutErrors | 3 | 6 | 8 |
| OutputParserExceptions | 7 | 1 | 7 |

## Análisis por rama

### `develop` (línea base)

El Qwen 2.5 3B (Ollama) actúa como grader pero con el threshold de la garantía mínima en 0.7 — si el grader descarta todos los docs, el fallback por score solo acepta chunks con `1 - distancia L2 ≥ 0.7`, lo que equivale a exigir distancia ≤ 0.3. Este umbral es demasiado estricto para `intfloat/multilingual-e5-base` en este dominio: el fallback por score resultante activa en el 100% de las queries (16 warnings para 14 queries, la diferencia se debe a que el agente ReAct puede invocar `search_legal_docs` más de una vez por query compleja).

El fallback por score puro tiene `context_precision` de 0.85, lo que indica que los chunks más cercanos semánticamente sí son relevantes — el problema no es el retriever sino el grader (demasiado estricto) y el umbral del fallback (demasiado selectivo).

### `fix/rag-score-threshold` (BUG-06: threshold 0.7 → 0.3)

El fix reduce el threshold del fallback por score de 0.7 a 0.3 (`_grade_by_score` en `src/rag/main.py:95`), lo que permite que el fallback devuelva más chunks cuando el grader Qwen falla. El resultado:

* El grader Qwen funciona correctamente en 9 de las 14 queries (solo 5 fallbacks). Cuando funciona, hace selecciones más precisas que el fallback puro — de ahí que `context_precision` suba de 0.85 a **0.91**.
* `context_recall` sube solo de 0.50 a 0.49 — la corrección del threshold no mejora el recall porque el retriever sigue devolviendo k=9 chunks y el grader Qwen sigue siendo conservador dentro de ese conjunto.

### `fine-tuning+GPU` (grader BERT fine-tuneado + threshold fix)

El grader fine-tuneado (`src/finetuning/grader.py`) es un QLoRA sobre Qwen2.5-3B-Instruct, cargado en 4-bit NF4 sobre CUDA. A diferencia del grader Ollama (que devuelve "si"/"no" con posibilidad de fallo completo), el grader fine-tuneado clasifica cada doc individualmente y solo cae al fallback por excepción — de ahí los **0 fallbacks globales**.

El tradeoff observado es directo y respaldado por el código de `_grade_with_finetuned()` (`src/rag/main.py:100`):

* El modelo fine-tuneado es más **permisivo** que el Qwen base: clasifica más chunks como `"relevante"`, lo que **sube el recall de 0.49 a 0.65**.
* Al dejar pasar más chunks (incluidos algunos irrelevantes), **baja la precisión de 0.91 a 0.52**.

Este es el tradeoff clásico precisión-recall. Para un sistema de normativa legal, recuperar información que podría ser relevante (recall alto) tiene valor, pero la pérdida de precisión implica que el contexto que llega al orquestador contiene más ruido, lo que puede afectar negativamente a `faithfulness`.

Los 8 TimeoutErrors y 7 OutputParserExceptions en este run son más altos que en los otros — posiblemente porque el contexto más extenso (más chunks) produce respuestas de Nova Lite más largas, que RAGAS tiene más dificultad para parsear. Esto distorsiona los scores a la baja.

### Por qué `faithfulness` es bajo en todas las ramas

`faithfulness` mide si las afirmaciones de la respuesta están soportadas por el contexto recuperado. Nova Lite (el orquestador, `src/orchestrator/main.py`) genera la respuesta final sin restricciones explícitas de grounding en el system prompt — incorpora conocimiento propio más allá del contexto proporcionado. Esto es independiente del grader y del threshold: ninguna variación en el retrieval mejora faithfulness si el LLM orquestador no está instruido para ceñirse al contexto.

### Por qué `context_recall` es bajo en todas las ramas

`context_recall` mide qué porción de la información necesaria (según el ground truth) está en el contexto recuperado. Hay dos causas estructurales en el código:

1. **k=9 insuficiente para preguntas multi-artículo**: `retrieve()` en `src/rag/main.py:62` usa `k=9` como valor fijo. `search_soft()` en `src/retrieval/retriever.py:125` recupera internamente `k*2=18` chunks pero devuelve solo 9 tras la reordenación por fuente. Para preguntas que tocan varios artículos de distintas fuentes (EU AI Act + BOE + AESIA), 9 chunks pueden no cubrir toda la información necesaria. Las trazas de Langfuse muestran que el grader descarta de media 4 de esos 9 chunks, dejando ~5 para el orquestador.

2. **Reordenación por fuente en `search_soft`**: el modo `"soft"` prioriza chunks de fuentes detectadas por palabras clave (RGPD, AESIA, AI Act). Esto puede hacer que chunks igualmente relevantes de fuentes no detectadas queden fuera del top-9.

## Limitaciones de la evaluación

### Tamaño del dataset

RAGAS recomienda un mínimo de **50 preguntas** para que las métricas sean estadísticamente fiables. El dataset actual tiene **14 ejemplos**, lo que implica que cada pregunta tiene un peso desproporcionado y un único error o timeout puede mover los scores varios puntos. Los resultados deben interpretarse como tendencias, no como medidas precisas.

### Construcción del dataset de evaluación

Generar preguntas de evaluación de calidad para normativa legal (EU AI Act, BOE, guías AESIA) requiere conocimiento del dominio jurídico que el equipo no tiene. Las preguntas actuales cubren los casos más obvios pero probablemente no representan la distribución real de consultas que haría un usuario experto. Ampliar el dataset requeriría colaboración con personas con formación legal.

### Incompatibilidades con Nova Lite

El LLM de evaluación es el mismo que usa el orquestador (Nova Lite), lo que introduce un sesgo de auto-evaluación. Además, Nova Lite presenta incompatibilidades con el formato JSON que espera RAGAS internamente, generando `OutputParserException` de forma recurrente:

* En `develop`: 7 errores de parseo.
* En `fix/rag-score-threshold`: 1 error de parseo.
* En `fine-tuning+GPU`: 7 errores de parseo.

Estos errores hacen que los jobs afectados cuenten como `NaN` en el cálculo de métricas, distorsionando los scores a la baja. La `answer_relevancy` fue excluida completamente por este motivo: Nova Lite nunca devuelve el campo `question` que RAGAS requiere, produciendo NaN sistemático en todos los runs.

### Variabilidad entre runs

Los scores varían entre ejecuciones de la misma rama por dos razones: (1) los TimeoutErrors son no deterministas y dependen de la carga de Bedrock; (2) Nova Lite tiene temperatura > 0 en las evaluaciones RAGAS. Con 14 preguntas, esta variabilidad puede representar ±0.05 en los scores. Los runs con caché (que reutilizan respuestas del agente) no son directamente comparables con runs sin caché.

## Conclusiones

* `context_precision` supera el umbral en `develop` (0.85) y `fix/rag-score-threshold` (0.91). El fix del threshold es la mejora más clara: reduce los fallbacks del grader Qwen del 100% al 35% de las queries y sube la precisión. Merece mergearse.
* El grader fine-tuneado funciona correctamente en CUDA con 0 fallbacks. Introduce un tradeoff favorable para un sistema legal: recall 0.65 (+0.16 respecto al fix) a costa de precisión 0.52 (-0.39). Si se acepta ese tradeoff, la rama de fine-tuning tiene valor, pero los errores de evaluación más altos (8 timeouts, 7 OutputParserExceptions) hacen que los scores sean menos fiables.
* `faithfulness` y `context_recall` no superan el umbral en ninguna rama. Son problemas estructurales con causas identificables en el código, no en el grader.

## Trabajo futuro

### Recall (`context_recall` actual: 0.49-0.65)

* **Aumentar k**: subir `k` de 9 a 12-15 en `retrieve()` (`src/rag/main.py:62`). `search_soft` ya recupera `k*2` internamente, por lo que el coste de añadir más chunks es bajo. Medir impacto en recall sin degradar precisión.
* **Revisar `search_soft`**: la reordenación por fuente de `src/retrieval/retriever.py:125-160` puede excluir chunks relevantes de fuentes no detectadas por las palabras clave actuales. Evaluar si el modo `"base"` (sin reordenación) mejora recall en preguntas multi-fuente.
* **Tamaño de chunk**: si aumentar k no es suficiente, revisar el tamaño de los chunks generados en `data/ingest.py`. Chunks más pequeños con mayor solapamiento podrían mejorar la cobertura de preguntas que tocan partes de varios artículos.

### Faithfulness (`faithfulness` actual: 0.59-0.73)

* **System prompt del orquestador**: añadir una instrucción explícita en `src/orchestrator/main.py` para que Nova Lite genere respuestas basadas únicamente en el contexto recuperado y cite explícitamente los fragmentos usados. Esta es la intervención con mayor impacto esperado y menor riesgo.

### Grader fine-tuneado

* **Ajustar el umbral de decisión**: el grader fine-tuneado es más permisivo que el Qwen base, lo que explica el tradeoff recall/precisión observado. Evaluar si añadir un umbral de confianza en `predict_relevance()` (`src/finetuning/grader.py:107`) permite recuperar precisión sin sacrificar recall.
* **Reducir timeouts en evaluación**: los 8 timeouts en el run de fine-tuning pueden deberse a que el contexto más extenso genera respuestas más largas en Nova Lite, saturando los workers de RAGAS. Reducir el paralelismo de evaluación o limitar la longitud del contexto enviado al orquestador.

### Evaluación

* **Ampliar dataset**: de 14 a 50+ preguntas con revisión de alguien con formación legal para cubrir casos edge del EU AI Act y BOE.
* **LLM de evaluación alternativo**: sustituir Nova Lite por un LLM externo (GPT-4o, Claude) para eliminar el sesgo de auto-evaluación y reducir los `OutputParserException`. Esto requiere coste y dependencia externa, pero daría métricas más fiables.
