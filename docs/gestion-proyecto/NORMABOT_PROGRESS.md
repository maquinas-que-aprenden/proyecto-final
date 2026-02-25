# NormaBot — Tracking de Progreso

**Última actualización**: 2026-02-25 09:15 UTC (Auditoría técnica 2)

Rama actual: `feature/model-ml` (ya mergeada a `develop`)

---

## Resumen Ejecutivo

**Estado: 85-90% implementado, flujo parcialmente funcional.**

**HALLAZGO CRÍTICO**: La auditoría anterior (24 feb) reportó "todas las herramientas conectadas, CERO bloqueadores". El escaneo del código fuente ACTUAL (25 feb) revela 4 stubs reales SIN implementar y tests vacío.

---

## Completado (VERIFICADO EN CÓDIGO 2026-02-25)

| Fecha | Item | Responsable | Estado |
|---|---|---|---|
| Pre-proyecto | Clasificador ML (3 variantes) | Rubén | 1424 líneas. XGBoost + SHAP. FUNCIONAL. |
| Pre-proyecto | MLflow tracking | Nati | Servidor EC2. FUNCIONAL. |
| Pre-proyecto | CI/CD (3 workflows) | Nati | PR lint, develop, main. FUNCIONAL. |
| Pre-proyecto | IaC (Terraform + Ansible) | Nati | VPC, EC2, S3, nginx. FUNCIONAL. |
| Pre-proyecto | Orquestador ReAct | Maru | 172 líneas. Bedrock Nova Lite. FUNCIONAL. |
| Pre-proyecto | Streamlit UI | Maru | 42 líneas. Chat conversacional. FUNCIONAL. |
| Pre-proyecto | Docker + ghcr.io | Nati | Build, push, deploy. FUNCIONAL. |
| ~20 feb | Corpus legal + DVC | Dani | 2.4 MB chunks_final.jsonl. FUNCIONAL. |
| ~20 feb | ChromaDB Retriever | Dani | 155 líneas. 3 modos búsqueda. Lazy init. FUNCIONAL. |
| ~21 feb | Langfuse v3 | Nati | CallbackHandler integrado. FUNCIONAL. |
| ~21 feb | RAGAS pipeline | Nati | 10 Q&A gold, MLflow logging. FUNCIONAL. |
| 2026-02-24 | Tarea 1.1: retrieve() | Dani | ChromaDB real. FUNCIONAL. |
| 2026-02-24 | Tarea 1.2: grade() | Dani | Ollama Qwen 2.5 3B. FUNCIONAL. |
| 2026-02-24 | PR #47 (predict_risk) | Rubén | Thread-safe + SHAP. FUNCIONAL. Ready to merge. |

---

## En Progreso

| Item | Responsable | Estado | Bloques |
|---|---|---|---|
| Tarea 1.3: generate() con LLM | Dani | **STUB** | Depende: decisión LLM (Bedrock/Ollama/Groq) |
| Tarea 3.1-3.3: Tools conectadas | Maru | **STUB** | Depende: generate() implementado |
| Tarea 4.1: 3 smoke tests | Nati | **NO INICIADA** | Ninguno técnico |
| PR #47 merge | Maru | Listo | Ninguno |

---

## Stubs Encontrados en Código

### 1. generate() — src/rag/main.py:89-96

Estado: **STUB** (hardcoded)
Línea 90: `# TODO: reemplazar con Groq LLM call`
Impacto: RAG pipeline incompleto. No sincroniza docs con respuesta.

### 2. search_legal_docs() — src/orchestrator/main.py:52-66

Estado: **STUB** (hardcoded)
Línea 60: `# TODO: conectar con src/rag`
Devuelve: "Art. 5 EU AI Act: Quedan prohibidas las prácticas de IA..."
Impacto: Tool no usa input del usuario. Solo placeholder.

### 3. classify_risk() — src/orchestrator/main.py:69-83

Estado: **STUB** (hardcoded)
Línea 77: `# TODO: conectar con src/classifier`
Devuelve: "Clasificación: ALTO RIESGO..."
Impacto: Tool ignora descripción del sistema.

### 4. generate_report() — src/orchestrator/main.py:86-101

Estado: **STUB** (hardcoded)
Línea 93: `# TODO: conectar con src/report`
Devuelve: Template estático
Impacto: No usa clasificación ni búsqueda real.

### 5. tests/ directorio

Estado: **VACÍO** (0 tests)
Impacto: Cero cobertura de código.

---

## Plan de Acción (Hoy 25 feb)

### CRÍTICO (Bloquea demo)

1. **generate() con LLM** — Dani (4-6h)
   - Ubicación: `src/rag/main.py:89-96`
   - Cambio: Reemplazar template con LLM call + fallback
   - Desbloquea: RAG completo, tool search_legal_docs

2. **Conectar tools** — Maru (3-4h, depende de 1)
   - Ubicación: `src/orchestrator/main.py:52-101`
   - Cambio: Importar RAG, classifier, report reales
   - Desbloquea: Demo end-to-end

3. **Tests** — Nati (1.5h)
   - Ubicación: `tests/test_smoke.py`
   - Cambio: Crear 3 funciones test (retrieve, classify, report)
   - Desbloquea: CI pasa

---

## Métricas

| Métrica | Valor |
|---|---|
| Días hasta presentación | 16 (12 mar 2026) |
| Tareas P0 completadas | 3/11 |
| Tareas P0 pendientes | 8/11 |
| Componentes FUNCIONAL | 10/13 |
| Componentes STUB | 5 |
| Tests | 0 (VACÍO) |
| Esfuerzo restante | ~9-12h |

---

## Decisión Requerida

**Tarea 1.3**: ¿Qué LLM para generate()?
- Opción A: Bedrock Nova Lite (reutilizar del orquestador)
- Opción B: Ollama local Qwen 2.5 3B (consistencia con grade)
- Opción C: Groq (barato, latencia baja)

**Recomendación**: Opción A (Bedrock) para simplificar, O Opción B (Ollama) para evitar dependencias de API.

---

## Stack Confirmado

| Componente | Versión | Status |
|---|---|---|
| Python | 3.12 | ✓ |
| LangChain | 0.x | ✓ |
| Bedrock | Nova Lite v1 | ✓ |
| Ollama | Qwen 2.5 3B | ✓ |
| ChromaDB | PersistentClient | ✓ |
| scikit-learn | 1.5.2 | ✓ |
| XGBoost | 3.2.0 | ✓ |
| SHAP | 0.46.0 | ✓ |
| MLflow | 2.17.2 | ✓ |
| Langfuse | v3 | ✓ |
| RAGAS | >=0.2.0 | ✓ |
| Streamlit | >=1.40.0 | ✓ |
| Docker | 3.12-slim | ✓ |

---

## Próxima Auditoría

Programada: 2026-02-25 17:00 UTC (fin del sprint)

Verificar:
- generate() implementado
- Tools conectadas
- Tests creados
- PRs mergeadas
- Docker e2e OK
- Langfuse dashboard visible
