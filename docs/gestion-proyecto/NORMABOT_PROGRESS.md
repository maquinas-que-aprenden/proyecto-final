# NormaBot — Tracking de Progreso

Última actualización: 2026-02-23

---

## Completado

| Fecha | Item | Responsable | Notas |
|---|---|---|---|
| Pre-proyecto | Clasificador ML (pipeline completo) | Rubén | Dos experimentos: real y sintético. TF-IDF + features manuales, XGBoost, Grid Search, SHAP, MLflow. |
| Pre-proyecto | NER legal con spaCy | Rubén | Extracción de entidades + resumen por tipo/clase. |
| Pre-proyecto | MLflow tracking remoto | Nati | Servidor en EC2, autenticación, Model Registry. |
| Pre-proyecto | CI/CD (3 workflows) | Nati | PR lint, CI develop, CI/CD main con deploy. |
| Pre-proyecto | IaC (Terraform + Ansible) | Nati | VPC, EC2, S3, IAM, nginx, docker-compose. |
| Pre-proyecto | Orquestador ReAct | Maru | Bedrock Nova Lite, 3 tools (stubs), system prompt. |
| Pre-proyecto | Streamlit UI básica | Maru | Chat conversacional conectado al orquestador. |
| Pre-proyecto | Docker + ghcr.io | Nati | Build, push, deploy automatizado. |
| ~20 feb | Corpus legal chunkeado + DVC | Dani | `chunks_final.jsonl` (2.4 MB) + `chunks_final_all_sources.jsonl` en S3 vía DVC. BOE, EU AI Act, AESIA, LOPD/RGPD. |
| ~20 feb | Notebook de chunking completo | Dani | `src/data/01_chunking_boe_eu_aesia.ipynb`: procesa HTML y PDF, genera chunks con metadata. |
| ~20 feb | Pipeline de retrieval (ChromaDB) | Dani | `src/retrieval/retriever.py` en develop: `search()`, `search_base()`, `search_soft()` con ChromaDB PersistentClient. |
| ~21 feb | Langfuse real implementado | Nati | `src/observability/main.py` en rama `chore/langfuse`: CallbackHandler v3, session_id, user_id, tags. |
| ~21 feb | Orquestador instrumentado con Langfuse | Nati | `src/orchestrator/main.py` en rama `chore/langfuse` con get_langfuse_handler(). |
| ~21 feb | RAGAS pipeline completo | Nati | `eval/run_ragas.py`, `eval/helpers.py`, `eval/dataset.json`. 10 preguntas gold, modo CI, MLflow logging. |
| ~21 feb | Clasificador reestructurado | Rubén | Separación `classifier_Dataset_artificial` / `classifier_Dataset_real`. Cambios en functions.py (448 líneas diff). Imágenes SHAP. |
| 2026-02-22 | Diagnóstico técnico | Maru/Claude | `NORMABOT_DIAGNOSIS.md` |
| 2026-02-22 | Roadmap priorizado | Maru/Claude | `NORMABOT_ROADMAP.md` |
| 2026-02-23 | Sistema de tutoría Claude Code | Maru | 6 skills, 2 agents, 3 hooks. `.claude/` configurado para todo el equipo. |
| 2026-02-23 | Plan de 3 semanas (enfoque ReAct) | Maru/Claude | Decisión arquitectónica + sprint plan en `reunion-realineamiento.md` |

## En Progreso

| Item | Responsable | Estado | Bloqueos |
|---|---|---|---|
| Merge ramas feature → develop | Todos | Pendiente de reunión | 4 ramas sin mergear: chore/langfuse, feature/RAGAS, feature/model-ml, feature/rag |
| `predict_risk()` como servicio | Rubén | En rama, no expuesto | Necesita: cargar joblib, pipeline features, devolver dict con SHAP |
| `src/rag/main.py` real | Dani/Maru | Stub en develop | Dani tiene retriever; falta grade + generate con LLM |
| `src/data/main.py` real | Dani | Stub en develop | Retriever existe en `src/retrieval/retriever.py` pero no está en src/data/main.py |
| Conectar tools del orquestador | Maru | Bloqueada por RAG + classifier | Necesita módulos reales antes |
| `src/report/main.py` con LLM | Maru | Stub | Necesita LLM integration |
| Tests mínimos | Nati | 0 tests | tests/ vacío |

## Pendiente (próximos pasos — Plan de 3 semanas)

### Semana 1: INTEGRAR (24 feb - 2 mar)
1. Mergear TODAS las ramas feature a develop
2. `predict_risk(text) → dict` en src/classifier/main.py
3. Trasladar retriever a src/data/main.py
4. Implementar src/rag/main.py con Corrective RAG real
5. Conectar 3 tools del orquestador a módulos reales
6. Implementar src/report/main.py con LLM
7. Smoke test end-to-end

### Semana 2: PULIR (3 mar - 9 mar)
8. Tests mínimos (3+ tests en tests/)
9. Correr RAGAS eval y documentar métricas
10. Documentar métricas clasificador en MLflow
11. Pulir UI Streamlit
12. Fallback multi-proveedor LLM
13. Docker funcional en EC2
14. Sesión QA

### Semana 3: PRESENTAR (10 mar - 12 mar)
15. Preparar consultas demo
16. Slides: arquitectura, métricas, screenshots
17. Ensayo presentación

## Métricas

- **Días restantes:** 17 (hasta 12 de marzo 2026)
- **Componentes funcionales:** 5 de 10 (clasificador, MLflow, CI/CD, Docker/IaC, orquestador-con-stubs)
- **Componentes parciales (en branches):** 3 (Langfuse, RAGAS, retriever ChromaDB)
- **Componentes stub:** 4 (RAG pipeline, data/main.py, report, tools del orquestador)
- **Tests:** 0 archivos de test
- **Coverage estimado:** 0%
- **Ramas sin mergear:** 4 (chore/langfuse, feature/RAGAS, feature/model-ml, feature/rag)

## Decisiones Tomadas

| Fecha | Decisión | Justificación |
|---|---|---|
| 2026-02-22 | Priorizar flujo end-to-end sobre features avanzadas | Sin RAG funcional, el proyecto no se puede demostrar. El clasificador ya está maduro. |
| 2026-02-23 | Usar ReAct Agent existente (no grafo custom) | Menos riesgo, más tiempo para ML+RAG+demo. ReAct es arquitectura agentic legítima. |
| 2026-02-23 | Plan de 3 semanas: Integrar → Pulir → Presentar | Semana 1 merge+conectar, semana 2 tests+métricas+UI, semana 3 presentación. |
| 2026-02-23 | Mantener dos clasificadores como experimentos paralelos | Demuestra rigor experimental (dataset real vs sintético). No son duplicados. |
