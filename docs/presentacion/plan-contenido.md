# Plan de Contenido — Presentación NormaBot

**Duración**: 15 min presentación + 15 min Q&A
**Fecha**: 12 de marzo de 2026

---

## Slide 1: Título (30s)

**NormaBot — Sistema Agentic RAG para Regulación de IA**

- Tagline: "Consulta normativa, clasifica riesgo, genera checklists de cumplimiento"
- Nombres del equipo + bootcamp

---

## Slide 2-3: El Problema (1.5 min)

### El problema real

- La regulación de IA en Europa es compleja: EU AI Act (113 artículos + anexos), BOE, RGPD
- Una empresa que desarrolla IA necesita saber: ¿mi sistema cumple? ¿qué nivel de riesgo tiene? ¿qué obligaciones tengo?
- Hoy esto requiere un abogado especializado y semanas de análisis

### Nuestra solución

- Un asistente conversacional que consulta la normativa real, clasifica el riesgo y genera un checklist de cumplimiento — en segundos
- No reemplaza al abogado, lo complementa (*"Informe preliminar generado por IA. Consulte profesional jurídico."*)

---

## Slide 4-5: Arquitectura y Pipeline (3 min)

**Usar el diagrama de arquitectura** (`docs/especs-normabot/normabot-architecture final.png`)

Explicar el flujo de izquierda a derecha:

### 1. Pipeline de datos (Dani)

- 3 fuentes legales → chunking estructurado → embeddings `multilingual-e5-base` → ChromaDB
- Versionado con DVC + S3

### 2. Agente ReAct (Maru) — el cerebro

- Bedrock Nova Lite decide qué herramienta usar según la pregunta
- No es un pipeline fijo: el agente razona y decide (mostrar ejemplo de traza Langfuse si hay)

### 3. Tool 1: RAG Correctivo (Dani + Maru)

- Retrieve de ChromaDB → Grade con Ollama Qwen 2.5 3B (local) → Format context
- Side-channel: citas verificadas van por fuera del LLM (ContextVar) — **el LLM no puede inventar citas**
- Decisión técnica: grading local para evitar dependencia de API y latencia

### 4. Tool 2: Clasificador + Checklist (Rubén + Maru)

- XGBoost (F1-macro 0.88) + override determinista Anexo III
- SHAP para explicabilidad → recomendaciones mapeadas a artículos EU AI Act
- Checklist 100% determinista (sin LLM) — obligaciones + borderline detection
- Decisión técnica: override legal prevalece sobre ML porque en derecho la exactitud es obligatoria

### 5. Memoria (Maru)

- SQLite checkpointer + trimming a 30K tokens
- El usuario puede mantener conversaciones con contexto

### 6. Observabilidad (Nati)

- Langfuse para trazas, MLflow para experimentos
- Graceful degradation: todo funciona sin estas dependencias

---

## Slide 6: Demo en vivo (3 min)

### 3 queries preparadas que muestren las 3 capacidades

1. **Consulta legal**: *"¿Qué dice el artículo 6 del EU AI Act sobre sistemas de alto riesgo?"*
   → Muestra citas verificadas en el expander, fuentes con artículo + norma

2. **Clasificación de riesgo**: *"Tengo un sistema de reconocimiento facial en tiempo real en espacios públicos"*
   → Muestra: nivel inaceptable (Art. 5.1.d), checklist de obligaciones, override determinista

3. **Caso ambiguo/borderline**: *"Sistema de IA para evaluar solicitudes de crédito bancario"*
   → Muestra: alto riesgo (Anexo III cat. 5.b), recomendaciones SHAP, detección borderline

### Tips para la demo

- Tener Ollama corriendo + .env configurado ANTES
- Si algo falla, mostrar el graceful degradation como feature ("diseñamos para fallar bien")
- Tener screenshots de backup por si EC2/internet falla

---

## Slide 7-8: Métricas y Evaluación (2 min)

### Clasificador ML

| Métrica | Valor | Contexto |
|---------|-------|----------|
| F1-macro | 0.88 | Dataset fusionado (real + sintético, ~300 ej.) |
| Explicabilidad | SHAP | Top 5 features con contribución por predicción |
| Estrategia imbalance | 3 niveles | class_weight balanced + StratifiedKFold + F1 scoring |
| Experimentos | 3 en MLflow | Dataset real vs artificial vs fusionado |

### RAG (RAGAS)

| Métrica | Valor | Umbral |
|---------|-------|--------|
| Faithfulness | No evaluable (rate limits Bedrock) | ≥ 0.80 |
| Context precision | 0.86-1.0 (2 runs) | ≥ 0.70 ✓ |
| Context recall | 0.44-0.52 | ≥ 0.70 (no alcanzado — grader restrictivo) |

- Ser honestos: context recall bajo → el grader es restrictivo → mejora futura clara
- Esto demuestra madurez: "medimos, identificamos el problema, sabemos cómo mejorarlo"

### Testing

- 53+ tests automatizados (23 checklist + 24 orchestrator + 4 constants + 2 memory), ~73+ total con deps ML
- CI/CD: 5 workflows GitHub Actions (lint → test → build → deploy → eval)

---

## Slide 9: Costes y Escalabilidad (1.5 min)

### Costes actuales

| Recurso | Coste | Notas |
|---------|-------|-------|
| EC2 (t3.medium) | ~$30/mes | App Streamlit + Ollama |
| Bedrock Nova Lite | ~$0.001/query | Pay per use, muy bajo |
| Ollama (local) | $0 | Grading sin coste API |
| S3 (DVC) | ~$1/mes | Almacenamiento de datos |
| MLflow server | compartido con EC2 | — |
| Langfuse cloud | free tier | — |
| **Total** | **~$40-45/mes** | — |

### Decisiones de ahorro

- Ollama local para grading → $0 vs ~$0.01/query si usáramos API
- Checklist determinista → 1 LLM call menos por sesión (~500ms + ahorro Bedrock)
- Nova Lite (vs Pro/Sonnet) → suficiente para orchestration

### Escalabilidad (mejoras futuras)

- Horizontal: ChromaDB → servicio separado, Ollama → GPU dedicada
- Corpus: pipeline de actualización automática (nuevo BOE → trigger → re-indexar)
- Multi-modelo: el override determinista permite cambiar el modelo ML sin tocar lógica legal

---

## Slide 10: Proceso del Equipo (1 min)

### Historia del proyecto en números

- 50 PRs mergeadas en 12 días (28 feb → 10 mar)
- Pico: 11 merges el 2 de marzo (sprint de bugfixing)
- 4 miembros, roles claros: Data, ML, Agents+UI, MLOps
- Herramientas: GitHub (PRs + issues), CodeRabbit (reviews automáticos), Claude Code (tutoring + debugging)

### Evolución clave

- **Sprint 1** (28 feb - 1 mar): integración inicial + primeros bugs
- **Sprint 2** (2-4 mar): bugfixing intensivo (11 PRs/día), side-channel, refactor report→checklist
- **Sprint 3** (5-7 mar): refactors, RAGAS, estabilización
- **Sprint 4** (8-10 mar): evaluación, documentación, cierre

---

## Slide 11-12: Reflexión (2.5 min)

### ¿Qué nos aportó?

- Experiencia real de integración de sistemas complejos: no es solo "un modelo" sino 6 módulos que deben funcionar juntos
- Entender que en producción el 80% del tiempo se va en bugs de integración, no en el modelo
- Trabajar con restricciones reales: dominio legal donde la exactitud no es opcional

### ¿Qué aprendimos?

- Que un dataset pequeño (300 ej.) es una limitación real — las métricas "demasiado buenas" del dataset sintético nos engañaron al principio (PR #81, #83)
- Que el grading del RAG es el eslabón más frágil: demasiado estricto → 0 documentos → fallback → respuestas pobres (8 PRs dedicadas a este bug)
- Que la observabilidad (Langfuse) no es un lujo: detectamos el bug de doble llamada al clasificador gracias a las trazas (PR #90, #95)
- Que CI/CD desde el día 1 salva vidas: 50 PRs en 12 días sin romper nada en main

### ¿Qué no repetiríamos?

- Dataset sintético como base principal — invertir más tiempo en datos reales desde el inicio
- Integrar todo tarde — los módulos funcionaban por separado pero la integración reveló bugs que no existían en aislamiento
- 3 herramientas en el orquestador (report era redundante) — diseñar con menos capas LLM desde el principio

### ¿Qué seguiríamos haciendo?

- Override determinista sobre ML en dominio legal — el ML cubre lo ambiguo, las reglas cubren lo claro
- Side-channel para datos verificables — nunca confiar al LLM datos que deben ser exactos
- Graceful degradation en todo — Langfuse, Ollama, MLflow son opcionales en runtime
- Claude Code como tutor de proyecto — diagnósticos, evaluaciones, tracking de progreso

---

## Distribución sugerida de speakers

| Sección | Quién | Por qué |
|---------|-------|---------|
| Problema + solución | Dani | Conoce el dominio legal y el corpus |
| Arquitectura (pipeline datos + RAG) | Dani | Construyó el pipeline de datos |
| Arquitectura (clasificador + checklist) | Rubén | Construyó el ML pipeline |
| Arquitectura (orquestador + memoria) | Maru | Construyó el agente y la integración |
| Demo | Maru | Conoce el flujo E2E |
| Métricas + evaluación | Rubén (clasificador) + Nati (RAGAS) | Cada uno sus métricas |
| Costes + infra + CI/CD | Nati | Construyó toda la infra |
| Reflexión | Todos (1 pregunta cada uno) | Cierre grupal |
