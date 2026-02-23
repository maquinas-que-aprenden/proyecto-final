# Reunión de Realineamiento — NormaBot

**Fecha:** [próxima reunión disponible]
**Duración:** 30-40 minutos
**Objetivo:** Reconocer los avances recientes, identificar qué falta para cerrar el flujo end-to-end, y asignar tareas concretas para los 17 días restantes (12 de marzo).

---

## DECISIÓN ARQUITECTÓNICA: Enfoque ReAct (Enfoque A)

> **Decisión:** Usar el `create_react_agent` existente como orquestador final.
> No construir un grafo LangGraph custom con StateGraph.
>
> **Justificación:**
> - Ya funciona (solo faltan las conexiones reales)
> - Es arquitectura agentic legítima (ReAct es state-of-the-art)
> - Permite dedicar el 80% del tiempo a ML + RAG + demo, no a fontanería
> - Para un bootcamp, lo que importa es: demo funcional > arquitectura elegante
>
> **Lo que esto significa:** Conectar los módulos reales a los 3 tools stub del
> orquestador. No reescribir el orquestador.

---

## Plan de 3 Semanas (17 días hasta presentación)

### Semana 1 (días 1-7): INTEGRAR — Merge + Conectar

**Objetivo:** Todo el código existente en una sola rama, tools conectados a código real.

| Día | Persona | Tarea | Entregable |
|-----|---------|-------|------------|
| 1-2 | **Nati** | Crear PR chore/langfuse → develop, merge | Langfuse real en develop |
| 1-2 | **Nati** | Crear PR feature/RAGAS → develop, merge | eval/ funcional en develop |
| 1-2 | **Rubén** | Crear PR feature/model-ml → develop, merge | Clasificador reestructurado en develop |
| 1-3 | **Rubén** | Crear `predict_risk(text) → dict` en src/classifier/main.py | Clasificador como servicio (carga joblib, pipeline features, SHAP) |
| 1-3 | **Dani** | Trasladar retriever de notebook a src/data/main.py | `search(query) → List[Dict]` usando ChromaDB real + corpus DVC |
| 3-5 | **Dani** | Implementar src/rag/main.py con Corrective RAG | `retrieve()` → `grade()` → `generate()` conectados a ChromaDB real |
| 4-6 | **Maru** | Conectar los 3 tools del orquestador a módulos reales | search_legal_docs → src/rag, classify_risk → src/classifier, generate_report → src/report |
| 5-7 | **Maru** | Implementar src/report/main.py con LLM | Informe personalizado basado en clasificación + RAG |
| 6-7 | **Todos** | Smoke test end-to-end: pregunta → respuesta real | Demo funcional mínima |

### Semana 2 (días 8-14): PULIR — Tests + Métricas + UI

**Objetivo:** Tests, métricas documentadas, UI presentable.

| Día | Persona | Tarea | Entregable |
|-----|---------|-------|------------|
| 8-9 | **Nati** | Tests mínimos: smoke test orquestador, test clasificador, test RAG | Al menos 3 tests en tests/ |
| 8-9 | **Nati** | Correr RAGAS eval y documentar métricas | Resultados en eval/ + MLflow |
| 8-10 | **Rubén** | Documentar métricas del clasificador (F1, confusion matrix) | Métricas reales en MLflow |
| 8-10 | **Dani** | Verificar corpus completo en ChromaDB (cobertura de artículos) | Estadísticas: N chunks, N artículos, N leyes |
| 10-12 | **Maru** | Pulir UI Streamlit: sidebar con info, manejo de errores | UI funcional y presentable |
| 10-12 | **Maru** | Fallback multi-proveedor LLM (Groq → Gemini → Mistral) | Resiliencia para la demo |
| 12-14 | **Nati** | Docker funcional en EC2 con todo conectado | Deploy real accesible |
| 12-14 | **Todos** | Sesión de QA: cada uno prueba el flujo completo | Lista de bugs → fix inmediato |

### Semana 3 (días 15-17): PRESENTAR

**Objetivo:** Demo impecable, slides con arquitectura y métricas.

| Día | Persona | Tarea |
|-----|---------|-------|
| 15 | **Todos** | Preparar 3-5 consultas tipo para la demo (una por funcionalidad) |
| 15 | **Maru** | Slides: arquitectura (diagrama), métricas (RAGAS, F1), screenshots Langfuse/MLflow |
| 16 | **Todos** | Ensayo de presentación (20 min + 10 min preguntas) |
| 17 | **Todos** | Buffer para imprevistos |

### Criterio de éxito por semana

| Semana | La semana fue exitosa si... |
|--------|-----------------------------|
| 1 | Un usuario puede hacer una pregunta legal en Streamlit y recibir una respuesta con citas reales |
| 2 | Hay tests pasando, métricas documentadas, y la app está desplegada en EC2 |
| 3 | La demo funciona sin fallos y el equipo puede explicar cada decisión técnica |

---

## Contexto para compartir antes de la reunión

> **Buenas noticias:** Tras revisar los commits de las últimas 48h, el equipo ha avanzado
> mucho más de lo que pensábamos. El corpus legal existe y está en DVC/S3, Langfuse está
> implementado de verdad, RAGAS tiene pipeline y dataset, y el clasificador se ha reestructurado.
>
> **Lo que falta:** Hay varias ramas de feature sin mergear a develop (`chore/langfuse`,
> `feature/RAGAS`, `feature/model-ml`). Y los módulos `src/rag/main.py` y `src/data/main.py`
> siguen siendo stubs en develop — a pesar de que Dani ya tiene el corpus chunkeado y
> un notebook de retrieval. La prioridad es conectar todo.

---

## Estado real descubierto al revisar los commits

### Dani (Data + RAG) — Avances significativos

- **Corpus legal EXISTE** y está en S3 vía DVC:
  - `data/chunks_legal/chunks_final.jsonl` (2.4 MB, ~cientos de chunks)
  - `data/chunks_legal/chunks_final_all_sources.jsonl` (merge con LOPD/RGPD)
- **Notebook de chunking completo** (`src/data/01_chunking_boe_eu_aesia.ipynb`):
  procesa BOE (HTML), EU AI Act (HTML), AESIA (PDF), LOPD/RGPD (PDF)
- **ChromaDB en requirements** (`22b643cc`)
- **Pipeline de retrieval** añadido (`90c64051`)
- **Rama `feature/data-chunks`** ya mergeada a develop

**Pendiente:** `src/rag/main.py` y `src/data/main.py` en develop siguen siendo stubs.
El trabajo de Dani está en notebooks pero no se ha trasladado a los módulos Python.

### Nati (MLOps) — Avances significativos

- **Langfuse REAL implementado** en `src/observability/main.py` (rama `chore/langfuse`):
  usa `langfuse.langchain.CallbackHandler` v3 con session_id, user_id, tags
- **Orquestador instrumentado** con `get_langfuse_handler()` (rama `chore/langfuse`)
- **RAGAS pipeline completo** (rama `feature/RAGAS`):
  - `eval/run_ragas.py` — Script principal con modo CI
  - `eval/helpers.py` — Carga dataset, invoca agente, calcula métricas, loguea en MLflow
  - `eval/dataset.json` — 10 preguntas gold con contexts y ground_truth
  - KPIs definidos: faithfulness >= 0.80, answer_relevancy >= 0.85
- **CI/CD actualizado** para incluir RAGAS como gate de calidad

**Pendiente:** Las ramas `chore/langfuse` y `feature/RAGAS` NO están mergeadas a develop.

### Rubén (ML + NLP) — Avances

- **Reestructuración de carpetas** entre `classifier_Dataset_artificial` y `classifier_Dataset_real` (`d6642661`)
- **Cambios importantes en `functions.py`** (448 líneas de diff)
- **Imágenes SHAP generadas** (beeswarm y waterfall por clase)
- **Documentación añadida** (`ad09516a`)
- **Notebooks ejecutados** con outputs

**Pendiente:** Rama `feature/model-ml` NO está mergeada a develop. No hay `predict_risk()` como función de servicio aún.

### Maru (Agents + UI)

- **Nodos RAG en LangGraph** añadidos hace ~6 días (rama `feature/rag`):
  retrieve, grade_documents, transform_query, generate
- **Sistema de tutoría Claude Code** configurado

---

## Agenda actualizada (30 min)

### 1. Reconocer avances (5 min)

Empezar la reunión reconociendo lo que cada uno ha hecho. El equipo ha trabajado
más de lo que parece. Esto es importante para la moral.

### 2. Estado de ramas y merges pendientes (10 min)

**Problema principal:** Hay mucho trabajo hecho pero disperso en ramas sin mergear.

| Rama | Autor | Estado | Acción |
|------|-------|--------|--------|
| `feature/data-chunks` | Dani | **Mergeada a develop** | Hecho |
| `chore/langfuse` | Nati | Sin mergear (2 archivos cambiados) | Crear PR → develop |
| `feature/RAGAS` | Nati | Sin mergear (5 archivos nuevos) | Crear PR → develop |
| `feature/model-ml` | Rubén | Sin mergear (161 archivos, 4K+ líneas) | Crear PR → develop |
| `feature/rag` | Maru | Sin mergear (nodos LangGraph) | Evaluar vs estado de Dani |

**Acción:** Mergear TODO a develop esta semana. Sin código en develop, no hay demo.

### 3. La pieza que falta: conectar stubs a código real (10 min)

A pesar de los avances, los módulos Python en `src/` siguen siendo stubs en develop.
El trabajo real está en notebooks y ramas. La tarea más urgente:

```
Notebooks/ramas de Dani ──→ src/data/main.py (ChromaDB real)
                           ──→ src/rag/main.py (RAG real)

Rubén (functions.py) ──→ src/classifier/main.py (predict_risk())

Nati (chore/langfuse) ──→ merge a develop

Maru (feature/rag) ──→ conectar tools del orquestador
```

### 4. Asignación para la semana (10 min)

| Persona | Tarea prioritaria | Entregable concreto | Fecha |
|---------|-------------------|---------------------|-------|
| **Dani** | Trasladar retrieval de notebook a `src/data/main.py` y `src/rag/main.py` | Funciones reales que usen ChromaDB + embeddings con el corpus DVC | 27 feb |
| **Rubén** | Exponer clasificador como servicio + mergear model-ml | `predict_risk(text) -> dict` en `src/classifier/main.py` + PR mergeada | 26 feb |
| **Nati** | Mergear langfuse + RAGAS a develop + tests mínimos | 2 PRs mergeadas + al menos 1 test en `tests/` | 26 feb |
| **Maru** | Conectar tools del orquestador con módulos reales | Las 3 tools en orchestrator llaman a src/rag, src/classifier, src/report | 28 feb |

### 5. Compromisos rápidos (5 min)

- [ ] Mergear TODAS las ramas feature a develop antes del jueves
- [ ] ¿Alguien necesita pair programming?
- [ ] ¿Todos instalan Claude Code y prueban `/tutor`?
- [ ] Próxima check-in: jueves

---

## Preguntas para la reunión

1. **Dani:** ¿El pipeline de retrieval del notebook funciona con ChromaDB real? ¿Falta solo trasladarlo a `src/`?

2. **Rubén:** ¿El modelo serializado (.joblib) está en el repo o en S3? ¿Se puede cargar sin re-entrenar?

3. **Nati:** ¿Langfuse funciona en producción o solo local? ¿Las credenciales están en el .env?

4. **Todos:** ¿Enfocamos en demo funcional con subconjunto de artículos o intentamos tener el corpus completo? (Recomendación: demo funcional primero)

---

## Lo que ya NO es un problema (vs diagnóstico anterior)

- ~~No hay corpus legal~~ → Existe en DVC/S3 (chunks_final.jsonl, 2.4 MB)
- ~~Langfuse es stub~~ → Implementado de verdad (rama chore/langfuse)
- ~~No hay evaluación RAGAS~~ → Pipeline completo con 10 preguntas gold + CI gate
- ~~ChromaDB no existe~~ → Ya está en requirements, Dani tiene notebook de retrieval
- ~~CI sin tests~~ → Nati ha trabajado en RAGAS como gate de calidad

## Lo que SÍ sigue siendo crítico

- `src/rag/main.py` y `src/data/main.py` **siguen siendo stubs en develop**
- No hay `predict_risk()` expuesta como función de servicio
- Las tools del orquestador **siguen devolviendo datos hardcodeados**
- **Ramas sin mergear** — el trabajo existe pero no está integrado
- **0 tests unitarios** en `tests/` (RAGAS es evaluación, no tests)

---

## Después de la reunión

1. Cada persona crea PR para su rama → develop
2. Actualizar `docs/gestion-proyecto/NORMABOT_PROGRESS.md` con acuerdos
3. Cada miembro prueba `/tutor` en Claude Code
4. Próxima check-in con demo parcial

---

## Sistema de tutoría Claude Code (1 min para explicar al equipo)

Hemos montado un sistema de skills en `.claude/` que todo el equipo puede usar:

- **`/tutor`** → "¿Qué debería hacer hoy?" (orientación general)
- **`/diagnostico`** → "¿Qué funciona de verdad en el código?" (auditoría)
- **`/planificar sprint`** → "¿Cuál es el plan para esta semana?" (tareas por persona)
- **`/progreso`** → "¿Cómo vamos?" (actualiza tracking)
- **`/evaluar`** → "¿Qué nota sacaríamos hoy?" (auto-evaluación vs rúbrica)
- **`/revisar [archivo]`** → "¿Está bien mi código?" (code review)

Además hay hooks automáticos: al abrir el proyecto se recuerda el deadline y los
skills disponibles, y al editar código en `src/` se recuerda escribir tests.
