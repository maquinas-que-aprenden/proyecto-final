# NormaBot — Plan de Mejoras basado en Temario del Bootcamp

**Fecha**: 2026-02-27
**Deadline presentación**: 12 de marzo de 2026 (13 días)
**Objetivo**: Cerrar los gaps entre NormaBot y los módulos vistos en clase para maximizar la cobertura en la evaluación.

---

## Cobertura actual del temario

| Módulo | Tema | Cobertura en NormaBot | Estado |
|--------|------|-----------------------|--------|
| NLP_04 | Procesamiento de texto, spaCy, TF-IDF, NER | spaCy + TF-IDF en clasificador | BIEN |
| ML_09 | XGBoost, GridSearch, métricas, cross-validation | Clasificador completo con SHAP + MLflow | BIEN |
| Deep Learning | CNNs, Transfer Learning | No aplica (NormaBot es NLP/LLM) | N/A |
| 4-Transformers | Arquitectura Transformer from scratch | Se usa vía APIs, no se implementa | N/A |
| 5-Pretraining | Pre-entrenamiento de LLMs | No aplica (usamos modelos existentes) | N/A |
| 6-Prompt Engineering | Zero-shot, few-shot, CoT, roles | Prompts en orquestador y RAG grading | PARCIAL |
| 7-Fine-tuning | QLoRA, PEFT, DPO, RLHF, Toxicity Eval | **NO CUBIERTO** | GAP |
| 8-Reasoning | GRPO, CoT interno | No aplica directamente | N/A |
| 9-LLMOps | Pipelines, monitorización, CI/CD | CI/CD + Docker + MLflow + Langfuse | BIEN |
| 10-Model Evaluation | Benchmarks, ROUGE, métricas | RAGAS pipeline implementado | BIEN |
| 11-Multimodal | Audio, visión | No aplica | N/A |
| 12-VectorStores | Embeddings, FAISS/Chroma, similitud | ChromaDB + sentence-transformers | BIEN |
| 13-RAG | Loaders, chunking, retrieval, reranking | Pipeline Corrective RAG completo | BIEN |
| 14-Agents | Function calling, tools, LangGraph | Orquestador ReAct con 3 tools | BIEN |
| 15-Evaluation | Guardrails, RAGas, seguridad | RAGAS sí, **guardrails NO** | GAP |
| 17-Proyecto Final | End-to-end: data, fine-tune, RAG, deploy | Casi completo, faltan algunos gaps | PARCIAL |

**Resultado**: 8/11 módulos relevantes bien cubiertos. 3 gaps principales + 2 parciales.

---

## Gaps identificados y mejoras propuestas

### Gap 1: Evaluación Sistemática de Sesgos + Feedback Loop — PRIORIDAD ALTA

**Módulos que cubre**: 7 (Model Toxicity Evaluation), 8 (Métricas — datasets desbalanceados), 10 (Model Evaluation), 15 (RAG Evaluation & RAGas)

#### Parte A — Análisis de sesgos del clasificador

- **Ubicación**: `data/notebooks/bias_analysis.ipynb`
- **Contenido**:
  - Rendimiento por área legal (RGPD vs EU AI Act vs AESIA) — precision/recall/F1 por subgrupo
  - Rendimiento por clase de riesgo — matriz de confusión detallada
  - Reutilizar `analisis_errores()` de `src/classifier/functions.py`
  - Documentar limitaciones del dataset pequeño (200-300 ej.) con intervalos de confianza
  - Identificar qué tipos de sistemas de IA confunde más y por qué
  - Conclusión: "sabemos dónde falla y por qué" + plan de mitigación
- **Responsable**: Rubén (ML+NLP)
- **Esfuerzo**: S (3-4h)
- **Por qué importa**: La guía del bootcamp preguntará sobre sesgos y métricas. Este notebook da respuestas directas. Demuestra madurez de ingeniero: no solo "funciona", sino "sabemos dónde falla y por qué".

#### Parte B — Sistema de feedback del usuario

- **Ubicación**: `app.py` (modificar chat UI existente)
- **Contenido**:
  - `st.feedback(options="thumbs")` después de cada respuesta
  - Guardar en JSON/SQLite: `{query, response, feedback, timestamp, session_id}`
  - Permite hablar de ciclo de mejora continua en la presentación
- **Responsable**: Maru (Agents+UI)
- **Esfuerzo**: S (2-3h, ~20-30 líneas de Streamlit)
- **Por qué importa**: Cierra el ciclo del pipeline obligatorio (paso 9: Monitoreo) y demuestra pensamiento de producto.

---

### Gap 2: Guardrails y Seguridad — PRIORIDAD ALTA

**Módulos que cubre**: 15 (Agents Evaluation — Guardrails, safety classification, moderación)

- **Ubicación**: `src/orchestrator/main.py`
- **Contenido**:
  - **Input guard**: Detectar queries fuera de dominio (no legales) y rechazarlas educadamente
  - **Output guard**: Verificar que SIEMPRE aparece el disclaimer legal ("Informe preliminar generado por IA. Consulte profesional jurídico.")
  - **Citation guard**: Validar que las citas legales mencionadas existen en el corpus
- **Responsable**: Maru (Agents+UI)
- **Esfuerzo**: S-M (2-4h)
- **Por qué importa**: NormaBot es un sistema legal donde la seguridad es crítica. El temario cubre LlamaGuard y moderación de inputs/outputs. Esta mejora demuestra responsabilidad en dominio sensible.

---

### Gap 3: Fine-tuning (Notebook QLoRA) — PRIORIDAD ALTA

**Módulos que cubre**: 7 (Fine-tuning — QLoRA, PEFT, DPO, RLHF)

- **Ubicación**: `notebooks/fine_tuning_analysis.ipynb`
- **Contenido**:
  - Documentar **por qué** se eligió Qwen 2.5 3B para grading (benchmark vs Llama 3.2 3B, Gemma 2 2B)
  - Mostrar un **experimento de QLoRA** sobre un modelo pequeño (ej: fine-tune para clasificación de relevancia legal), aunque sea con pocos datos
  - Si no hay tiempo para entrenar: documentar la **estrategia de fine-tuning** que se habría seguido con más datos/tiempo/GPU
  - Métricas de comparación: latencia, calidad de grading, consumo de VRAM
- **Responsable**: Rubén (ML+NLP)
- **Esfuerzo**: M (4-6h si es notebook real con entrenamiento, 2h si es documentación + análisis)
- **Por qué importa**: El temario dedica un módulo entero a fine-tuning. Es el gap más visible para un evaluador. Al menos un notebook experimental demuestra que se conoce la técnica.

---

### Gap 4: Prompt Engineering Documentado + Memoria Conversacional — PRIORIDAD MEDIA

**Módulos que cubre**: 6 (Prompt Engineering — zero-shot, few-shot, CoT, roles, **LAB9: Chatbot con mantenimiento de contexto**), 14 (Agents — orquestación multi-paso)

#### Parte A — Notebook de prompt engineering

- **Ubicación**: `data/notebooks/prompt_engineering.ipynb`
- **Contenido**:
  - Prompts usados en RAG grading (zero-shot con criterios de relevancia)
  - Prompts del orquestador (role-based: "Eres un experto en regulación de IA...")
  - Prompts de generate() (síntesis con citas legales)
  - Iteraciones realizadas: versión 1 → problemas → versión 2 → mejora
  - Técnicas aplicadas: zero-shot, role prompting, structured output (JSON)
- **Responsable**: Maru/Dani
- **Esfuerzo**: S (2-3h)
- **Por qué importa**: Ya se usan técnicas de prompt engineering, pero no hay documentación de la iteración. Un notebook que muestre el proceso demuestra dominio del módulo 6.

#### Parte B — Memoria de usuario/conversación

- **Ubicación**: `src/orchestrator/main.py` + `app.py`
- **Contenido**:
  - **Historial de conversación**: Mantener las últimas N interacciones (query + respuesta) y pasarlas como contexto al LLM en cada turno. Permite preguntas de seguimiento ("¿Y qué dice el artículo 5?" sin repetir contexto).
  - **Memoria por sesión**: Usar `st.session_state` en Streamlit para acumular el historial del chat. El orquestador recibe `chat_history: list[dict]` además de la query actual.
  - **Inyección en prompt**: Añadir el historial como mensajes previos en la llamada al LLM (Bedrock soporta `messages[]` con roles user/assistant). Gestionar el tamaño del contexto con una ventana deslizante o resumen automático.
  - **Persistencia opcional**: Guardar el historial en el mismo JSON/SQLite del feedback (Gap 1B) para análisis posterior de patrones de uso.
- **Responsable**: Maru (Agents+UI)
- **Esfuerzo**: S-M (3-4h)
- **Por qué importa**:
  - El LAB9 del módulo 6 cubre explícitamente "chatbot conversacional con mantenimiento de contexto" — sin memoria, NormaBot es un sistema de pregunta-respuesta aislado, no un chatbot real.
  - En la demo, poder hacer preguntas de seguimiento ("¿Y sobre el artículo 6?", "Explícame más") muestra un producto más maduro.
  - Refuerza el módulo 14 (Agents): un agente con memoria demuestra orquestación multi-paso con estado persistente.
  - Combina bien con el feedback loop (Gap 1B): memoria + feedback = ciclo completo de interacción.

---

### Gap 5: Documentar Grading como Reranking — PRIORIDAD BAJA

**Módulos que cubre**: 13 (RAG avanzado — Document retrieval and Reranking)

- **Ubicación**: Documentación existente (CLAUDE.md, README, o slides)
- **Contenido**:
  - Reframear el Corrective RAG como "LLM-based reranking": el grading con Qwen 2.5 3B actúa como un reranker semántico que descarta documentos irrelevantes
  - Comparar con cross-encoder reranking (técnica vista en clase)
  - Justificar la decisión: grading binario es más interpretable que score continuo para dominio legal
- **Responsable**: Dani (Data+RAG)
- **Esfuerzo**: XS (1h)
- **Por qué importa**: El temario cubre reranking explícitamente. Documentar que ya se hace (de otra forma) evita que parezca un gap.

---

## Cronograma de implementación

| Fecha | Tarea | Quién | Gap |
|-------|-------|-------|-----|
| **27-28 feb** | Notebook de sesgos del clasificador | Rubén | 1A |
| **27-28 feb** | Guardrails input/output en orquestador | Maru | 2 |
| **28 feb - 1 mar** | Feedback loop en Streamlit | Maru | 1B |
| **1-2 mar** | Notebook fine-tuning QLoRA | Rubén | 3 |
| **2-3 mar** | Notebook prompt engineering | Maru/Dani | 4A |
| **2-3 mar** | Memoria conversacional (historial + inyección en prompt) | Maru | 4B |
| **3 mar** | Documentar reranking + report generator LLM | Dani/Maru | 5 |
| **3-5 mar** | Merges + validación e2e + QA | Equipo | — |
| **5-8 mar** | Slides + demo script | Equipo | — |
| **9-11 mar** | Ensayos de presentación | Equipo | — |
| **12 mar** | **PRESENTACION** | | |

**Esfuerzo total estimado**: ~25-30 horas repartidas en el equipo (Rubén: 8-10h, Maru: 12-14h, Dani: 3-4h)

---

## Cobertura resultante del temario

Con los 5 gaps cerrados, NormaBot cubrirá **11 de 11 módulos relevantes** del curso:

| Módulo | Antes | Después | Qué lo demuestra |
|--------|-------|---------|-------------------|
| NLP/spaCy/TF-IDF | BIEN | BIEN | Clasificador |
| ML clásico/métricas | BIEN | BIEN+ | Clasificador + **notebook sesgos** |
| Prompt Engineering | PARCIAL | **BIEN** | **Notebook documentado + memoria conversacional** |
| Fine-tuning/QLoRA | GAP | **BIEN** | **Notebook experimental** |
| LLMOps | BIEN | BIEN | CI/CD + Docker + MLflow + Langfuse |
| Model Evaluation | BIEN | BIEN+ | RAGAS + **análisis de sesgos** |
| VectorStores | BIEN | BIEN | ChromaDB |
| RAG | BIEN | BIEN+ | Corrective RAG + **reranking documentado** |
| Agentes | BIEN | BIEN+ | ReAct con LangGraph + **memoria conversacional** |
| Guardrails/Seguridad | GAP | **BIEN** | **Input/output validation** |
| Feedback/Monitoreo | GAP | **BIEN** | **Thumbs up/down + persistencia** |

---

## Lo que ya está bien cubierto (no tocar, lucir en presentación)

| Temario | Qué demostrar | Dónde está |
|---------|---------------|------------|
| NLP (spaCy, TF-IDF) | Pipeline de features del clasificador | `src/classifier/functions.py` |
| ML clásico (XGBoost, métricas) | Grid Search + StratifiedKFold + SHAP | `src/classifier/functions.py` + notebooks |
| VectorStores (Chroma) | Corpus legal embeddeado + búsqueda semántica | `src/retrieval/retriever.py` |
| RAG completo | Corrective RAG: retrieve, grade, generate | `src/rag/main.py` |
| Agentes (LangGraph) | ReAct agent con 3 tools reales | `src/orchestrator/main.py` |
| LLMOps | CI/CD + Docker + MLflow + Langfuse + DVC | `infra/` + `.github/workflows/` |
| Evaluación RAG | RAGAS con 10 preguntas gold | `data/eval/` |
