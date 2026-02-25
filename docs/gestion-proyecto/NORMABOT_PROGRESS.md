# NormaBot — Tracking de Progreso

Última actualización: **2026-02-24 (tarde) — PRs #36, #37, #43 mergeadas; Langfuse + RAGAS ya en develop**
Última actualización: 2026-02-24 (Sprint 1 en progreso)

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
| ~21 feb | Clasificador reestructurado | Rubén | Separación `classifier_Dataset_artificial` / `classifier_Dataset_real`. Cambios en functions.py (448 líneas diff). Imágenes SHAP. |
| 2026-02-22 | Diagnóstico técnico | Maru/Claude | `NORMABOT_DIAGNOSIS.md` |
| 2026-02-22 | Roadmap priorizado | Maru/Claude | `NORMABOT_ROADMAP.md` |
| 2026-02-23 | Sistema de tutoría Claude Code | Maru | 6 skills, 2 agents, 3 hooks. `.claude/` configurado para todo el equipo. |
| 2026-02-23 | Plan de 3 semanas (enfoque ReAct) | Maru/Claude | Decisión arquitectónica + sprint plan en `reunion-realineamiento.md` |
| 2026-02-23 | Sync `feature/model-ml` con develop | Rubén | Fetch + rebase local + force-push. Rama actualizada sobre develop. |
| 2026-02-23 | Fix lint ruff (F541, F811) en notebooks fusionado | Rubén | `5_entrenamiento_v2.ipynb` y `7_entrenamiento_v3.ipynb`: eliminados `import os` duplicados y f-string sin placeholder. |
| 2026-02-23 | Unificación de `functions.py` del clasificador | Rubén | **Un único `functions.py`** en `src/classifier/`. Eliminados los 3 archivos duplicados de subcarpetas. Base: versión fusionado (keywords expandidos, `kw_salvaguarda`, `min_df`). |
| 2026-02-23 | Actualización de 33 notebooks (sys.path robusto) | Rubén | Celda de setup en todos los notebooks: búsqueda de `functions.py` en 3 candidatos (raíz proyecto, `..`, `.`). Compatible con VS Code y Jupyter clásico. |
| 2026-02-24 | **Sprint 1 Tarea 1.1**: retrieve() conectado a ChromaDB real | Maru | `src/rag/main.py`: importa `search()` de `src.retrieval.retriever`, convierte formato (`text`/`distance` → `doc`/`score`), error handling graceful. `src/retrieval/retriever.py`: convertido a inicialización lazy (`_get_collection()` singleton). |
| 2026-02-24 | **Sprint 1 Tarea 1.2**: grade() con LLM local (Ollama Qwen 2.5 3B) | Maru | `src/rag/main.py`: evaluación de relevancia documental con LLM local. Prompt sí/no por documento. Fallback doble (Ollama no disponible → score; LLM falla por doc → threshold). Firma cambió: `grade(docs)` → `grade(query, docs)`. `langchain-ollama>=0.3.0` añadido a requirements. |
| 2026-02-24 | Instalación Ollama + modelo Qwen 2.5 3B | Maru | `brew install ollama`, `ollama pull qwen2.5:3b`. Modelo local de 1.9 GB para grading. |
| 2026-02-24 | Sprint Plan detallado creado | Maru | `NORMABOT_SPRINT_PLAN.md`: 3 sprints, tareas asignadas por persona, dependencias mapeadas. |

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
| Merge ramas feature → develop | Todos | Pendiente de reunión | 3 ramas sin mergear: chore/langfuse, feature/RAGAS, feature/rag |
| `predict_risk()` como servicio | Rubén | Tarea 2.1 pendiente | Necesita: cargar joblib, pipeline features, devolver dict con SHAP |
| `src/rag/main.py` — generate() | Dani/Maru | **Tarea 1.3 pendiente** | retrieve() ✓ y grade() ✓ completados. Falta generate() con LLM |
| Conectar tools del orquestador | Maru | **Tareas 3.1-3.3 pendientes** | search_legal_docs bloqueada por Tarea 1.3; classify_risk puede avanzar |
| `src/report/main.py` con LLM | Maru | Stub (Sprint 2) | Necesita LLM integration |
| Tests mínimos | Nati | 0 tests | tests/ vacío — Tarea 4.1 |

## Pendiente (próximos pasos — Semana 1: INTEGRAR, 24 feb - 2 mar)

### Hoy (24 feb) — Siguientes 2 horas

1. **Mergear PR #47** (Rubén, 5 min)
   - Incluye: predict_risk() 174 líneas, thread safety con Lock, SHAP robustness
   - Impacto: desbloquea integración del orquestador

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
- **Días restantes:** 16 (hasta 12 de marzo 2026)
- **Sprint actual:** Sprint 1 — INTEGRAR (24 feb - 2 mar)
- **Tareas Sprint 1 completadas:** 2 de 13 (Tarea 1.1 retrieve + Tarea 1.2 grade)
- **Componentes funcionales:** 7 de 10 (clasificador, MLflow, CI/CD, Docker/IaC, orquestador-con-stubs, RAG retrieve, RAG grade)
- **Componentes parciales (en branches):** 3 (Langfuse, RAGAS, retriever ChromaDB)
- **Componentes stub:** 3 (RAG generate, report, tools del orquestador)
- **LLMs integrados:** Bedrock Nova Lite (orquestador) + Ollama Qwen 2.5 3B (RAG grading)
- **Tests:** 0 archivos de test
- **Coverage estimado:** 0%
- **Ramas activas:** `feature/tools` (Sprint 1 work)
- **Ramas sin mergear:** 3 (chore/langfuse, feature/RAGAS, feature/rag)

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
| 2026-02-22 | Priorizar flujo end-to-end sobre features avanzadas | Sin RAG funcional, el proyecto no se puede demostrar. El clasificador ya está maduro. |
| 2026-02-23 | Usar ReAct Agent existente (no grafo custom) | Menos riesgo, más tiempo para ML+RAG+demo. ReAct es arquitectura agentic legítima. |
| 2026-02-23 | Plan de 3 semanas: Integrar → Pulir → Presentar | Semana 1 merge+conectar, semana 2 tests+métricas+UI, semana 3 presentación. |
| 2026-02-23 | Mantener dos clasificadores como experimentos paralelos | Demuestra rigor experimental (dataset real vs sintético). No son duplicados. |
| 2026-02-24 | Ollama Qwen 2.5 3B para RAG grading (en lugar de Groq API) | El grading es clasificación binaria (sí/no, 1 token output, ~5 llamadas por query). Un modelo local de 3B elimina: (a) API keys adicionales en producción, (b) rate limits, (c) latencia de red. Qwen 2.5 3B elegido sobre Llama 3.2 3B y Gemma 2 2B por mejor soporte de español legal. Validado con 3 docs de prueba (2 legales + 1 irrelevante). |
| 2026-02-24 | `langchain-ollama` en lugar de `langchain-groq` en requirements | Consistente con la decisión de modelo local. Se puede añadir groq/gemini más adelante para generate() si se necesita. |
