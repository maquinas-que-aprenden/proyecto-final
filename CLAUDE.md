# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NormaBot is an Agentic RAG system for querying Spanish/EU AI regulation (BOE, EU AI Act), classifying AI systems by risk level, and generating deterministic compliance checklists. Deployed on AWS EC2 via Docker.

## Architecture

A **ReAct agent** (LangGraph `create_react_agent`) orchestrates two main tools plus two memory tools:

1. **RAG Normativo** (`src/rag/main.py`) — Corrective RAG: Retrieve → Grade. Uses ChromaDB + `intfloat/multilingual-e5-base` embeddings. `retrieve()` calls `src.retrieval.retriever.search()` (ChromaDB real). `grade()` uses **Ollama Qwen 2.5 3B** (local LLM) for relevance grading with score-based fallback. `format_context()` prepares graded docs for the orchestrator LLM (no separate generation step — the orchestrator generates the final answer). Data pipeline in `data/ingest.py` (raw→chunks) and `data/index.py` (chunks→embeddings→ChromaDB).
2. **Clasificador de Riesgo + Checklist** (`src/classifier/`, `src/checklist/main.py`) — XGBoost classifies AI systems into 4 EU AI Act risk levels (inaceptable, alto, limitado, mínimo). Full ML pipeline in `functions.py`: spaCy text cleaning, TF-IDF + manual keyword features, Grid Search with StratifiedKFold, SHAP explainability, MLflow tracking. Includes deterministic compliance checklist with obligations, SHAP-based recommendations, and borderline detection.

**Orchestrator** (`src/orchestrator/main.py`, 486 lines): ReAct agent using Amazon Bedrock (Nova Lite v1) with tool calling. Four `@tool` functions: `search_legal_docs`, `classify_risk`, `save_user_preference`, `get_user_preferences`. Uses a **side-channel ContextVar** (`_tool_metadata`) to transport verified citations and risk metadata outside the LLM — prevents hallucinated citations. Includes **SQLite checkpointer** for conversation persistence (graceful fallback to MemorySaver) and a **pre-model hook** (`src/memory/hooks`) that trims history to 30K tokens before each LLM call.

**Retriever** (`src/retrieval/retriever.py`): ChromaDB PersistentClient with lazy initialization. `search()` supports `mode="base"` (direct semantic) and `mode="soft"` (source-prioritized). Collection: `normabot_legal_chunks`.

**Entry point**: `app.py` (128 lines) — Streamlit chat UI. Calls `src.orchestrator.main.run(query, session_id, user_id)` which returns `{"messages": [...], "metadata": {...}}`. Renders verified metadata (citations, risk classification) via expanders — sourced from side-channel, not LLM output.

## Source Modules

| Module | Main file | Lines | Purpose |
|--------|-----------|-------|---------|
| `src/rag/` | `main.py` | 175 | Corrective RAG: retrieve + grade + format_context |
| `src/retrieval/` | `retriever.py` | 184 | ChromaDB PersistentClient with lazy init |
| `src/classifier/` | `main.py` | 512 | XGBoost inference + Annex III override + SHAP |
| `src/checklist/` | `main.py` | 469 | Deterministic compliance checklist (no LLM) |
| `src/orchestrator/` | `main.py` | 486 | ReAct agent + SQLite memory + side-channel metadata |
| `src/memory/` | `hooks.py` | 41 | Pre-model hook: trim conversation to 30K tokens |
| `src/observability/` | `langfuse_compat.py` | 25 | Graceful Langfuse degradation (no-op if unavailable) |

## Classifier: Structure

Files under `src/classifier/`:
- **`functions.py`** — ML pipeline library: spaCy text cleaning, TF-IDF, Grid Search, SHAP, MLflow. MLflow experiment: `clasificador_riesgo_dataset_fusionado`.
- **`main.py`** — Inference service: `predict_risk(text) -> dict`. Loads XGBoost + SVD + LabelEncoder from `classifier_dataset_fusionado/model/`. Includes Annex III deterministic override and Langfuse observability.
- **`retrain.py`** — Incremental retraining with augmented data (Annex III examples). Promotes artefacts only if F1-macro improves by ≥ 0.005.
- **`create_normative_features.py`** — Enriches training dataset with 5 binary features (Art. 5 EU AI Act patterns). CLI: `python -m src.classifier.create_normative_features`.
- **`_constants.py`** — Single source of truth for `KEYWORDS_DOMINIO`, `PALABRAS_SUPERVISION`, `STOPWORDS_ES`, `RISK_LABELS`, `LEAKAGE_COLUMNS`. All other modules import from here.
- **`classifier_dataset_real/`** — Experiments on the original hand-labelled real dataset. MLflow experiment: `clasificador_riesgo_dataset_real`.
  - `model/` — Serialized models from experiments
  - `data/finetune/` — `train.jsonl`, `test.jsonl` used for fine-tuning evaluation
- **`classifier_dataset_artificial/`** — Experiments on a purely synthetic dataset. MLflow experiment: `clasificador_riesgo_dataset_artificial`.
  - `model/` — Serialized models from experiments
  - `data/finetune/` — `train.jsonl`, `test.jsonl` used for fine-tuning evaluation
- **`classifier_dataset_fusionado/`** — **Production model.** Experiments on the merged dataset (real + synthetic). MLflow experiment: `clasificador_riesgo_dataset_fusionado`. **Artefacts loaded by `main.py` at runtime.**
  - `model/` — `modelo_xgboost.joblib`, `tfidf_vectorizer.joblib`, `svd_transformer.joblib`, `label_encoder.joblib`, `mejor_modelo_seleccion.json`
  - `data/finetune/` — `train.jsonl`, `test.jsonl`

## Evaluation (RAGAS)

The `eval/` directory contains the RAG evaluation framework:
- **`run_ragas.py`** — Main orchestrator. Two-phase evaluation: Phase A (retriever metrics: context_precision, context_recall ≥ 0.70) and Phase B (E2E: faithfulness ≥ 0.80).
- **`helpers.py`** — Evaluation utilities: retriever invocation, agent response caching per git SHA, MLflow/Langfuse logging, Nova Lite JSON fixup (`_fix_nova_json()`).
- **`dataset.json`** — Test cases with questions, ground_truth, and contexts from EU AI Act.
- CLI: `python eval/run_ragas.py --ci --retriever-only`

## Commands

```bash
# Lint
ruff check .

# Tests
pytest tests/ -v

# Run single test file
pytest tests/test_checklist.py -v

# Run app locally
streamlit run app.py --server.port=8080

# Docker
docker build -t normabot .
docker run -p 8080:8080 --env-file .env normabot

# Docker Compose (local dev with volumes)
docker compose up

# Data pipeline (requires dvc pull first for raw data)
python data/ingest.py                  # raw → chunks JSONL
python data/index.py                   # chunks → embeddings + ChromaDB

# RAGAS evaluation
python eval/run_ragas.py --ci --retriever-only   # Phase A only
python eval/run_ragas.py --ci                     # Phase A + B

# Run individual module (each src module has __main__ block for smoke testing)
python -m src.rag.main
python -m src.classifier.main
python -m src.orchestrator.main

# Install dependencies (split by context)
pip install -r requirements/app.txt        # Streamlit + LangGraph + LangChain
pip install -r requirements/ml.txt         # ML/NLP (spaCy, XGBoost, SHAP, MLflow, torch)
pip install -r requirements/data.txt       # Data pipeline (sentence-transformers, chromadb, bs4, pypdf)
pip install -r requirements/dev.txt        # ruff only
pip install -r requirements/infra.txt      # AWS, DVC, Langfuse, RAGAS
pip install -r requirements/classifier.txt # Classifier-specific dependencies
```

## Tests

| File | Tests | Purpose |
|------|-------|---------|
| `test_checklist.py` | 23 | Deterministic checklist: obligations, recommendations, borderline |
| `test_orchestrator.py` | 24 | Mocked ReAct agent integration tests |
| `test_classifier.py` | ~10 | Smoke tests + ML pipeline validation |
| `test_constants.py` | 4 | Constants module unit tests |
| `test_memory.py` | 2 | Memory hooks (token trimming) |
| `test_retrain.py` | ~10 | Incremental retraining pipeline |
| `conftest.py` | — | Shared fixtures |

To run the full test suite (including ML tests), install ML dependencies first: `pip install -r requirements/ml.txt`. Without these, `test_classifier.py` and `test_retrain.py` will fail with import errors. To run only deterministic tests: `pytest tests/test_checklist.py tests/test_orchestrator.py tests/test_memory.py tests/test_constants.py -v`.

## Conventions

- **Python 3.12**, linter: **ruff**, tests: **pytest**, validation: **Pydantic**
- Code identifiers in English; docstrings and comments in Spanish (legal domain)
- Commits and PRs in Spanish
- Requirements split into `base.txt` (shared pandas/numpy/dotenv), `app.txt`, `ml.txt`, `data.txt`, `dev.txt`, `infra.txt`, `classifier.txt`
- spaCy model: `es_core_news_sm` (loaded lazily via singleton `_get_nlp()` / `_get_nlp_ner()` in `functions.py`)
- Ollama model: `qwen2.5:3b` (loaded lazily via singleton `_get_grading_llm()` in `src/rag/main.py`). Requires Ollama running locally (`brew services start ollama`)
- MLflow: URI via `MLFLOW_TRACKING_URI` env var, password from `MLFLOW_PASSWORD` env var or `.env` in classifier dir

## Infrastructure

- **CI/CD**: GitHub Actions — 5 workflows:
  - `pr_lint.yml` — ruff on changed .py/.ipynb files
  - `ci-develop.yml` — lint → Docker build to ghcr.io :develop
  - `cicd-main.yml` — lint → Docker build → deploy to EC2 via SSH
  - `deploy-manual.yml` — manual deployment trigger
  - `eval.yml` — automated RAGAS evaluation pipeline
- **Docker**: `python:3.12-slim`, port 8080, healthcheck on `/_stcore/health`. Ollama installed in container with SHA256 verification. Entrypoint: `ollama-entrypoint.sh` (starts Ollama + Streamlit). Non-root user (`appuser`).
- **Docker Compose**: `docker-compose.yml` for local dev. Volumes for ChromaDB vectorstore, eval datasets, Ollama model cache, and SQLite conversation memory.
- **IaC**: `infra/terraform/` (VPC, EC2, S3, IAM for Bedrock) + `infra/ansible/` (docker-compose deploy, nginx, MLflow server)
- **DVC**: configured for data versioning; `data/raw/`, `data/processed/vectorstore/` and `data/processed/chunks_legal/*.jsonl` are gitignored. DVC metadata (`.dvc` files) tracked in `data/processed/`.
- **Data directory layout**:
  - `data/ingest.py` — raw→chunks pipeline script
  - `data/index.py` — chunks→embeddings→ChromaDB pipeline script
  - `data/raw/` — original legal documents (DVC-managed)
  - `data/processed/chunks_legal/` — chunked JSONL files (DVC-managed)
  - `data/processed/vectorstore/` — embeddings + ChromaDB (DVC-managed)
  - `data/memory/` — SQLite conversation database (`conversations.db`)
- **Container registry**: `ghcr.io/maquinas-que-aprenden/proyecto-final`
- **Ollama**: Local LLM inference. Used for RAG document grading (Qwen 2.5 3B). Install: `brew install ollama`. Pull model: `ollama pull qwen2.5:3b`. Start: `brew services start ollama`. In Docker: installed in container via `ollama-entrypoint.sh`.
- **CodeRabbit**: configured in `.coderabbit.yaml` — reviews focus only on logic/security/performance bugs, all style linters disabled

## Key Domain Rules

- Every generated response MUST include the disclaimer: *"Informe preliminar generado por IA. Consulte profesional jurídico."*
- Legal citations must be exact (law, article, date). Hallucinated citations are unacceptable — the side-channel ContextVar pattern ensures citations come directly from ChromaDB metadata, not LLM generation.
- Classifier dataset is small (200-300 examples). Always use `class_weight='balanced'` and document as a known limitation.
- LLM stack: Bedrock Nova Lite for orchestrator (also generates RAG answers), **Ollama Qwen 2.5 3B** (local) for RAG document grading. Model selection rationale: grading is a binary classification task (sí/no per document, ~5 calls per query) — a local 3B model avoids API keys, rate limits, and network latency. Qwen 2.5 3B chosen over Llama 3.2 3B and Gemma 2 2B for superior Spanish language support.

## Environment Variables

Required in `.env`:
- `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` — Bedrock access
- `BEDROCK_MODEL_ID` — defaults to `eu.amazon.nova-lite-v1:0`
- `MLFLOW_TRACKING_URI` — defaults to `https://34.244.146.100`
- `MLFLOW_PASSWORD` — MLflow tracking server auth
- `MLFLOW_TRACKING_INSECURE_TLS` — set if using self-signed certs

Optional:
- `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` — Langfuse observability (graceful no-op if missing)
- `LANGFUSE_HOST` — defaults to `https://cloud.langfuse.com`
- `NORMABOT_MEMORY_DIR` — SQLite memory path (defaults to `data/memory`)
- `APP_VERSION` — version tag for Langfuse traces (defaults to `dev`)

## Team

| Member | Role | Areas | GitHub |
|--------|------|-------|--------|
| Dani | Data + RAG Engineer | ChromaDB, embeddings, corpus, RAG pipeline | @danyocando-git |
| Rubén | ML + NLP Engineer | Classifier, spaCy, XGBoost, SHAP, fine-tuning | @Rcerezo-dev |
| Maru | Agents + UI Lead | Orchestrator, Streamlit, integration | @mariaeugenia-alvarez |
| Nati | MLOps + Observability | CI/CD, Langfuse, RAGAS, MLflow, Docker | @natgarea |

## Deadline

**Presentation: March 12, 2026**

## Tutoring System (Claude Code Skills)

This project includes a Claude Code tutoring system to help the team stay focused and deliver a working product. See `AGENTS.md` for full architecture documentation.

### Quick Reference

| Skill | Purpose |
|-------|---------|
| `/tutor` | Main orchestrator — project guidance, priorities, next steps |
| `/diagnostico` | Technical audit of code state (functional vs stub vs empty) |
| `/planificar [fase\|sprint]` | Sprint planning with tasks assigned to team members |
| `/progreso` | Progress tracking — updates NORMABOT_PROGRESS.md |
| `/evaluar` | Self-evaluation against bootcamp rubric |
| `/revisar [archivo\|PR]` | Code review with bootcamp context |

### Project State Files

- `docs/gestion-proyecto/NORMABOT_DIAGNOSIS.md` — Technical audit: what's functional, stub, or empty
- `docs/gestion-proyecto/NORMABOT_ROADMAP.md` — Prioritized roadmap (P0/P1/P2) with effort estimates
- `docs/gestion-proyecto/NORMABOT_PROGRESS.md` — Progress tracking: completed, in-progress, pending
