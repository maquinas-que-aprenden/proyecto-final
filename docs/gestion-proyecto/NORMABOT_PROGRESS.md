# NormaBot — Tracking de Progreso

Última actualización: **2026-02-24 (sesión tracker — post-merge model-ml + refactor/data)**

---

## Completado

| Fecha | Item | Responsable | Notas |
|---|---|---|---|
| Pre-proyecto | Clasificador ML (pipeline completo) | Rubén | Tres experimentos paralelos: artificial, fusionado, real. TF-IDF + features manuales, XGBoost, Grid Search, SHAP, MLflow. |
| Pre-proyecto | NER legal con spaCy | Rubén | Extracción de entidades + resumen por tipo/clase en `functions.py`. |
| Pre-proyecto | MLflow tracking remoto | Nati | Servidor en EC2, autenticación, Model Registry. |
| Pre-proyecto | CI/CD (3 workflows) | Nati | PR lint, CI develop, CI/CD main con deploy a ghcr.io. |
| Pre-proyecto | IaC (Terraform + Ansible) | Nati | VPC, EC2, S3, IAM, nginx, docker-compose, MLflow server. |
| Pre-proyecto | Orquestador ReAct | Maru | Bedrock Nova Lite, system prompt con disclaimer obligatorio. |
| Pre-proyecto | Streamlit UI básica | Maru | Chat conversacional conectado al orquestador. |
| Pre-proyecto | Docker + ghcr.io | Nati | Build, push, deploy automatizado. |
| ~20 feb | Corpus legal chunkeado + DVC | Dani | `chunks_final.jsonl` (2.4 MB) + `chunks_final_all_sources.jsonl` en S3 vía DVC. BOE, EU AI Act, AESIA, LOPD/RGPD. |
| ~20 feb | Notebook de chunking completo | Dani | `src/data/01_chunking_boe_eu_aesia.ipynb`: procesa HTML y PDF, genera chunks con metadata. |
| ~20 feb | Pipeline de retrieval (ChromaDB) | Dani | `src/retrieval/retriever.py` en develop: `search()`, `search_base()`, `search_soft()` con ChromaDB PersistentClient. |
| ~21 feb | Langfuse real implementado | Nati | `src/observability/main.py` en rama `chore/langfuse`: CallbackHandler v3, session_id, user_id, tags. |
| ~21 feb | Orquestador instrumentado con Langfuse | Nati | `src/orchestrator/main.py` en rama `chore/langfuse` con `get_langfuse_handler()`. |
| ~21 feb | RAGAS pipeline completo | Nati | `eval/run_ragas.py`, `eval/helpers.py`, `eval/dataset.json`. 10 preguntas gold, modo CI, MLflow logging. |
| 2026-02-23 | Sync feature/model-ml con develop | Rubén | Fetch + rebase local + force-push. Rama actualizada sobre develop. |
| 2026-02-23 | Fix lint ruff en notebooks clasificador | Rubén | Eliminados `import os` duplicados, f-string sin placeholder, etc. |
| 2026-02-23 | Unificacion functions.py | Rubén | Un único `functions.py` en `src/classifier/`. Eliminados 3 archivos duplicados. Base: fusionado (keywords, `kw_salvaguarda`). |
| 2026-02-23 | Actualizacion 33 notebooks (sys.path robusto) | Rubén | Celda de setup en todos: búsqueda de `functions.py` en 3 candidatos. Compatible VS Code y Jupyter. |
| 2026-02-24 | PR #38 merged: feature/model-ml a develop | Rubén/Maru | Clasificador reestructurado, 3 experimentos, notebooks ejecutados, modelos serializados. |
| 2026-02-24 | predict_risk(text) dict funcional | Rubén | `src/classifier/main.py`: cargar modelo (LogReg+TF-IDF), lazy loading, SHAP top features. Tests OK. |
| 2026-02-24 | PR #43 merged: refactor/data a develop | Dani/Maru | Retriever conectado a RAG con Ollama. Notebooks renumerados, estructura limpia. |
| 2026-02-24 | RAG pipeline semi-real (Ollama) | Maru | `src/rag/main.py`: retrieve→grade→generate con Ollama. Chunking y retrieval tests OK. |

## En Progreso

| Item | Responsable | Estado | Bloqueos |
|---|---|---|---|
| Merge ramas Langfuse + RAGAS a develop | Nati | SIGUIENTE SPRINT | Ninguno, listas para PR |
| src/data/main.py como módulo real | Dani | Migrado de retriever | Exposición uniforme pendiente |
| Tools del orquestador conectados | Maru | En develop | Necesita: RAG real (Ollama), clasificador (OK), report LLM |
| src/report/main.py con LLM | Maru | Stub | Necesita: template + LLM fallback |
| Tests mínimos (pytest) | Nati | 0 tests en tests/ | Bloqueado por completitud RAG |

## Pendiente — Próximos Pasos (Plan 3 semanas revisado)

### Semana 1: INTEGRAR COMPLETAMENTE (24 feb - 2 mar)

P0 Bloqueantes:
1. Merge chore/langfuse + feature/RAGAS a develop (2 PRs, ~30 min)
2. Pruebas end-to-end RAG con Ollama
3. Conectar 3 tools del orquestador a módulos reales
4. Implementar `src/report/main.py` con LLM
5. Smoke test: pregunta → RAG → clasificador → informe

P1 Importantes:
6. Fallback multi-proveedor LLM (Groq → Gemini → Mistral)
7. Pulir UI Streamlit

### Semana 2: TESTS + METRICAS (3 mar - 9 mar)

8. Tests mínimos: 3+ en `tests/`
9. RAGAS eval contra RAG real
10. Documentar métricas clasificador (MLflow)
11. Docker funcional en EC2
12. Sesión QA

### Semana 3: PRESENTAR (10 mar - 12 mar)

13. 5 consultas demo
14. Slides + screenshots
15. Ensayo

## Metricas

- Dias restantes: 16 (hasta 12 mar 2026)
- Componentes funcionales: 8/10 (desde 5/10 ayer)
  - OK Clasificador (serializado, SHAP)
  - OK MLflow
  - OK CI/CD
  - OK Docker/IaC
  - OK Orquestador ReAct
  - OK Corpus legal (DVC+ChromaDB)
  - OK Retriever (Ollama)
  - OK Streamlit UI
- Componentes en progreso: 2 (Langfuse, RAGAS ramas listas)
- Componentes stub: 2 (RAG pipeline Ollama, Report LLM)
- Tests: 0 archivos pytest, smoke tests locales OK
- Coverage estimado: 30%
- PRs mergeadas hoy: 2 (feature/model-ml, refactor/data)
- Ramas esperando merge: 2 (chore/langfuse, feature/RAGAS) + 1 feature/rag-main
- Modelos serializados: LogReg + TF-IDF (85% F1-macro en test)

## Decisiones Tomadas

| Fecha | Decisión | Justificación |
|---|---|---|
| 2026-02-22 | Priorizar end-to-end sobre features avanzadas | Clasificador maduro, pero RAG es core |
| 2026-02-23 | ReAct Agent (no grafo custom) | Menos riesgo, más tiempo para RAG+demo |
| 2026-02-23 | Plan 3 semanas: Integrar→Pulir→Presentar | Distribucion equilibrada |
| 2026-02-23 | 2 clasificadores como experimentos | Rigor experimental: dataset real vs sintético |
| 2026-02-24 | Ollama como fallback RAG | Groq rate-limited. Ollama offline + Groq production |
| 2026-02-24 | Merge inmediato feature/model-ml + refactor/data | Ramas listas, liberan bloqueantes |

## Resumen Ejecutivo

Estado: A 16 dias, proyecto en línea de meta. +3 componentes funcionales hoy.

Lo que cambió:
- 2 PRs mergeadas (feature/model-ml + refactor/data)
- predict_risk() implementado con SHAP
- RAG conectado con Ollama en feature/rag-main
- Clasificador 85% F1-macro, serializado listo

Falta (P0 bloqueantes):
1. Merge 2 ramas (Langfuse, RAGAS) — 30 min
2. Merge feature/rag-main — 15 min
3. Conectar tools orquestador — 2 horas
4. Report + LLM — 1 hora
5. Tests — 1-2 horas

Total esfuerzo: 5-6 horas integración+tests.

Recomendación: Sprint diario (2-3h). Jueves 27 feb: end-to-end funcional. Viernes: tests. Fin de semana+lunes: docs+slides. Mínimo riesgo.
