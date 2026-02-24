# NormaBot — Diagnóstico Técnico

Fecha: 2026-02-23 (actualizado sesión tarde — unificación classifier + sync develop)
Fecha: 2026-02-24 (actualizado) | Rama: feature/tools

---

## 1. Mapa del Estado Actual

### Componentes FUNCIONALES (código real, ejecutable)

| Componente | Ubicación | Estado |
|---|---|---|
| **Clasificador ML — 3 experimentos paralelos** | `src/classifier/` | Completo. Tres carpetas: `classifier_dataset_artificial/`, `classifier_dataset_fusionado/`, `classifier_dataset_real/`. Cada una con notebooks 1–12 y subcarpetas `data/`, `model/`, `datasets/`. MLflow registra en experimentos separados. |
| **`functions.py` unificado** | `src/classifier/functions.py` | **Un único archivo** compartido por los 3 experimentos. Base: versión fusionado (la más completa). Incluye: `KEYWORDS_DOMINIO` expandido (55+ kw), `_PALABRAS_SUPERVISION`, `crear_features_manuales()` con 5 features (incluye `kw_salvaguarda`), `crear_tfidf()` con `min_df`, pipeline completo XGBoost + Grid Search + SHAP + MLflow. Cada notebook sobreescribe `functions.MLFLOW_EXPERIMENT` y `functions._DATASET_TAGS` en su celda de setup. |
| **NER legal** | `src/classifier/functions.py` → `extraer_entidades()`, `resumen_entidades()` | Funcional. spaCy `es_core_news_sm` con `nlp.pipe` para batch processing. |
| **Orquestador ReAct** | `src/orchestrator/main.py` | Funcional pero con tools stub. Agente ReAct con Bedrock Nova Lite, system prompt bien diseñado con disclaimer obligatorio. |
| **UI Streamlit** | `app.py` | Funcional. Chat conversacional mínimo conectado al orquestador. |
| **CI/CD** | `.github/workflows/` | Funcional. 3 workflows: PR lint, CI develop, CI/CD main. |
| **Docker** | `Dockerfile`, `docker-compose.yml` | Funcional. python:3.12-slim, healthcheck, ghcr.io. |
| **IaC** | `infra/terraform/`, `infra/ansible/` | Funcional. Terraform + Ansible. |
| **MLflow tracking** | `functions.py` → `configure_mlflow()`, `log_mlflow_safe()` | Funcional. Servidor remoto en EC2. |
| **DVC** | `.dvc/`, `.dvcignore` | Configurado con S3 backend. |

### Componentes EN BRANCHES (implementados pero no mergeados a develop)

| Componente | Ubicación | Rama | Autor | Estado |
|---|---|---|---|---|
| **Corpus legal chunkeado** | `data/chunks_legal/chunks_final.jsonl` | develop (DVC) | Dani | 2.4 MB, BOE + EU AI Act + AESIA + LOPD/RGPD |
| **ChromaDB Retriever** | `src/retrieval/retriever.py` | develop | Dani | `search()`, `search_base()`, `search_soft()` con PersistentClient. Colección `normabot_legal_chunks`. |
| **Notebook chunking** | `src/data/01_chunking_boe_eu_aesia.ipynb` | develop | Dani | Pipeline completo: HTML, PDF → chunks con metadata |
| **Langfuse real** | `src/observability/main.py` | `chore/langfuse` | Nati | CallbackHandler v3, session_id, user_id, tags |
| **Orquestador + Langfuse** | `src/orchestrator/main.py` | `chore/langfuse` | Nati | Instrumentado con `get_langfuse_handler()` |
| **RAGAS pipeline** | `eval/run_ragas.py`, `eval/helpers.py`, `eval/dataset.json` | `feature/RAGAS` | Nati | 10 preguntas gold, faithfulness >= 0.80, modo CI, MLflow logging |
| **Clasificador reestructurado** | `src/classifier/` | `feature/model-ml` | Rubén | 161 archivos, separación datasets real/artificial/fusionado, imágenes SHAP. **Rama synced con develop y pusheada.** |
| **Nodos RAG LangGraph** | `src/rag/` | `feature/rag` | Maru | retrieve, grade_documents, transform_query, generate |

### Componentes STUB (placeholder, aún no implementados)
| **Clasificador ML (dataset real)** | `src/classifier/functions.py` (1297 líneas) + `src/classifier/classifier_dataset_real/` | **FUNCIONAL**. Pipeline end-to-end completo: `limpiar_texto()` (spaCy fallback regex), `crear_features_manuales()` (keywords AESIA + dominio), `TfidfVectorizer`, `LogisticRegression` + `XGBoost`, `GridSearchCV` con `StratifiedKFold`, evaluación (confusion matrix, ROC multiclase), SHAP (beeswarm + waterfall plots). Modelos serializados: `mejor_modelo.joblib`, `tfidf_vectorizer.joblib`, `label_encoder.joblib`. MLflow tracking activo en `configure_mlflow()`. |
| **Clasificador ML (dataset sintético)** | `src/classifier/classifier_dataset_artificial/` | **FUNCIONAL**. Variante con dataset artificial/aumentado bajo `classifier_2/`. Misma estructura que real pero con datos augmentados (`eu_ai_act_flagged`). Modelos serializados en `model/`. |
| **Clasificador ML (dataset fusionado)** | `src/classifier/classifier_dataset_fusionado/` | **FUNCIONAL**. Variante con dataset fusionado. Añade `svd_transformer.joblib` + `ohe_encoder.joblib` para features avanzadas. Modelos serializados en `model/`. |
| **NER legal** | `src/classifier/functions.py` → `extraer_entidades()`, `resumen_entidades()` | **FUNCIONAL**. spaCy `es_core_news_sm` con `nlp.pipe` para batch processing. Fallback a regex si spaCy no disponible. |
| **ChromaDB Retriever** | `src/retrieval/retriever.py` (155 líneas) | **FUNCIONAL**. PersistentClient con **inicialización lazy** (`_get_collection()` singleton). Apunta a `/data/processed/vectorstore/chroma/`. `search()`, `search_base()`, `search_soft()` con prioridad de fuentes (RGPD, AESIA, EU_AI_ACT). `search_tool()` expone API para agentes (string formateado listo para LLM). No crashea si vectorstore no existe. |
| **RAG retrieve** | `src/rag/main.py` línea 36-53 | **FUNCIONAL**. `retrieve(query, k=5)` llama a `src.retrieval.retriever.search(query, k, mode="soft")`. Convierte formato retriever (`text`/`distance`) a formato grade (`doc`/`score`). Error handling: devuelve `[]` si ChromaDB no disponible. |
| **RAG grade** | `src/rag/main.py` línea 59-86 | **FUNCIONAL**. `grade(query, docs)` evalúa relevancia de cada documento con **Ollama Qwen 2.5 3B** (LLM local). Prompt: "¿el documento contiene información útil para responder la pregunta?" → responde "sí"/"no". Fallback doble: si Ollama no disponible → filtro por score; si LLM falla por doc individual → score threshold. Singleton lazy `_get_grading_llm()`. |
| **Corpus legal chunkeado** | `data/processed/chunks_legal/` (DVC-managed, 2.4 MB) | **FUNCIONAL**. `chunks_final.jsonl` y `chunks_final_all_sources.jsonl` con metadata (source, file, unit_title). Versioned en DVC + S3 backend. Importado en `src/retrieval/retriever.py`. |
| **Orquestador ReAct** | `src/orchestrator/main.py` (172 líneas) | **FUNCIONAL PERO TOOLS STUB**. Agente ReAct con `create_react_agent()` + Bedrock Nova Lite v1. System prompt con disclaimer obligatorio. `run()` ejecuta el agente. **PERO**: las 3 tools (`search_legal_docs`, `classify_risk`, `generate_report`) devuelven hardcoded strings, NO llaman a implementaciones reales. |
| **Estado LangGraph** | `src/agents/state.py` | **FUNCIONAL**. `AgentState` TypedDict con `Annotated[list, operator.add]` para acumular documentos y sources. Estructura lista para conectar nodos. |
| **UI Streamlit** | `app.py` (42 líneas) | **FUNCIONAL**. Chat conversacional mínimo, conectado a `src.orchestrator.main.run()`. Sidebar informativo. |
| **Observabilidad Langfuse** | `src/observability/main.py` (34 líneas) | **FUNCIONAL**. `get_langfuse_handler()` devuelve CallbackHandler v3 con session_id, user_id, tags. Requiere env vars: `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`. Ya integrado en `src/orchestrator/main.py` (línea 135). |
| **CI/CD** | `.github/workflows/` (3 workflows) | **FUNCIONAL**. PR lint, CI develop, CI/CD main. |
| **Docker** | `Dockerfile`, `docker-compose.yml` | **FUNCIONAL**. python:3.12-slim, port 8080, healthcheck. |
| **IaC** | `infra/terraform/`, `infra/ansible/` | **FUNCIONAL**. Terraform + Ansible, MLflow server, nginx. |
| **MLflow tracking** | `src/classifier/functions.py` → `configure_mlflow()`, `log_mlflow_safe()` | **FUNCIONAL**. Servidor remoto en EC2 (34.244.146.100), autenticación, soporte multi-entorno. |
| **DVC** | `.dvc/`, `.dvcignore`, `data/processed/*.dvc` | **FUNCIONAL**. Configurado con S3 backend. Archivos versionados: `chunks_final.jsonl.dvc`, `vectorstore.dvc`. |
| **RAGAS evaluation** | `eval/run_ragas.py` (108 líneas), `eval/helpers.py`, `eval/dataset.json` (10 preguntas gold) | **FUNCIONAL**. Pipeline RAGAS completo: KPIs (faithfulness >= 0.80, answer_relevancy >= 0.85), CI mode, MLflow logging. Pronto se integrará en pipeline CI. |

### Componentes STUB (placeholder, aún NO implementados)

| Componente | Ubicación | Estado |
|---|---|---|
| **RAG pipeline generate** | `src/rag/main.py` línea 89-96 | STUB. `generate()` concatena citas statically. No llama a LLM para sintetizar respuesta. TODO: implementar con LLM (Ollama o Bedrock). |
| **Generador de Informes** | `src/report/main.py` línea 6-33 | STUB. `generate_report()` devuelve template string estático con f-strings. No usa LLM. TODO: llamar a Groq con template + datos. |
| **Tool search_legal_docs** | `src/orchestrator/main.py` línea 52-66 | STUB. Devuelve hardcoded string. TODO: llamar a `src.rag.main.retrieve() → grade() → generate()` o a `src.retrieval.retriever.search_tool()` directamente. |
| **Tool classify_risk** | `src/orchestrator/main.py` línea 69-83 | STUB. Devuelve hardcoded string. TODO: exponer `src.classifier.functions.predict()` como función para el orquestador + agregar SHAP explicabilidad. |
| **Tool generate_report** | `src/orchestrator/main.py` línea 86-101 | STUB. Devuelve hardcoded string. TODO: conectar con `src.report.main.generate_report()`. |
| **Data ingesta** | `src/data/main.py` (si existe) | STUB o NO EXISTE. El ingesta real está en `data/ingest.py` (script, no módulo). Chunking: `data/notebooks/01_embeddings_chunks.ipynb` → chunks JSONL. Indexing: `data/index.py` → ChromaDB. TODO: consolidar en módulo `src.data.main` si es necesario. |

### Componentes VACÍOS

| Componente | Estado |
|---|---|
| `tests/` | Vacío. **0 tests unitarios**. RAGAS es evaluación, no tests. TODO: mínimo 3 smoke tests (retrieve, classify, generate). |
| `scripts/` | Solo `.gitkeep`. Sin scripts de scraping versionados. |

---

## 2. Stack Tecnológico (Versiones)

| Capa | Tecnología | Estado |
|---|---|---|
| LLM (orquestador) | Amazon Bedrock Nova Lite v1 | ✓ Integrado en `src/orchestrator/main.py` |
| LLM (RAG grading) | Ollama Qwen 2.5 3B (local) | ✓ Integrado en `src/rag/main.py` — clasificación binaria de relevancia |
| LLM (RAG generation) | Pendiente decisión | ✗ No integrado (STUB en `src/rag/main.py`) |
| Agentes | LangGraph `create_react_agent` | ✓ Funcional (con tools stub) |
| Vector store | ChromaDB PersistentClient | ✓ Funcional en `src/retrieval/retriever.py` |
| Embeddings | paraphrase-multilingual-MiniLM-L12-v2 | ✓ Usado en `data/index.py` (ingesta real) |
| ML Classifier | scikit-learn 1.5.2, XGBoost 3.2.0 | ✓ Funcional (3 experimentos) |
| NLP text cleaning | spaCy 3.8.2 (es_core_news_sm) | ✓ Funcional + fallback regex |
| Explicabilidad | SHAP 0.46.0 | ✓ Funcional (plots en notebooks) |
| Tracking | MLflow 2.17.2 + Langfuse v3 | ✓ Funcional (Langfuse integrado) |
| UI | Streamlit >=1.40.0 | ✓ Funcional |
| Evaluación RAG | RAGAS >=0.2.0 | ✓ Funcional (pipeline 10 Q&A) |
| Data versioning | DVC >=3.50.0 | ✓ Funcional con S3 |
| CI/CD | GitHub Actions (3 workflows) | ✓ Funcional |
| IaC | Terraform + Ansible | ✓ Funcional |

---

## 3. Cambios desde el diagnóstico anterior (2026-02-23)

1. **Merge #43 (refactor/data)** — Consolidó estructura de datos:
   - Renumeró notebooks: `01_chunking_boe_eu_aesia.ipynb` → `01_embeddings_chunks.ipynb`
   - Actualizó rutas de ChromaDB en `src/retrieval/retriever.py`

2. **[2026-02-24] Sprint 1 — Tareas 1.1 y 1.2 completadas** (rama `feature/tools`):
   - **Tarea 1.1**: `retrieve()` conectado a ChromaDB real via `src.retrieval.retriever.search()`. Formato convertido (`text`/`distance` → `doc`/`score`). Error handling graceful.
   - **Tarea 1.2**: `grade()` implementado con **Ollama Qwen 2.5 3B** (LLM local) para evaluación de relevancia documental. Fallback a score threshold si Ollama no disponible.
   - **Lazy init en retriever**: `src/retrieval/retriever.py` convertido de inicialización al importar a inicialización lazy (`_get_collection()` singleton) para evitar crash si vectorstore no existe.
   - **Decisión LLM para grading**: Se eligió modelo local (Ollama Qwen 2.5 3B) sobre APIs externas (Groq, Gemini, Bedrock). Razonamiento: el grading es clasificación binaria (sí/no) con output de 1 token — un modelo local de 3B es suficiente, elimina dependencia de API keys adicionales, rate limits, y latencia de red. Qwen 2.5 3B seleccionado por su superior soporte de español sobre Llama 3.2 3B y Gemma 2 2B.
   - **Requirements**: `langchain-ollama>=0.3.0` añadido a `requirements/app.txt`.

1. **Clasificador ML maduro**: Pipeline completo con **tres experimentos paralelos** (artificial, fusionado, real), `functions.py` unificado, evaluación rigurosa, SHAP, MLflow con experimentos y tags separados por dataset. Punto más fuerte del proyecto.
2. **MLflow integrado de verdad**: Servidor remoto en EC2, autenticación, soporte multi-entorno, `log_mlflow_safe()` resiliente.
3. **Corpus legal EXISTE**: 2.4 MB de chunks en DVC/S3. No hay que crear datos desde cero.
4. **Retriever ChromaDB funcional**: `src/retrieval/retriever.py` en develop con búsqueda por prioridad de fuentes.
5. **Langfuse implementado**: Solo falta merge de la rama.
6. **RAGAS pipeline completo**: 10 preguntas gold, thresholds definidos, modo CI.
7. **IaC completa + CI/CD funcional**: Terraform, Ansible, 3 workflows, Docker, ghcr.io.
8. **Protección anti-leakage documentada** en classifier_2.
3. **Estado actual de ramas remotas**:
   - `origin/chore/langfuse` — Langfuse ya integrado en develop (line 135 de orchestrator/main.py)
   - `origin/feature/rag` — Nodos LangGraph (retrieve, grade, transform, generate) existen pero NO MERGEADOS
   - `origin/feature/model-ml` — Clasificador 3 experimentos ya en develop

4. **RAGAS pipeline** — Existe en repo, pero no se ejecuta automáticamente en CI (solo está en `eval/`).

---

## 4. Fortalezas Técnicas

1. **Clasificador ML maduro**: Pipeline de 1297 líneas en `functions.py`, 3 experimentos paralelos (real, artificial, fusionado), evaluación rigurosa con SHAP, MLflow Model Registry.
2. **MLflow integrado de verdad**: Servidor remoto funcional, `configure_mlflow()` + `log_mlflow_safe()` con fallback resiliente.
3. **Corpus legal EXISTE y es real**: 2.4 MB de chunks DVC-versionados en S3, metadata estructurada (source, file, unit_title, etc.).
4. **ChromaDB retriever funcional**: `src/retrieval/retriever.py` con búsqueda por prioridad de fuentes, `search_tool()` expone API lista para usar.
5. **Langfuse implementado**: Ya en orchestrator, captura session_id + user_id.
6. **RAGAS pipeline completo**: 10 preguntas gold, umbrales definidos, modo CI.
7. **IaC + CI/CD funcionales**: Terraform, Ansible, 3 workflows GitHub Actions, Docker.
8. **Fallback resiliente**: NLP sin spaCy usa regex; Langfuse falla gracefully (line 140-142 orchestrator).
9. **Modelos serializados en disco**: 27 archivos `.joblib` listos para cargar.

| Gap | Acción requerida | Responsable |
|---|---|---|
| **Ramas sin mergear** | Merge chore/langfuse, feature/RAGAS a develop (`feature/model-ml` synced, pendiente PR) | Nati |
| **RAG pipeline stub** | Conectar retriever real + implementar grade + generate con LLM | Dani + Maru |
| **Tools del orquestador hardcodeados** | Conectar a src/rag, src/classifier, src/report reales | Maru |
| **Clasificador no expuesto como servicio** | `predict_risk(text) → dict` con SHAP | Rubén |
| **0 tests** | Mínimo 3 smoke tests | Nati |
---

## 5. Gaps Críticos para la Presentación

### P0 — Bloqueantes (DEMO ROTO SIN ESTO)

| Gap | Ubicación | Acción Requerida | Responsable |
|---|---|---|---|
| ~~**RAG retrieve() NO consulta ChromaDB**~~ | `src/rag/main.py:36-53` | ~~Reemplazar hardcodeado~~ → **HECHO** (Tarea 1.1, 2026-02-24) | Dani + Maru |
| ~~**RAG grade() SIN LLM evaluation**~~ | `src/rag/main.py:59-86` | ~~Implementar con LLM~~ → **HECHO** con Ollama Qwen 2.5 3B (Tarea 1.2, 2026-02-24) | Dani + Maru |
| **RAG generate() SIN LLM synthesis** | `src/rag/main.py:89-96` | Implementar con LLM: sintetizar respuesta con citas legales | Dani + Maru |
| **Tools del orquestador hardcodeados** | `src/orchestrator/main.py:52-101` | Conectar tools a implementaciones reales (src/rag, src/report, src/classifier) | Maru |
| **Clasificador no expuesto al orquestador** | No hay función `predict_risk(text) → dict` | Crear función wrapper que cargue modelo + return (risk_level, shap_explanation) | Rubén |
| **0 tests unitarios** | `tests/` | Mínimo 3 smoke tests (retrieve, classify, generate) | Nati |

### P1 — Importantes (Calidad de presentación)

| Gap | Acción Requerida |
|---|---|
| **Generador de Informes es template estático** | Implementar con LLM (Groq) en `src/report/main.py` |
| **Sin fallback multi-proveedor LLM para generate** | Definir LLM para generate() y posible fallback chain |
| **UI muy básica** | Agregar sidebar con métricas, manejo de errores, streaming responses |
| **Docker no probado end-to-end** | Hacer deploy completo en EC2 con todo conectado |
| **RAGAS no en CI** | Integrar `eval/run_ragas.py` en workflow de GitHub Actions |

### P2 — Deseables (si queda tiempo)

| Gap |
|---|
| Dashboard de métricas Streamlit + MLflow |
| Sistema de feedback de usuario |
| Fine-tuning QLoRA (documentar proceso) |
| Scripts de scraping versionados |
| Cache semántico para queries frecuentes |

---

## 6. Resumen Ejecutivo

**Estado: 75% implementado, integración en progreso.**

### Qué funciona:
- **Clasificador ML**: 100% funcional, 3 experimentos, modelos listos.
- **ChromaDB Retriever**: 100% funcional, busca corpus real, API expuesta, lazy init.
- **RAG retrieve**: 100% funcional, conectado a ChromaDB real.
- **RAG grade**: 100% funcional, usa Ollama Qwen 2.5 3B (LLM local) con fallback a score.
- **Langfuse**: 100% integrado.
- **RAGAS**: 100% pipeline, no en CI.
- **Infra/CI/CD**: 100% funcional.

### Qué NO funciona:
- **RAG generate**: STUB (concatenación estática de citas, sin LLM).
- **Tools del orquestador**: 3 tools devuelven hardcoded strings.
- **Informes**: Template estático, sin LLM.
- **Tests**: 0 tests.

### Acción inmediata más urgente (P0):
1. ~~**Conectar RAG retrieve**~~ → HECHO
2. ~~**Implementar RAG grade con LLM**~~ → HECHO
3. **Implementar RAG generate con LLM** (Tarea 1.3)
4. **Conectar tools**: Hacer que las 3 tools del orquestador invoquen funciones reales
5. **Exponer clasificador**: Función `predict_risk()` con SHAP para orquestador
6. **Escribir 3 smoke tests**: Validar retrieve, classify, generate

**Estimación restante**: ~30 horas (Dani: 9h generate+tests, Maru: 12h orquestador, Rubén: 8h classifier, Nati: 3h tests).

**Plazo**: Sprint 1 en progreso (24 feb - 2 mar). Tareas 1.1 y 1.2 completadas en día 1.

---

## 7. Especificidad Técnica para Cada Gap

### RAG Retrieve — COMPLETADO (2026-02-24)
**Ubicación**: `src/rag/main.py:36-53`

```python
# IMPLEMENTADO
from src.retrieval.retriever import search

def retrieve(query: str, k: int = 5) -> list[dict]:
    results = search(query, k=k, mode="soft")  # ChromaDB real
    return [{"doc": r["text"], "metadata": r.get("metadata", {}),
             "score": max(0.0, 1.0 - r.get("distance", 1.0))} for r in results]
```

### RAG Grade — COMPLETADO (2026-02-24)
**Ubicación**: `src/rag/main.py:59-86`

```python
# IMPLEMENTADO — Ollama Qwen 2.5 3B (local)
def grade(query: str, docs: list[dict], threshold: float = 0.7) -> list[dict]:
    llm = _get_grading_llm()  # ChatOllama(model="qwen2.5:3b")
    for doc in docs:
        response = llm.invoke(GRADING_PROMPT.format(document=doc["doc"], query=query))
        if response.content.strip().lower().startswith("si"):
            relevant.append(doc)
    # Fallback: si Ollama no disponible → _grade_by_score(docs, threshold)
```

**Nota**: La firma cambió de `grade(docs)` a `grade(query, docs)` — el query es necesario para la evaluación contextual con LLM.

### Tools del Orquestador — PENDIENTE
**Ubicación actual**: `src/orchestrator/main.py:52-101`

```python
# PENDIENTE — actualizar llamada a grade() con nueva firma
from src.rag.main import retrieve, grade, generate

@tool
def search_legal_docs(query: str) -> str:
    docs = retrieve(query)         # ChromaDB ✓
    relevant = grade(query, docs)  # Ollama LLM ✓ (nota: query como primer arg)
    result = generate(query, relevant)  # TODO: implementar con LLM
    return result["answer"]
```

---

## 8. Archivo de Auditoría: Módulos Escaneados

| Módulo | Líneas | Clasificación | Notas |
|---|---|---|---|
| `src/rag/main.py` | 115 | PARCIAL | `retrieve()` FUNCIONAL (ChromaDB real), `grade()` FUNCIONAL (Ollama Qwen 2.5 3B), `generate()` STUB |
| `src/orchestrator/main.py` | 172 | PARCIAL | Agente funcional, tools stub |
| `src/classifier/main.py` | 57 | STUB | Wrapper sobre functions.py real |
| `src/classifier/functions.py` | 1297 | FUNCIONAL | Pipeline completo, 2 variantes (real + artificial) |
| `src/retrieval/retriever.py` | 155 | FUNCIONAL | ChromaDB real, 3 modos búsqueda, lazy init |
| `src/report/main.py` | 47 | STUB | Template estático |
| `src/observability/main.py` | 34 | FUNCIONAL | Langfuse v3 integrado |
| `src/agents/state.py` | 34 | FUNCIONAL | TypedDict, estructura lista |
| `app.py` | 42 | FUNCIONAL | Streamlit mínimo |
| `eval/run_ragas.py` | 108 | FUNCIONAL | RAGAS pipeline |
| `eval/helpers.py` | N/A | FUNCIONAL | Helper functions |
| `eval/dataset.json` | 10 Q&A | FUNCIONAL | Gold questions para eval |
| `tests/` | 0 | VACÍO | Sin tests |

---

## 9. Git Status

**Rama actual**: `feature/tools` (Sprint 1 en progreso)
**Commits recientes**:
- `9b6ab077` — Merge PR #43 (refactor/data)
- Pendiente commit: Tareas 1.1 + 1.2 (retrieve + grade funcionales)

**Ramas sin mergear importantes**:
- `origin/feature/rag` — Nodos LangGraph con retrieve, grade, transform, generate
- `origin/chore/langfuse` — Langfuse integrado (YA en develop ahora)
- `origin/feature/model-ml` — Clasificador reestructurado (YA en develop ahora)


---

## 10. Quick Reference: Qué Necesita Cada Miembro del Equipo

### Dani (Data + RAG Engineer) — 35 horas

**RAG Pipeline**
```
SRC:
  - src/rag/main.py → retrieve(), grade(), generate()
  - src/retrieval/retriever.py → search_tool() (YA FUNCIONAL)

WORK:
  1. retrieve() → Llamar a retriever.search_tool() + parsear a list[dict]
  2. grade() → Usar LLM (Groq) para evaluar relevancia docs
  3. generate() → Usar LLM para sintetizar respuesta final
  4. Testear end-to-end con queries reales sobre EU AI Act
```

**Hitos**:
- [ ] retrieve() consulta ChromaDB real (8h)
- [ ] grade() usa LLM (10h)
- [ ] generate() usa LLM + fallback (12h)
- [ ] Integración e2e testeo (5h)

---

### Maru (Agents + UI Lead) — 27 horas

**Orquestador + Tools**
```
SRC:
  - src/orchestrator/main.py → tools (STUB)
  - src/rag/main.py → retrieve, grade, generate (A CONECTAR)
  - src/classifier/functions.py → predict + SHAP (A INTEGRAR)
  - src/report/main.py → generate_report (A CONECTAR)

WORK:
  1. Tool search_legal_docs() → Llamar RAG pipeline real
  2. Tool classify_risk() → Llamar clasificador + SHAP
  3. Tool generate_report() → Llamar report generator
  4. Streaming responses en UI
  5. Error handling graceful
```

**Hitos**:
- [ ] search_legal_docs() funcional (8h)
- [ ] classify_risk() funcional (8h)
- [ ] generate_report() funcional (6h)
- [ ] UI mejorada (5h)

---

### Rubén (ML + Classifier Engineer) — 8 horas

**Exponer Clasificador al Orquestador**
```
SRC:
  - src/classifier/functions.py → preparar_dataset(), evaluar_modelo()
  - src/classifier/classifier_dataset_real/model/ → mejor_modelo.joblib

WORK:
  1. Crear función predict_risk(text: str) → dict:
     {
       "risk_level": "inaceptable|alto|limitado|minimo",
       "confidence": float,
       "shap_explanation": str,  # Top 3 features
       "articles": [...]  # Art. relevantes EU AI Act
     }
  2. Cargar modelo serializado (mejor_modelo.joblib)
  3. Limpiar texto entrada
  4. Extraer features (TF-IDF + manuales)
  5. Predicción + SHAP summary
```

**Hitos**:
- [ ] Función predict_risk() (5h)
- [ ] SHAP explicabilidad integrada (3h)

---

### Nati (MLOps + Observability) — 2 horas

**Tests + RAGAS**
```
SRC:
  - tests/ → CREAR 3 smoke tests
  - eval/run_ragas.py → YA FUNCIONAL, integrar en CI

WORK:
  1. test_retrieve() → Verificar que retrieve devuelve docs de ChromaDB
  2. test_classify() → Verificar que classify devuelve nivel de riesgo válido
  3. test_generate() → Verificar que generate sintetiza respuesta
  4. Integrar eval/run_ragas.py en .github/workflows/
```

**Hitos**:
- [ ] 3 tests básicos (2h)

---

## 11. Matriz de Dependencias

```
┌─────────────────────────────────────────────────────────┐
│  UI (Streamlit)                                         │
│  └─ orchestrator.run(query)                             │
│     └─ ReAct Agent (Bedrock)                            │
│        ├─ @tool search_legal_docs                       │
│        │  └─ rag.retrieve() ✓ (ChromaDB real)           │
│        │     ├─ retriever.search() ✓ (lazy init)        │
│        │  └─ rag.grade() ✓ (Ollama Qwen 2.5 3B)        │
│        │     └─ LLM local (sin API key)                 │
│        │  └─ rag.generate() ◄──── BLOQUEADOR: Dani      │
│        │     └─ LLM (pendiente)                         │
│        │                                                 │
│        ├─ @tool classify_risk ◄── BLOQUEADOR: Maru      │
│        │  └─ classifier.predict_risk() ◄─ BLOQUEADOR: Rubén
│        │     ├─ functions.limpiar_texto() ✓             │
│        │     ├─ functions.crear_features_manuales() ✓   │
│        │     └─ mejor_modelo.joblib ✓                   │
│        │                                                 │
│        └─ @tool generate_report ◄─ BLOQUEADOR: Maru     │
│           └─ report.generate_report() (stub)            │
│              └─ LLM (Groq)                              │
│                                                         │
│ MLflow Tracking ✓                                       │
│ Langfuse Observability ✓                                │
│ DVC Data Versioning ✓                                   │
└─────────────────────────────────────────────────────────┘

✓ = Funcional | ◄─── = Bloqueador | (stub) = A implementar
```

---

## 12. Ejecución Recomendada

**Fase 1 (Dani, paralelo): ~~15 horas~~ → 9 horas restantes**
1. ~~Reemplazar retrieve() con retriever.search()~~ → HECHO (Tarea 1.1)
2. ~~Implementar grade() con LLM~~ → HECHO con Ollama Qwen 2.5 3B (Tarea 1.2)
3. Implementar generate() con LLM (Tarea 1.3)

**Fase 2 (Rubén, paralelo): 8 horas**
1. Crear predict_risk() wrapper
2. Integrar SHAP explicabilidad

El proyecto tiene **más avance del que parece**, pero **disperso en ramas sin mergear**:

- **ML/Clasificador + MLOps + Infra**: maduro y funcional. `functions.py` unificado, 3 experimentos MLflow separados, notebooks con setup robusto (sys.path + os.chdir + MLFLOW override). `feature/model-ml` synced con develop, pendiente PR.
- **Data + Retrieval**: corpus existe en DVC, retriever ChromaDB funciona en develop.
- **Observabilidad + Evaluación**: Langfuse y RAGAS implementados (en branches).
- **RAG + Orquestador + Report**: stubs en develop. Es la conexión que falta.

**Prioridad absoluta:** PR de `feature/model-ml` → mergear chore/langfuse + feature/RAGAS → conectar módulos reales a tools del orquestador → demo end-to-end funcional.
**Fase 3 (Maru, bloqueada por Fases 1+2): 20 horas**
1. Conectar tools del orquestador
2. Mejorar UI (streaming, error handling)
3. Testear end-to-end

**Fase 4 (Nati, final): 2 horas**
1. Escribir 3 smoke tests
2. Integrar RAGAS en CI

**Tiempo total**: ~~45 horas~~ → ~32 horas restantes
**Paralelización potencial**: Fases 1 y 2 en paralelo
**Fecha objetivo**: 2026-03-01 (en track — 2 de 6 tareas P0 completadas en día 1)

