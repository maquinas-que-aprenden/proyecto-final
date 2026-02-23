# NormaBot — Tracking de Progreso

Última actualización: 2026-02-22

---

## Completado

| Fecha | Item | Notas |
|---|---|---|
| Pre-proyecto | Clasificador ML (pipeline completo) | Dos experimentos: real y sintético. TF-IDF + features manuales, XGBoost, Grid Search, SHAP, MLflow. |
| Pre-proyecto | NER legal con spaCy | Extracción de entidades + resumen por tipo/clase. |
| Pre-proyecto | MLflow tracking remoto | Servidor en EC2, autenticación, Model Registry. |
| Pre-proyecto | CI/CD (3 workflows) | PR lint, CI develop, CI/CD main con deploy. |
| Pre-proyecto | IaC (Terraform + Ansible) | VPC, EC2, S3, IAM, nginx, docker-compose. |
| Pre-proyecto | Orquestador ReAct | Bedrock Nova Lite, 3 tools (stubs), system prompt. |
| Pre-proyecto | Streamlit UI básica | Chat conversacional conectado al orquestador. |
| Pre-proyecto | Docker + ghcr.io | Build, push, deploy automatizado. |
| 2026-02-22 | Diagnóstico técnico | `NORMABOT_DIAGNOSIS.md` |
| 2026-02-22 | Roadmap priorizado | `NORMABOT_ROADMAP.md` |

## En Progreso

| Item | Responsable | Estado |
|---|---|---|
| — | — | — |

## Pendiente (próximos pasos)

1. ChromaDB + Embeddings (`src/data/main.py`)
2. RAG Pipeline real (`src/rag/main.py`)
3. Conectar tools del orquestador
4. Clasificador como servicio (predict desde joblib)
5. Generador de informes con LLM
6. Tests mínimos
7. Evaluación RAGAS
8. Langfuse (observabilidad)

## Decisiones Tomadas

| Fecha | Decisión | Justificación |
|---|---|---|
| 2026-02-22 | Priorizar flujo end-to-end sobre features avanzadas | Sin RAG funcional, el proyecto no se puede demostrar. El clasificador ya está maduro. |
