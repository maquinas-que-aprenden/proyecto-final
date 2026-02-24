# NormaBot — Sprint Plan

Fecha: 2026-02-24 (actualizado 22:00 UTC) | Deadline: 2026-03-12 (16 dias)

---

## Resumen de lo completado (Sprint 1, Dia 1)

8 tareas cerradas en un dia. El flujo end-to-end esta casi completo:

| # | Tarea | Responsable | Estado |
|---|-------|-------------|--------|
| 1.1 | Conectar retriever a ChromaDB real | Dani/Maru | HECHO |
| 1.2 | Implementar grade() con Ollama Qwen 2.5 3B | Dani/Maru | HECHO |
| 1.3 | Implementar generate() con Bedrock Nova Lite | Maru | HECHO |
| 2.1 | predict_risk() con modelo joblib real (F1=0.86) | Maru | HECHO |
| 2.2 | Explicabilidad SHAP integrada (coef lineales) | Maru | HECHO |
| 3.1 | Conectar tool search_legal_docs a RAG real | Maru | HECHO |
| 3.2 | Conectar tool classify_risk a predict_risk() | Maru | HECHO |
| 3.3 | Conectar tool generate_report a classifier+retriever+template | Maru | HECHO |

**Stack funcional**: ChromaDB retrieve → Ollama grade → Bedrock generate → ReAct agent (Bedrock Nova Lite) con 3 tools reales.

---

## Sprint 1 — INTEGRAR (24 feb - 2 mar) — Tareas pendientes

### Dani (Data + RAG) — 1h restante

#### Tarea 1.4: Test e2e del RAG pipeline — Esfuerzo: S (1h)
- Ejecutar 5 queries variadas contra el pipeline completo
- Verificar que las citas son reales (no inventadas)
- Documentar metricas informales (latencia, calidad respuesta)
- **Verificacion**: `python -m src.rag.main`

### Ruben (ML + NLP) — 2h restante

#### Tarea 2.3: Documentar API del clasificador — Esfuerzo: S (2h)
- Agregar docstrings completos a `predict_risk()` — ya tiene docstring basico
- Actualizar `docs/ml/pipeline.md` con la API de servicio
- Verificar que `model_metadata.json` es coherente en las 3 variantes

### Maru (Agents + UI) — 6h restantes

#### Tarea 3.4: Test end-to-end del orquestador — Esfuerzo: M (4h)
- Probar las 3 herramientas via el agente ReAct completo
- Queries de test (ya en `__main__` del orchestrator):
  1. "Que dice el articulo 5 del EU AI Act?" (RAG)
  2. "Clasifica mi sistema de reconocimiento facial" (Clasificador)
  3. "Genera un informe para mi chatbot de atencion al cliente" (Report)
  4. "Clasifica un sistema de scoring crediticio y dime que articulos aplican" (multi-tool)
- Verificar Langfuse captura las trazas
- Fix bugs de integracion

#### Tarea 3.5: Mejorar UI Streamlit — Esfuerzo: S (2h)
- Agregar spinner/loading mientras el agente procesa
- Mejorar sidebar: mostrar tools disponibles, estado del sistema
- Error handling graceful (sin tracebacks en UI)

### Nati (MLOps) — 4h restantes

#### Tarea 4.1: Escribir 3 smoke tests — Esfuerzo: M (3h)
- **Archivo**: `tests/test_smoke.py`
- Tests:
  1. `test_retrieve()`: buscar "EU AI Act", verificar >= 1 resultado con metadata
  2. `test_classify()`: clasificar "sistema de reconocimiento facial", verificar risk_level valido
  3. `test_generate_report()`: verificar que retorna string con disclaimer
- Usar `@pytest.mark.skipif` si falta ChromaDB o modelo joblib

#### Tarea 4.2: Integrar RAGAS en CI — Esfuerzo: S (1h)
- Agregar step en `.github/workflows/ci-develop.yml` que ejecute `eval/run_ragas.py --ci`
- Solo en merges a develop (no en cada PR)

### Criterio de exito del Sprint 1

- [x] `python -m src.classifier.main` clasifica con modelo joblib REAL
- [x] `classify_risk` tool conectada a predict_risk() real
- [x] `generate_report` tool conectada a predict_risk() + retriever + template
- [x] `python -m src.rag.main` devuelve respuestas con citas REALES de ChromaDB
- [x] `search_legal_docs` tool conectada a RAG pipeline real
- [ ] `python -m src.orchestrator.main` ejecuta las 3 tools con implementaciones REALES ← Tarea 3.4
- [ ] `streamlit run app.py` permite hacer preguntas y recibe respuestas reales ← Tarea 3.5
- [ ] `pytest tests/` pasa (minimo 3 tests) ← Tarea 4.1

---

## Sprint 2 — PULIR (3 mar - 9 mar)

### Objetivo

Calidad de presentacion: metricas objetivas, resiliencia, deploy funcional.

#### Maru — Informe con LLM + fallback multi-proveedor (~8h)
- [ ] Implementar `src/report/main.py` con Groq LLM — Esfuerzo: M
- [ ] Fallback multi-proveedor Groq -> Gemini -> Mistral con retry exponential backoff — Esfuerzo: M
- [ ] Streaming responses en Streamlit — Esfuerzo: S

#### Ruben — Documentacion ML + metricas (~4h)
- [ ] Documentar metricas del clasificador final en `docs/ml/metricas.md` — Esfuerzo: S
- [ ] Correr MLflow con metricas actualizadas — Esfuerzo: S
- [ ] Verificar que 3 experimentos estan registrados en MLflow — Esfuerzo: S

#### Nati — Deploy + observabilidad (~8h)
- [ ] Docker build + run local end-to-end — Esfuerzo: M
- [ ] Deploy en EC2 con docker-compose — Esfuerzo: M
- [ ] Verificar Langfuse dashboard con trazas reales — Esfuerzo: S
- [ ] Correr RAGAS eval con RAG real, documentar resultados — Esfuerzo: M

#### Dani — Refinamiento RAG (~4h)
- [ ] Optimizar retrieval (ajustar k, probar modos base vs soft) — Esfuerzo: M
- [ ] Agregar mas fuentes si faltan (LOPD/RGPD, AESIA) — Esfuerzo: S

---

## Sprint 3 — PRESENTAR (10 mar - 12 mar)

### Objetivo

Presentacion lista: demo funcional, slides, ensayo.

#### Todo el equipo
- [ ] Preparar 5 consultas demo que muestren cada tool — Esfuerzo: S
- [ ] Preparar slides: arquitectura, metricas, screenshots, stack — Esfuerzo: M
- [ ] Ensayo de presentacion (minimo 2 pasadas) — Esfuerzo: M
- [ ] Fix de ultimo momento si algo falla en demo — Esfuerzo: S

---

## Sugerencias de mejora — Funcionalidades de alto impacto

Tres ideas para diferenciar NormaBot en la presentacion, priorizando herramientas del bootcamp:

### 1. Dashboard de Explicabilidad ML con Streamlit + SHAP + Plotly

**Impacto**: Demuestra dominio de ML interpretable — tema clave en bootcamps de IA.

Crear una pestaña en Streamlit que, tras cada clasificacion de riesgo, muestre:
- **Waterfall plot SHAP** con las top-10 features que empujaron la prediccion (usando `shap.plots.waterfall` o reconstruccion con Plotly desde los coeficientes lineales que ya tenemos).
- **Force plot interactivo** embebido con `streamlit-shap` o exportado como HTML.
- **Confusion matrix animada** del modelo (datos de evaluacion ya disponibles en MLflow).
- **Comparativa de modelos** en tabla: LogReg vs XGBoost vs variante fusionada, con F1-macro, accuracy, y tiempo de inferencia — datos extraidos de MLflow via API.

**Stack**: SHAP, Plotly, MLflow client, Streamlit tabs, `streamlit-shap`.
**Esfuerzo**: M (4-6h) — los datos ya existen, es pura visualizacion.
**Quien**: Ruben (ML) + Maru (UI).

---

### 2. Evaluacion automatizada RAG con RAGAS + dataset gold + Langfuse traces

**Impacto**: Demuestra rigor en evaluacion de sistemas generativos — muy valorado como practica MLOps.

Construir un pipeline de evaluacion end-to-end:
- **Dataset gold**: 20-30 pares (pregunta, respuesta_esperada, contexto_relevante) sobre el EU AI Act. Archivo JSONL en `data/eval/gold_qa.jsonl`.
- **RAGAS metricas**: faithfulness (no hallucina), answer_relevancy, context_precision, context_recall — ejecutado como script reproducible `eval/run_ragas.py`.
- **Integracion Langfuse**: cada evaluacion se registra como score en Langfuse, visible en dashboard. Usar `langfuse.score()` para anotar las trazas del RAG con metricas RAGAS.
- **CI gate**: si faithfulness < 0.7, el pipeline falla (quality gate automatico en GitHub Actions).
- **Visualizacion**: tabla en Streamlit con resultados de ultima evaluacion (fecha, metricas, # queries, pass/fail).

**Stack**: RAGAS, Langfuse SDK, pytest, GitHub Actions, Streamlit.
**Esfuerzo**: L (8-10h) — requiere crear dataset gold y conectar RAGAS a Langfuse.
**Quien**: Nati (pipeline + CI) + Dani (dataset gold + tuning).

---

### 3. Grafo de agentes visual con LangGraph Studio + multi-step reasoning

**Impacto**: Demuestra el patron agentico avanzado — diferenciador frente a RAGs simples.

Llevar el agente ReAct un paso mas alla:
- **LangGraph Studio**: conectar el grafo del agente a LangGraph Studio (localhost) para visualizar en tiempo real los nodos (reason → tool_call → observe → reason). Captura de pantalla para slides.
- **Multi-step planning**: agregar un nodo `plan` previo al ReAct loop que descomponga consultas complejas. Ejemplo: "Clasifica mi sistema de scoring crediticio, busca los articulos que aplican, y genera un informe" → el planner decide: 1) classify_risk, 2) search_legal_docs, 3) generate_report en secuencia.
- **Memory conversacional**: agregar `MemorySaver` de LangGraph para que el agente recuerde contexto entre turnos. Ejemplo: usuario dice "Clasifica un chatbot", luego "Ahora genera el informe para ese sistema" — el agente recuerda la descripcion.
- **Visualizacion del grafo**: exportar el grafo como Mermaid diagram y renderizar en la sidebar de Streamlit con `st.graphviz_chart` o `streamlit-mermaid`.

**Stack**: LangGraph, LangGraph Studio, MemorySaver (checkpointer), Mermaid, Streamlit.
**Esfuerzo**: M-L (6-8h) — memory es rapido (2h), planner requiere prompt engineering (4h), Studio es config (1h).
**Quien**: Maru (agente) + Nati (Studio/deploy).

---

## Resumen de horas por persona

| Persona | Sprint 1 (restante) | Sprint 2 | Sprint 3 | Sugerencias | Total restante |
|---------|---------------------|----------|----------|-------------|----------------|
| Dani | 1h (1.4) | 4h | 2h | 4h (sug. 2) | 11h |
| Ruben | 2h (2.3) | 4h | 2h | 3h (sug. 1) | 11h |
| Maru | 6h (3.4 + 3.5) | 8h | 4h | 5h (sug. 1+3) | 23h |
| Nati | 4h (4.1 + 4.2) | 8h | 2h | 5h (sug. 2+3) | 19h |
| **Total** | **13h** | **24h** | **10h** | **17h** | **64h** |

> Sprint 1 progreso: 8 tareas completadas, 6 restantes. Velocidad dia 1: excepcional.

---

## Riesgos

| Riesgo | Prob. | Impacto | Mitigacion |
|--------|-------|---------|-----------|
| Groq rate limiting en demo | Alta | Alto | Fallback multi-proveedor (sug. Sprint 2) |
| Ollama no disponible en EC2 | Media | Medio | Fallback a filtro por score en grade() |
| ChromaDB vacio en Docker | Media | Alto | DVC pull en Dockerfile o pre-built image |
| Bedrock no disponible | Baja | Critico | Tener API key Groq de backup |
| Scope creep con sugerencias | Media | Medio | Las 3 sugerencias son independientes — implementar por prioridad, descartar si no da tiempo |
