# NormaBot — Sistema Agentic RAG para Regulación de IA

NormaBot es un sistema inteligente que consulta normativa española y europea sobre Inteligencia Artificial (BOE, EU AI Act), clasifica sistemas de IA por nivel de riesgo y genera checklists de cumplimiento. Combina un agente ReAct, RAG correctivo con grading local, un clasificador ML con explicabilidad SHAP y un checklist determinista — todo orquestado por un único agente conversacional.

> Proyecto final del Bootcamp de ML/IA — Marzo 2026

---

## Arquitectura

![Arquitectura NormaBot](docs/especs-normabot/normabot-architecture%20final.png)

El sistema sigue una arquitectura **Agentic RAG** con un agente ReAct (LangGraph) como orquestador central:

1. **Pipeline de datos**: Fuentes legales (BOE, EU AI Act) → chunking estructurado → embeddings multilingües → ChromaDB
2. **Agente ReAct** (Amazon Bedrock Nova Lite): decide qué herramienta invocar según la consulta del usuario
3. **Herramientas**:
   - `search_legal_docs` — RAG correctivo: recupera documentos de ChromaDB y los evalúa con un LLM local
   - `classify_risk` — Clasificación de riesgo con XGBoost + checklist de cumplimiento determinista
   - `save/get_user_preferences` — Memoria conversacional persistente (SQLite)
4. **UI Streamlit**: Chat conversacional con metadatos verificados (citas legales, nivel de riesgo)

---

## Características principales

- **Consultas legales con citas verificadas** — Las citas provienen directamente de ChromaDB (side-channel), no del LLM, eliminando alucinaciones en referencias legales
- **Clasificación de riesgo EU AI Act** — 4 niveles (inaceptable, alto, limitado, mínimo) con override determinista del Anexo III para garantizar correctitud legal
- **Checklist de cumplimiento** — Obligaciones, recomendaciones basadas en SHAP y detección de casos borderline, 100% determinista (sin LLM)
- **Grading local** — Ollama Qwen 2.5 3B evalúa relevancia de documentos sin depender de APIs externas
- **Memoria conversacional** — Persistencia en SQLite con trimming automático a 30K tokens
- **Observabilidad opcional** — Langfuse integrado con degradación graceful (funciona con o sin API keys)
- **Evaluación RAGAS** — Pipeline automatizado de evaluación del RAG en dos fases (retriever + E2E)

---

## Tech Stack

| Capa | Tecnología |
|------|-----------|
| Orquestador | LangGraph ReAct Agent + Amazon Bedrock (Nova Lite v1) |
| RAG | ChromaDB + `intfloat/multilingual-e5-base` + Ollama Qwen 2.5 3B |
| Clasificador ML | XGBoost + spaCy + TF-IDF/SVD + SHAP |
| UI | Streamlit |
| Observabilidad | Langfuse + MLflow |
| Evaluación | RAGAS (context precision/recall, faithfulness) |
| Infra | Docker + Terraform + Ansible + GitHub Actions (CI/CD) |
| Datos | DVC + S3 |

---

## Quick Start

### Opción 1: Local

```bash
# Clonar e instalar dependencias
git clone https://github.com/maquinas-que-aprenden/proyecto-final.git
cd proyecto-final
pip install -r requirements/app.txt -r requirements/data.txt

# Descargar datos (requiere acceso DVC/S3)
dvc pull

# Iniciar Ollama (necesario para grading)
# macOS:
brew install ollama && ollama pull qwen2.5:3b && brew services start ollama
# Linux: curl -fsSL https://ollama.com/install.sh | sh && ollama pull qwen2.5:3b && ollama serve &
# En Docker, Ollama se instala automáticamente (ver Dockerfile)

# Configurar variables de entorno
cp .env.example .env  # editar con credenciales AWS

# Ejecutar
streamlit run app.py --server.port=8080
```

### Opción 2: Docker

```bash
docker compose up
```

---

## Estructura del repositorio

```
├── app.py                      # Entry point — Streamlit UI
├── src/
│   ├── orchestrator/           # Agente ReAct + memoria + side-channel
│   ├── rag/                    # RAG correctivo: retrieve → grade → format
│   ├── retrieval/              # ChromaDB PersistentClient
│   ├── classifier/             # XGBoost + Annex III override + SHAP
│   ├── checklist/              # Checklist determinista de cumplimiento
│   ├── memory/                 # Pre-model hook (token trimming)
│   └── observability/          # Langfuse con degradación graceful
├── data/
│   ├── ingest.py               # Pipeline: documentos raw → chunks JSONL
│   ├── index.py                # Pipeline: chunks → embeddings → ChromaDB
│   ├── raw/                    # Corpus legal (DVC)
│   └── processed/              # Chunks, vectorstore, memoria (DVC)
├── eval/                       # RAGAS: run_ragas.py + dataset.json
├── tests/                      # 53+ tests (pytest)
├── infra/
│   ├── terraform/              # IaC: VPC, EC2, S3, IAM
│   └── ansible/                # Playbooks: deploy, nginx, MLflow
├── .github/workflows/          # 5 workflows CI/CD
├── Dockerfile                  # python:3.12-slim + Ollama sidecar
└── docker-compose.yml          # Dev local con volúmenes persistentes
```

---

## Métricas

| Componente | Métrica | Valor |
|-----------|---------|-------|
| Clasificador (XGBoost) | F1-macro | 0.88 |
| Clasificador | Dataset | ~600 ejemplos (real [`EU-AI-Act-Flagged`](https://huggingface.co/datasets/suhas-km/EU-AI-Act-Flagged) + sintético fusionado) |
| RAG (RAGAS) | Faithfulness | ≥ 0.80 (umbral) |
| RAG (RAGAS) | Context precision | (umbral ≥ 0.70) |
| RAG (RAGAS) | Context recall | 0.44–0.52 (umbral ≥ 0.70) |
| Tests | Automatizados | 53+ deterministas, ~73+ total con ML deps |
| CI/CD | Workflows | 5 (lint, build, deploy, eval, manual) |

---

## Decisiones técnicas relevantes

| Decisión | Justificación |
|----------|--------------|
| **Ollama local para grading** (vs API externa) | El grading es una tarea binaria (sí/no) con ~5 llamadas por query. Un modelo local 3B evita latencia de red, rate limits y costes. Qwen 2.5 3B elegido por mejor soporte de español vs Llama 3.2 3B y Gemma 2 2B. |
| **Checklist determinista** (vs generar con LLM) | El módulo de report original hacía una segunda llamada a Bedrock, duplicando la llamada al clasificador. Reemplazado por lógica pura que mapea obligaciones EU AI Act sin intervención del LLM (~500ms menos de latencia). |
| **Side-channel para citas** (vs confiar en el LLM) | Las citas legales se transportan fuera del LLM mediante ContextVar. El LLM genera la respuesta narrativa, pero las referencias a artículos provienen directamente de ChromaDB — imposible que alucine una cita. |
| **XGBoost + override Anexo III** (vs solo ML) | El dataset es limitado (~600 ejemplos) y el dominio legal exige exactitud. Un override determinista con regex del Art. 5 y Anexo III garantiza clasificación correcta en casos claros; el ML cubre los casos ambiguos. |
| **Graceful degradation** | Langfuse, MLflow y Ollama son opcionales en runtime. El sistema funciona en modo degradado sin observabilidad ni grading LLM (fallback a score semántico). |

---

## Limitaciones conocidas

- **Dataset limitado** (~600 ejemplos) — Mitigado con `class_weight='balanced'`, StratifiedKFold y override determinista. Documentado como limitación inherente al dominio legal especializado.
- **ML clásico insuficiente para dominio legal** — TF-IDF + XGBoost no captura relaciones semánticas complejas del lenguaje jurídico. Mejora futura: modelos basados en transformers (BERT/RoBERTa fine-tuneado) para mejor comprensión contextual.
- **Context recall RAGAS** — Por debajo del umbral (0.44-0.52 vs 0.70 objetivo). El retriever no recupera todos los documentos relevantes; mejora futura: aumentar K, ajustar chunking o ampliar dataset de evaluación.
- **Evaluación RAGAS con Nova Lite** — El LLM evaluador (Bedrock Nova Lite) tiene incompatibilidades con el formato JSON que espera RAGAS, lo que impide calcular faithfulness de forma fiable. Mejora futura: usar un modelo compatible (e.g. GPT-4o, Claude) como LLM evaluador.
- **Dependencia de Ollama** — El grading local requiere Ollama corriendo. En caso de fallo, el sistema continúa con fallback por score semántico (sin grading LLM).
- **Corpus centrado en regulación de IA** — Cubre EU AI Act, BOE, normativa AESIA y RGPD/LOPDGDD. La extensión a sector financiero y otras normativas sectoriales queda como mejora futura.

---

## Tests

```bash
# Ejecutar todos los tests
pytest tests/ -v

# Solo tests deterministas (sin dependencias ML)
pytest tests/test_checklist.py tests/test_orchestrator.py tests/test_memory.py -v
```

| Archivo | Tests | Qué cubre |
|---------|-------|-----------|
| `test_checklist.py` | 23 | Obligaciones, recomendaciones SHAP, borderline |
| `test_orchestrator.py` | 24 | Agente ReAct mockeado, tool routing, metadata |
| `test_classifier.py` | ~10 | Pipeline ML, predicción, SHAP |
| `test_constants.py` | 4 | Constantes y keywords |
| `test_memory.py` | 2 | Token trimming hooks |
| `test_retrain.py` | ~10 | Reentrenamiento incremental |

---

## Despliegue

El proyecto se despliega automáticamente en AWS EC2 al mergear a `main`:

1. GitHub Actions ejecuta lint + tests
2. Construye imagen Docker y la sube a `ghcr.io/maquinas-que-aprenden/proyecto-final`
3. Conecta por SSH a EC2 y actualiza el contenedor

Infraestructura provisionada con Terraform (VPC, EC2, S3, IAM) y configurada con Ansible (docker-compose, nginx, MLflow).

---

## Equipo

| Miembro | Rol | Áreas |
|---------|-----|-------|
| Dani | Data + RAG Engineer | ChromaDB, embeddings, corpus legal, pipeline de datos |
| Rubén | ML + NLP Engineer | Clasificador, spaCy, XGBoost, SHAP, fine-tuning |
| Maru | Agents + UI Lead | Orquestador ReAct, Streamlit, integración |
| Nati | MLOps + Observabilidad | CI/CD, Langfuse, RAGAS, MLflow, Docker, Terraform |

---

*Informe preliminar generado por IA. Consulte profesional jurídico.*
