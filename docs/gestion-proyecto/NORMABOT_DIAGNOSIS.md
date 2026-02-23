# NormaBot — Diagnóstico Técnico

Fecha: 2026-02-22

---

## 1. Mapa del Estado Actual

### Componentes FUNCIONALES (código real, ejecutable)

| Componente | Ubicación | Estado |
|---|---|---|
| **Clasificador ML (dataset real)** | `src/classifier/functions.py` | Completo. Pipeline end-to-end: limpieza spaCy, TF-IDF, features manuales por keywords de dominio, LogisticRegression baseline, XGBoost, Grid Search con StratifiedKFold, evaluación (confusion matrix, ROC multiclase, análisis de errores), SHAP (beeswarm + waterfall), serialización joblib, MLflow tracking + Model Registry. |
| **Clasificador ML (dataset sintético)** | `src/classifier/classifier_2/functions.py` | Completo. Variante con dataset artificial/aumentado. Añade soporte para `extra_columns` en `preparar_dataset()` con protección anti-leakage documentada, y `evaluar_modelo()` que acepta features pre-transformadas. |
| **NER legal** | `src/classifier/functions.py` → `extraer_entidades()`, `resumen_entidades()` | Funcional. spaCy `es_core_news_sm` con `nlp.pipe` para batch processing. Extrae entidades y genera resúmenes por tipo y clase de riesgo. |
| **Orquestador ReAct** | `src/orchestrator/main.py` | Funcional pero con tools stub. Agente ReAct con Bedrock Nova Lite, system prompt bien diseñado con disclaimer obligatorio. Las 3 herramientas (`search_legal_docs`, `classify_risk`, `generate_report`) devuelven respuestas hardcodeadas. |
| **UI Streamlit** | `app.py` | Funcional. Chat conversacional mínimo conectado al orquestador. Sidebar con info de agentes. |
| **CI/CD** | `.github/workflows/` | Funcional. 3 workflows: PR lint (ruff en archivos cambiados), CI develop (lint + Docker build), CI/CD main (lint + Docker build + deploy EC2 via SSH). |
| **Docker** | `Dockerfile`, `docker-compose.yml` | Funcional. python:3.12-slim, healthcheck en Streamlit, deploy via ghcr.io. |
| **IaC** | `infra/terraform/`, `infra/ansible/` | Funcional. Terraform (VPC, EC2, S3, IAM Bedrock) + Ansible (docker-compose, nginx, MLflow server). |
| **MLflow tracking** | `functions.py` → `configure_mlflow()`, `log_mlflow_safe()` | Funcional. Servidor remoto en EC2 (https://34.244.146.100), autenticación por password, soporte Colab/local/.env. |
| **DVC** | `.dvc/`, `.dvcignore` | Configurado. Directorios `data/raw/` y `data/processed/` en gitignore. |

### Componentes STUB (placeholder, no implementados)

| Componente | Ubicación | Estado |
|---|---|---|
| **RAG Pipeline** | `src/rag/main.py` | Stub. `retrieve()`, `grade()`, `generate()` devuelven datos hardcodeados. No hay ChromaDB, no hay embeddings, no hay conexión LLM. |
| **ChromaDB + Embeddings** | `src/data/main.py` | Stub. `ingest()` y `search()` simulan indexación y búsqueda. Sin sentence-transformers, sin ChromaDB real. |
| **Generador de Informes** | `src/report/main.py` | Stub. Template string estático, sin llamada a LLM. |
| **Observabilidad** | `src/observability/main.py` | Stub. `create_trace()` devuelve datos simulados. Sin Langfuse real. |
| **UI legacy** | `src/ui/main.py` | Stub de consola. Obsoleto (reemplazado por `app.py`). |
| **Feature extraction standalone** | `src/classifier/feature.py` | Stub. Funciones simuladas de TF-IDF, features manuales y NER. La implementación real está en `functions.py`. |
| **MLflow stubs** | `src/classifier/mlflow_stub.py`, `classifier_2/mlflow_stub.py` | Stubs. La implementación real de MLflow está en los `functions.py` respectivos. |

### Componentes VACÍOS

| Componente | Estado |
|---|---|
| `tests/` | Vacío. No hay ni un solo test. |
| `eval/` | Solo `.gitkeep`. No hay evaluación RAGAS/DeepEval implementada. |
| `scripts/` | Solo `.gitkeep`. No hay scripts de scraping BOE ni ETL. |
| `data/` | Solo `.gitkeep`. Sin corpus legal indexado en el repo (probablemente en DVC/drive). |

---

## 2. Stack Tecnológico Identificado

| Capa | Tecnología | Versión | Estado |
|---|---|---|---|
| LLM (orquestador) | Amazon Bedrock (Nova Lite v1) | via langchain-aws | Integrado |
| LLM (RAG generation) | Groq / Gemini / Mistral | — | No integrado |
| Agentes | LangGraph + LangChain | >=0.2.0 / >=0.3.0 | `create_react_agent` funcional |
| Vector store | ChromaDB | — | No integrado (stub) |
| Embeddings | sentence-transformers | — | No integrado (stub) |
| ML | scikit-learn 1.5.2, XGBoost 3.2.0 | Pinned | Funcional |
| NLP | spaCy 3.8.2 (`es_core_news_sm`) | Pinned | Funcional |
| Explicabilidad | SHAP 0.46.0 | Pinned | Funcional |
| Tracking | MLflow 2.17.2 | Pinned | Funcional (servidor remoto) |
| Fine-tuning | torch, transformers, peft, trl, bitsandbytes | Pinned | En requirements, no hay código |
| UI | Streamlit >=1.40.0 | — | Funcional |
| CI/CD | GitHub Actions | — | Funcional |
| IaC | Terraform + Ansible | — | Funcional |
| Observabilidad | Langfuse >=2.50.0 | En requirements/infra | Solo stub |
| Evaluación RAG | RAGAS >=0.2.0 | En requirements/infra | No implementado |
| Data versioning | DVC >=3.50.0 | En requirements/infra | Configurado |

---

## 3. Fortalezas Técnicas

1. **Clasificador ML maduro**: Pipeline completo de producción con dos experimentos paralelos (real vs sintético), pipeline de features bien pensado (TF-IDF + keywords de dominio), evaluación rigurosa (CV, ROC multiclase, análisis de errores), explicabilidad SHAP con manejo robusto de formatos sparse/dense y protección OOM. Esto es el punto más fuerte del proyecto.

2. **MLflow integrado de verdad**: No es un stub — hay servidor remoto desplegado en EC2, autenticación, soporte multi-entorno (Colab/local/.env), `log_mlflow_safe()` como wrapper resiliente, y `registrar_modelo_en_registry()` para promotion a Production. Demuestra MLOps real.

3. **Protección anti-leakage documentada**: `classifier_2/functions.py` documenta explícitamente qué columnas tienen leakage y por qué (`violation`, `severity`, `ambiguity`, `explanation`, `split`). Esto demuestra rigor metodológico.

4. **IaC completa**: Terraform + Ansible para provisionar y desplegar toda la infra. No es un "deploy manual por SSH" — hay reproducibilidad real.

5. **CI/CD funcional con 3 pipelines**: Lint incremental en PRs, build en develop, full CI/CD con deploy en main. Flujo de trabajo profesional.

6. **Diseño del orquestador**: El system prompt de NormaBot es sólido (responde en idioma del usuario, cita fuentes, disclaimer obligatorio). La arquitectura ReAct con tool calling es correcta y extensible.

7. **Gestión de dependencias limpia**: Split en 5 archivos de requirements por contexto. CVE-2024-11392/11393/11394 mitigado con `transformers>=4.48.0`.

---

## 4. Gaps Críticos para la Presentación

### P0 — Bloqueantes (el proyecto no funciona end-to-end sin estos)

| Gap | Impacto | Detalle |
|---|---|---|
| **RAG pipeline no implementado** | El agente principal no puede responder preguntas legales reales | `src/rag/main.py` es un stub. Necesita: ChromaDB real, embeddings con sentence-transformers, ingesta del corpus legal, grading (filtro determinista + LLM judge), y generación con Groq/Bedrock. |
| **ChromaDB + Embeddings no implementados** | Sin vector store no hay retrieval | `src/data/main.py` es un stub. Necesita: `SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')`, `chromadb.PersistentClient`, ingesta de documentos chunkeados. |
| **Tools del orquestador no conectados** | El ReAct agent llama stubs, no los módulos reales | `search_legal_docs`, `classify_risk`, `generate_report` en `orchestrator/main.py` deben importar y llamar a las implementaciones en `src/rag`, `src/classifier`, `src/report`. |
| **No hay corpus legal ingestado** | Sin datos no hay RAG | `data/` está vacío. Necesita artículos del BOE/EU AI Act chunkeados con metadata (ley, artículo, fecha). |
| **No hay tests** | Riesgo de regresiones; el CI tiene tests comentados | `tests/` vacío. Mínimo: test del clasificador, test del RAG pipeline, test del orquestador. |

### P1 — Importantes (afectan calidad de la presentación)

| Gap | Impacto |
|---|---|
| **Generador de informes es un template estático** | No usa LLM; no personaliza por caso real. |
| **Observabilidad solo stub** | Langfuse está en requirements pero no integrado. Sin trazas reales de las llamadas LLM. |
| **Evaluación RAGAS no implementada** | `eval/` vacío. Sin métricas objetivas de calidad del RAG (faithfulness, relevance). |
| **Sin fallback multi-proveedor** | El orquestador solo usa Bedrock. No hay cadena Groq → Gemini → Mistral. |
| **Clasificador no integrado en el flujo** | `functions.py` funciona como biblioteca para notebooks, pero no está expuesto como servicio que el orquestador pueda llamar con un texto arbitrario. |

### P2 — Deseables (diferencian el proyecto)

| Gap | Impacto |
|---|---|
| **Fine-tuning QLoRA sin código** | Dependencias en `ml.txt` pero no hay scripts ni notebooks de fine-tuning en el repo. |
| **Sin scripts de scraping** | `scripts/` vacío. El scraping del BOE no está versionado. |
| **EvidentlyAI no integrado** | Mencionado en CLAUDE.md original pero sin código ni dependencia. |
| **Sin Corrective RAG completo** | El diseño describe self-reflection y web fallback, pero ni siquiera el retrieve básico existe. |
| **`src/ui/main.py` obsoleto** | Stub de consola que debería eliminarse (ya existe `app.py`). |

---

## 5. Resumen Ejecutivo

El proyecto tiene **dos zonas de madurez muy diferentes**:

- **ML/Clasificador + MLOps + Infra**: maduro, funcional, bien diseñado. Demuestra competencia real en ML supervisado, NLP, MLOps y DevOps.
- **RAG + Agentes + Observabilidad**: solo stubs y scaffolding. La funcionalidad core del producto (consultar normativa legal) no funciona.

**Para la presentación, la prioridad absoluta es cerrar el flujo end-to-end**: ingestar corpus → ChromaDB → RAG pipeline → conectar tools del orquestador → que un usuario pueda hacer una pregunta legal y recibir una respuesta real con citas.
