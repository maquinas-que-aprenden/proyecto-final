# NormaBot — Diagnóstico Técnico

Fecha: 2026-02-23 (actualizado sesión tarde — unificación classifier + sync develop)

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

| Componente | Ubicación | Estado |
|---|---|---|
| **RAG Pipeline** | `src/rag/main.py` (en develop) | Stub. `retrieve()`, `grade()`, `generate()` devuelven datos hardcodeados. |
| **Data ingesta** | `src/data/main.py` (en develop) | Stub. `ingest()` y `search()` simulan indexación. El retriever REAL está en `src/retrieval/retriever.py`. |
| **Generador de Informes** | `src/report/main.py` | Stub. Template string estático, sin LLM. |
| **Tools del orquestador** | `src/orchestrator/main.py` | Stubs. Las 3 herramientas devuelven respuestas hardcodeadas. |

### Componentes VACÍOS

| Componente | Estado |
|---|---|
| `tests/` | Vacío. No hay tests unitarios (RAGAS es evaluación, no tests). |
| `scripts/` | Solo `.gitkeep`. No hay scripts de scraping versionados. |

---

## 2. Stack Tecnológico

| Capa | Tecnología | Estado |
|---|---|---|
| LLM (orquestador) | Amazon Bedrock (Nova Lite v1) | Integrado |
| LLM (RAG generation) | Groq / Gemini / Mistral | No integrado |
| Agentes | LangGraph `create_react_agent` | Funcional (con stubs) |
| Vector store | ChromaDB PersistentClient | En develop (retriever.py), no conectado a RAG |
| Embeddings | paraphrase-multilingual-MiniLM-L12-v2 | En develop (retriever.py) |
| ML | scikit-learn 1.5.2, XGBoost 3.2.0 | Funcional |
| NLP | spaCy 3.8.2 (es_core_news_sm) | Funcional |
| Explicabilidad | SHAP 0.46.0 | Funcional |
| Tracking | MLflow 2.17.2 | Funcional (servidor remoto) |
| UI | Streamlit >=1.40.0 | Funcional |
| Observabilidad | Langfuse (CallbackHandler v3) | En rama chore/langfuse |
| Evaluación RAG | RAGAS >=0.2.0 | En rama feature/RAGAS |
| Data versioning | DVC >=3.50.0 | Funcional con S3 |
| CI/CD | GitHub Actions (3 workflows) | Funcional |
| IaC | Terraform + Ansible | Funcional |

---

## 3. Fortalezas Técnicas

1. **Clasificador ML maduro**: Pipeline completo con **tres experimentos paralelos** (artificial, fusionado, real), `functions.py` unificado, evaluación rigurosa, SHAP, MLflow con experimentos y tags separados por dataset. Punto más fuerte del proyecto.
2. **MLflow integrado de verdad**: Servidor remoto en EC2, autenticación, soporte multi-entorno, `log_mlflow_safe()` resiliente.
3. **Corpus legal EXISTE**: 2.4 MB de chunks en DVC/S3. No hay que crear datos desde cero.
4. **Retriever ChromaDB funcional**: `src/retrieval/retriever.py` en develop con búsqueda por prioridad de fuentes.
5. **Langfuse implementado**: Solo falta merge de la rama.
6. **RAGAS pipeline completo**: 10 preguntas gold, thresholds definidos, modo CI.
7. **IaC completa + CI/CD funcional**: Terraform, Ansible, 3 workflows, Docker, ghcr.io.
8. **Protección anti-leakage documentada** en classifier_2.

---

## 4. Gaps Críticos para la Presentación

### P0 — Bloqueantes (necesarios para demo funcional)

| Gap | Acción requerida | Responsable |
|---|---|---|
| **Ramas sin mergear** | Merge chore/langfuse, feature/RAGAS a develop (`feature/model-ml` synced, pendiente PR) | Nati |
| **RAG pipeline stub** | Conectar retriever real + implementar grade + generate con LLM | Dani + Maru |
| **Tools del orquestador hardcodeados** | Conectar a src/rag, src/classifier, src/report reales | Maru |
| **Clasificador no expuesto como servicio** | `predict_risk(text) → dict` con SHAP | Rubén |
| **0 tests** | Mínimo 3 smoke tests | Nati |

### P1 — Importantes (calidad de presentación)

| Gap | Acción requerida |
|---|---|
| **Informes son template estático** | Implementar con LLM |
| **Sin fallback multi-proveedor** | Cadena Groq → Gemini → Mistral |
| **UI básica** | Sidebar informativo, manejo de errores |
| **Docker no probado con todo conectado** | Deploy end-to-end en EC2 |

### P2 — Deseables (si queda tiempo)

| Gap |
|---|
| Dashboard métricas en Streamlit |
| Sistema de feedback del usuario |
| Fine-tuning QLoRA (documentar proceso) |
| Scripts de scraping versionados |
| Cache semántico |

---

## 5. Resumen Ejecutivo

El proyecto tiene **más avance del que parece**, pero **disperso en ramas sin mergear**:

- **ML/Clasificador + MLOps + Infra**: maduro y funcional. `functions.py` unificado, 3 experimentos MLflow separados, notebooks con setup robusto (sys.path + os.chdir + MLFLOW override). `feature/model-ml` synced con develop, pendiente PR.
- **Data + Retrieval**: corpus existe en DVC, retriever ChromaDB funciona en develop.
- **Observabilidad + Evaluación**: Langfuse y RAGAS implementados (en branches).
- **RAG + Orquestador + Report**: stubs en develop. Es la conexión que falta.

**Prioridad absoluta:** PR de `feature/model-ml` → mergear chore/langfuse + feature/RAGAS → conectar módulos reales a tools del orquestador → demo end-to-end funcional.

**Decisión arquitectónica:** Usar el ReAct Agent existente (`create_react_agent`). No construir grafo custom.
