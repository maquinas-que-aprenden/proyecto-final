# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NormaBot is an Agentic RAG system for querying Spanish/EU AI regulation (BOE, EU AI Act), classifying AI systems by risk level, and generating compliance reports. Deployed on AWS EC2 via Docker.

## Architecture

A **ReAct agent** (LangGraph `create_react_agent`) orchestrates four tools:

1. **RAG Normativo** (`src/rag/main.py`) — Corrective RAG: Retrieve → Grade → Generate with legal citations. Uses ChromaDB + `intfloat/multilingual-e5-base` embeddings. `retrieve()` calls `src.retrieval.retriever.search()` (ChromaDB real). `grade()` uses **Ollama Qwen 2.5 3B** (local LLM) for relevance grading with score-based fallback. `generate()` uses Bedrock Nova Lite with fallback to concatenation summary. Data pipeline in `data/ingest.py` (raw→chunks) and `data/index.py` (chunks→embeddings→ChromaDB).
2. **Clasificador de Riesgo + Checklist** (`src/classifier/`, `src/checklist/main.py`) — XGBoost classifies AI systems into 4 EU AI Act risk levels (inaceptable, alto, limitado, mínimo). Full ML pipeline in `functions.py`: spaCy text cleaning, TF-IDF + manual keyword features, Grid Search with StratifiedKFold, SHAP explainability, MLflow tracking. Annexo III deterministic override (9 regex patterns). Includes deterministic compliance checklist with obligations, SHAP-based recommendations, and borderline detection. Results cached via `lru_cache`.
3. **Guardar preferencias** — `save_user_preference`: stores user preferences/context in an `InMemoryStore` namespaced by `user_id` or `thread_id`.
4. **Recuperar preferencias** — `get_user_preferences`: retrieves stored preferences for personalized responses.

**Orchestrator** (`src/orchestrator/main.py`): ReAct agent using Amazon Bedrock (Nova Lite v1) with tool calling. The LLM decides which tool(s) to invoke based on the user query. The two main `@tool` functions (`search_legal_docs`, `classify_risk`) connect to `src/rag` and `src/classifier`+`src/checklist`. Features:
- **Memory**: SQLite checkpointer (with InMemorySaver fallback) for conversation persistence across turns. `pre_model_hook` from `src/memory/hooks.py` trims messages to stay within LLM context window (30K tokens).
- **Side-channel metadata**: `_tool_metadata` (`ContextVar`) collects verified citations and risk data from tools, passed directly to the UI without LLM reformulation.
- **Thread-safe singletons**: `_get_checkpointer()` and `_get_store()` use double-checked locking.
- **Langfuse observability**: all tools decorated with `@observe`.

**Memory** (`src/memory/hooks.py`): `pre_model_hook` trims conversation history using `trim_messages` (strategy="last", 30K token limit) before sending to LLM, preserving full history in checkpointer.

**Retriever** (`src/retrieval/retriever.py`): ChromaDB PersistentClient with lazy initialization. `search()` supports `mode="base"` (direct semantic) and `mode="soft"` (source-prioritized). `search_tool()` returns LLM-ready formatted string. Collection: `normabot_legal_chunks`.

**Entry point**: `app.py` — Streamlit chat UI with session management (`session_id`, `user_id`), `_render_metadata()` for verified side-channel data (risk classification, legal citations), and `<thinking>` tag stripping.

## Classifier: Two Parallel Experiments

There are two classifier variants under `src/classifier/`:
- **Root level** (`functions.py`, `feature.py`, `main.py`) — trained on real manually-labeled dataset. MLflow experiment: `clasificador_riesgo_ia`.
- **`classifier_2/`** — trained on synthetic/augmented dataset (`eu_ai_act_flagged`). MLflow experiment: `clasificador_riesgo_ia_artificial`. Has extended `preparar_dataset()` supporting `extra_columns` with leakage-safe features.

Both share similar function signatures but differ in: `evaluar_modelo()` (root takes `tfidf` param and transforms internally; `classifier_2` expects pre-transformed features), `preparar_dataset()` (classifier_2 supports `extra_columns` and auto-derives `num_articles`), and `analisis_errores()` (classifier_2 takes separate `X_test_text` param).

## Commands

```bash
# Lint
ruff check .

# Tests (5 suites, ~108 tests)
pytest tests/ -v

# Run single test file
pytest tests/test_something.py -v

# Run app locally
streamlit run app.py --server.port=8080

# Docker
docker build -t normabot .
docker run -p 8080:8080 --env-file .env normabot

# Data pipeline (requires dvc pull first for raw data)
python data/ingest.py                  # raw → chunks JSONL
python data/index.py                   # chunks → embeddings + ChromaDB

# Run individual module (each src module has __main__ block for smoke testing)
python -m src.rag.main
python -m src.classifier.main
python -m src.orchestrator.main

# Install dependencies (split by context)
pip install -r requirements/app.txt    # Streamlit + LangGraph + LangChain
pip install -r requirements/ml.txt     # ML/NLP (spaCy, XGBoost, SHAP, MLflow, torch)
pip install -r requirements/data.txt   # Data pipeline (sentence-transformers, chromadb, bs4, pypdf)
pip install -r requirements/dev.txt    # ruff only
pip install -r requirements/infra.txt  # AWS, DVC, Langfuse, RAGAS
```

## Conventions

- **Python 3.12**, linter: **ruff**, tests: **pytest**, validation: **Pydantic**
- Code identifiers in English; docstrings and comments in Spanish (legal domain)
- Commits and PRs in Spanish
- Requirements split into `base.txt` (shared pandas/numpy/dotenv), `app.txt`, `ml.txt`, `data.txt`, `dev.txt`, `infra.txt`
- spaCy model: `es_core_news_sm` (loaded lazily via singleton `_get_nlp()` / `_get_nlp_ner()` in `functions.py`)
- Ollama model: `qwen2.5:3b` (loaded lazily via singleton `_get_grading_llm()` in `src/rag/main.py`). Requires Ollama running locally (`brew services start ollama`)
- MLflow: URI via `MLFLOW_TRACKING_URI` env var, password from `MLFLOW_PASSWORD` env var or `.env` in classifier dir
- Tests mock external dependencies (Bedrock, Ollama, LangGraph) at `sys.modules` level to avoid needing credentials or services in CI

## Infrastructure

- **CI/CD**: GitHub Actions — `pr_lint.yml` (ruff on changed .py/.ipynb files), `ci-develop.yml` (lint → smoke tests → Docker build to ghcr.io :develop), `cicd-main.yml` (lint → smoke tests → Docker build → deploy to EC2 via SSH), `eval.yml` (RAGAS evaluation on EC2, manual trigger via `workflow_dispatch`)
- **Docker**: `python:3.12-slim`, port 8080, healthcheck on `/_stcore/health`
- **IaC**: `infra/terraform/` (VPC, EC2, S3, IAM for Bedrock) + `infra/ansible/` (docker-compose deploy, nginx, MLflow server)
- **DVC**: configured for data versioning; `data/raw/`, `data/processed/vectorstore/` and `data/processed/chunks_legal/*.jsonl` are gitignored. DVC metadata (`.dvc` files) tracked in `data/processed/`.
- **Data directory layout**:
  - `data/ingest.py` — raw→chunks pipeline script
  - `data/index.py` — chunks→embeddings→ChromaDB pipeline script
  - `data/raw/` — original legal documents (DVC-managed)
  - `data/processed/chunks_legal/` — chunked JSONL files (DVC-managed)
  - `data/processed/vectorstore/` — embeddings + ChromaDB (DVC-managed)
  - `data/eval/` — RAG evaluation results
  - `data/notebooks/` — evaluation notebooks (embeddings tuning, retrieval tests, complex queries)
- **Container registry**: `ghcr.io/maquinas-que-aprenden/proyecto-final`
- **Ollama**: Local LLM inference. Used for RAG document grading (Qwen 2.5 3B). Install: `brew install ollama`. Pull model: `ollama pull qwen2.5:3b`. Start: `brew services start ollama`. In Docker/EC2: needs Ollama sidecar or pre-installed.
- **Langfuse**: v2 (`>=2.7.3,<3.0.0`) for observability. All tools and pipeline functions decorated with `@observe`. `src/observability/main.py` provides `get_langfuse_handler()` for LangChain `CallbackHandler` integration. Disabled in tests via `LANGFUSE_ENABLED=false`. Known limitation: root LangGraph trace via `CallbackHandler` not available due to langchain 0.3 incompatibility; individual tool traces work via `@observe`.
- **CodeRabbit**: configured in `.coderabbit.yaml` — reviews focus only on logic/security/performance bugs, all style linters disabled

## Key Domain Rules

- Every generated response MUST include the disclaimer: *"Informe preliminar generado por IA. Consulte profesional jurídico."*
- Legal citations must be exact (law, article, date). Hallucinated citations are unacceptable.
- Classifier dataset is small (200-300 examples). Always use `class_weight='balanced'` and document as a known limitation.
- LLM stack: Bedrock Nova Lite for orchestrator and RAG generation, **Ollama Qwen 2.5 3B** (local) for RAG document grading. Model selection rationale: grading is a binary classification task (sí/no per document, ~5 calls per query) — a local 3B model avoids API keys, rate limits, and network latency. Qwen 2.5 3B chosen over Llama 3.2 3B and Gemma 2 2B for superior Spanish language support.

## Environment Variables

Required in `.env`:
- `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` — Bedrock access
- `BEDROCK_MODEL_ID` — defaults to `eu.amazon.nova-lite-v1:0`
- `BEDROCK_REGION` — defaults to `AWS_REGION`, then `eu-west-1`
- `MLFLOW_PASSWORD` — MLflow tracking server auth
- `MLFLOW_TRACKING_URI` — defaults to `https://34.244.146.100`
- `MLFLOW_TRACKING_INSECURE_TLS` — set if using self-signed certs
- `NORMABOT_MEMORY_DIR` — defaults to `data/memory` (SQLite conversations DB)
- `LANGFUSE_ENABLED` — set to `false` in tests (via `conftest.py`)
- `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` — Langfuse auth
- `LANGFUSE_HOST` — defaults to `https://cloud.langfuse.com`
- `APP_VERSION` — defaults to `dev` (sent to Langfuse for trace versioning)

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
