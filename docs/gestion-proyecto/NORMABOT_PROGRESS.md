# NormaBot — Tracking de Progreso

Última actualización: 2026-02-24 (Sprint 1 en progreso)

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
| Merge ramas feature → develop | Todos | Pendiente de reunión | 3 ramas sin mergear: chore/langfuse, feature/RAGAS, feature/rag |
| `predict_risk()` como servicio | Rubén | Tarea 2.1 pendiente | Necesita: cargar joblib, pipeline features, devolver dict con SHAP |
| `src/rag/main.py` — generate() | Dani/Maru | **Tarea 1.3 pendiente** | retrieve() ✓ y grade() ✓ completados. Falta generate() con LLM |
| Conectar tools del orquestador | Maru | **Tareas 3.1-3.3 pendientes** | search_legal_docs bloqueada por Tarea 1.3; classify_risk puede avanzar |
| `src/report/main.py` con LLM | Maru | Stub (Sprint 2) | Necesita LLM integration |
| Tests mínimos | Nati | 0 tests | tests/ vacío — Tarea 4.1 |

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
| 2026-02-22 | Priorizar flujo end-to-end sobre features avanzadas | Sin RAG funcional, el proyecto no se puede demostrar. El clasificador ya está maduro. |
| 2026-02-23 | Usar ReAct Agent existente (no grafo custom) | Menos riesgo, más tiempo para ML+RAG+demo. ReAct es arquitectura agentic legítima. |
| 2026-02-23 | Plan de 3 semanas: Integrar → Pulir → Presentar | Semana 1 merge+conectar, semana 2 tests+métricas+UI, semana 3 presentación. |
| 2026-02-23 | Mantener dos clasificadores como experimentos paralelos | Demuestra rigor experimental (dataset real vs sintético). No son duplicados. |
| 2026-02-24 | Ollama Qwen 2.5 3B para RAG grading (en lugar de Groq API) | El grading es clasificación binaria (sí/no, 1 token output, ~5 llamadas por query). Un modelo local de 3B elimina: (a) API keys adicionales en producción, (b) rate limits, (c) latencia de red. Qwen 2.5 3B elegido sobre Llama 3.2 3B y Gemma 2 2B por mejor soporte de español legal. Validado con 3 docs de prueba (2 legales + 1 irrelevante). |
| 2026-02-24 | `langchain-ollama` en lugar de `langchain-groq` en requirements | Consistente con la decisión de modelo local. Se puede añadir groq/gemini más adelante para generate() si se necesita. |
