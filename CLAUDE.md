# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NormaBot is an Agentic RAG system for querying Spanish/EU AI regulation (BOE, EU AI Act), classifying AI systems by risk level, and generating compliance reports. Deployed on AWS EC2 via Docker.

## Architecture

A **ReAct agent** (LangGraph `create_react_agent`) orchestrates three tools:

1. **RAG Normativo** (`src/rag/main.py`) — Corrective RAG: Retrieve → Grade → Generate with legal citations. Uses ChromaDB + `paraphrase-multilingual-MiniLM-L12-v2` embeddings.
2. **Clasificador de Riesgo** (`src/classifier/`) — XGBoost classifies AI systems into 4 EU AI Act risk levels (inaceptable, alto, limitado, mínimo). Full ML pipeline in `functions.py`: spaCy text cleaning, TF-IDF + manual keyword features, Grid Search with StratifiedKFold, SHAP explainability, MLflow tracking.
3. **Informes** (`src/report/main.py`) — Generates structured compliance reports with legal citations.

**Orchestrator** (`src/orchestrator/main.py`): ReAct agent using Amazon Bedrock (Nova Lite v1) with tool calling. The LLM decides which tool(s) to invoke based on the user query. The three `@tool` functions are currently stubs returning hardcoded responses — they need to be connected to the real implementations in `src/rag`, `src/classifier`, and `src/report`.

**State** (`src/agents/state.py`): `AgentState` TypedDict with `Annotated[list, operator.add]` for accumulating documents and sources across nodes.

**Entry point**: `app.py` — Streamlit chat UI that calls `src.orchestrator.main.run(query)`.

## Classifier: Two Parallel Experiments

There are two classifier variants under `src/classifier/`:
- **Root level** (`functions.py`, `feature.py`, `main.py`) — trained on real manually-labeled dataset. MLflow experiment: `clasificador_riesgo_ia`.
- **`classifier_2/`** — trained on synthetic/augmented dataset (`eu_ai_act_flagged`). MLflow experiment: `clasificador_riesgo_ia_artificial`. Has extended `preparar_dataset()` supporting `extra_columns` with leakage-safe features.

Both share similar function signatures but differ in: `evaluar_modelo()` (root takes `tfidf` param and transforms internally; `classifier_2` expects pre-transformed features), `preparar_dataset()` (classifier_2 supports `extra_columns` and auto-derives `num_articles`), and `analisis_errores()` (classifier_2 takes separate `X_test_text` param).

## Commands

```bash
# Lint
ruff check .

# Tests (tests/ is currently empty)
pytest tests/ -v

# Run single test file
pytest tests/test_something.py -v

# Run app locally
streamlit run app.py --server.port=8080

# Docker
docker build -t normabot .
docker run -p 8080:8080 --env-file .env normabot

# Run individual module (each src module has __main__ block for smoke testing)
python -m src.rag.main
python -m src.classifier.main
python -m src.orchestrator.main

# Install dependencies (split by context)
pip install -r requirements/app.txt    # Streamlit + LangGraph + LangChain
pip install -r requirements/ml.txt     # ML/NLP (spaCy, XGBoost, SHAP, MLflow, torch)
pip install -r requirements/dev.txt    # ruff only
pip install -r requirements/infra.txt  # AWS, DVC, Langfuse, RAGAS
```

## Conventions

- **Python 3.12**, linter: **ruff**, tests: **pytest**, validation: **Pydantic**
- Code identifiers in English; docstrings and comments in Spanish (legal domain)
- Commits and PRs in Spanish
- Requirements split into `base.txt` (shared pandas/numpy/dotenv), `app.txt`, `ml.txt`, `dev.txt`, `infra.txt`
- spaCy model: `es_core_news_sm` (loaded lazily via singleton `_get_nlp()` / `_get_nlp_ner()` in `functions.py`)
- MLflow: URI via `MLFLOW_TRACKING_URI` env var, password from `MLFLOW_PASSWORD` env var or `.env` in classifier dir

## Infrastructure

- **CI/CD**: GitHub Actions — `pr_lint.yml` (ruff on changed .py/.ipynb files), `ci-develop.yml` (lint → Docker build to ghcr.io :develop), `cicd-main.yml` (lint → Docker build → deploy to EC2 via SSH)
- **Docker**: `python:3.12-slim`, port 8080, healthcheck on `/_stcore/health`
- **IaC**: `infra/terraform/` (VPC, EC2, S3, IAM for Bedrock) + `infra/ansible/` (docker-compose deploy, nginx, MLflow server)
- **DVC**: configured for data versioning; `data/raw/` and `data/processed/` are gitignored
- **Container registry**: `ghcr.io/maquinas-que-aprenden/proyecto-final`
- **CodeRabbit**: configured in `.coderabbit.yaml` — reviews focus only on logic/security/performance bugs, all style linters disabled

## Key Domain Rules

- Every generated response MUST include the disclaimer: *"Informe preliminar generado por IA. Consulte profesional jurídico."*
- Legal citations must be exact (law, article, date). Hallucinated citations are unacceptable.
- Classifier dataset is small (200-300 examples). Always use `class_weight='balanced'` and document as a known limitation.
- LLM: Bedrock Nova Lite for orchestrator. Groq (Llama 3.3 70B) planned for RAG generation, with Gemini → Mistral fallback chain for rate limiting.

## Environment Variables

Required in `.env`:
- `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` — Bedrock access
- `BEDROCK_MODEL_ID` — defaults to `eu.amazon.nova-lite-v1:0`
- `MLFLOW_PASSWORD` — MLflow tracking server auth
- `MLFLOW_TRACKING_URI` — defaults to `https://34.244.146.100`
- `MLFLOW_TRACKING_INSECURE_TLS` — set if using self-signed certs

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
