# NormaBot — Roadmap de Desarrollo

Fecha: 2026-02-22

Priorizado por **impacto en la presentación / esfuerzo**. Las funcionalidades están alineadas con el temario del bootcamp.

---

## Leyenda

- **Complejidad**: S (< 1 día), M (1-2 días), L (3+ días)
- **Temario**: área del bootcamp que cubre

---

## Fase 1 — Flujo End-to-End (P0, bloqueante)

Objetivo: que un usuario pueda hacer una pregunta legal y recibir una respuesta real.

### 1.1 Ingesta del corpus legal en ChromaDB
- **Descripción**: Implementar `src/data/main.py` con SentenceTransformer (`paraphrase-multilingual-MiniLM-L12-v2`) + ChromaDB persistente. Chunking por artículo/sección con metadata (ley, artículo, fecha, BOE número).
- **Temario**: Bases de datos vectoriales, NLP
- **Complejidad**: M
- **Justificación**: Sin vector store no hay RAG. Es el primer eslabón de toda la cadena.

### 1.2 RAG Pipeline real (Corrective RAG)
- **Descripción**: Implementar en `src/rag/main.py`: retrieve desde ChromaDB → grading híbrido (filtro por score + LLM judge) → query transformation si no hay docs relevantes → generate con LLM (Groq/Bedrock) → self-reflection para verificar que la respuesta cita fuentes reales.
- **Temario**: RAG, LLMs, Prompt Engineering
- **Complejidad**: L
- **Justificación**: Es la funcionalidad core del producto. El Corrective RAG con self-reflection diferencia el proyecto de un RAG naive.

### 1.3 Conectar tools del orquestador
- **Descripción**: Reemplazar los stubs en `src/orchestrator/main.py` para que `search_legal_docs` llame a `src/rag`, `classify_risk` llame al clasificador serializado (cargar desde joblib), y `generate_report` use LLM + template.
- **Temario**: Agentes autónomos, sistemas multiagente
- **Complejidad**: S
- **Justificación**: Sin esto, el agente ReAct devuelve respuestas fake. Es la integración que hace que todo funcione junto.

### 1.4 Tests mínimos
- **Descripción**: pytest para: (a) clasificador — predict con modelo cargado, (b) RAG — retrieve + grade con docs conocidos, (c) orquestador — invocación end-to-end con mock LLM. Descomentar job de tests en CI.
- **Temario**: MLOps (CI/CD, testing)
- **Complejidad**: M
- **Justificación**: El CI tiene el job de tests comentado. Sin tests, cualquier cambio puede romper el flujo sin que nadie se entere.

---

## Fase 2 — Calidad y Diferenciación (P1)

Objetivo: métricas objetivas de calidad y features que diferencien el proyecto.

### 2.1 Evaluación RAGAS
- **Descripción**: Implementar `eval/run_ragas.py` con un dataset de preguntas-respuestas gold. Medir Faithfulness (>= 0.80) y Answer Relevance (>= 0.85). Integrar como paso en CI (gate de calidad).
- **Temario**: Evaluación de modelos, RAG
- **Complejidad**: M
- **Justificación**: KPI objetivo del proyecto. Demuestra que el RAG no alucina, que es crítico en dominio legal. Pocas personas en un bootcamp implementan evaluación automática de RAG.

### 2.2 Integración Langfuse (observabilidad)
- **Descripción**: Reemplazar stub en `src/observability/main.py` con Langfuse real. Instrumentar: latencia por paso del RAG, tokens consumidos, costes, trazas de las decisiones del agente. Dashboard visible en presentación.
- **Temario**: MLOps (monitoreo, logging)
- **Complejidad**: S
- **Justificación**: Ya está en requirements. Pasar de stub a real es poco esfuerzo y da un dashboard visual muy impactante para la presentación.

### 2.3 Fallback multi-proveedor LLM
- **Descripción**: Implementar cadena Groq → Gemini → Mistral con retry y exponential backoff. Si Groq devuelve 429 (rate limit), rotar a Gemini; si falla, a Mistral.
- **Temario**: APIs y despliegue, resiliencia
- **Complejidad**: S
- **Justificación**: Groq tiene 14.400 req/día. En una demo puede agotarse. El fallback asegura disponibilidad y demuestra diseño resiliente.

### 2.4 Clasificador como servicio integrado
- **Descripción**: Crear una función `predict_risk(text: str) -> dict` en `src/classifier/` que cargue el modelo serializado (joblib), aplique el pipeline de features, y devuelva nivel de riesgo + SHAP explanation. Conectar con el tool del orquestador.
- **Temario**: ML clásico, APIs
- **Complejidad**: S
- **Justificación**: El clasificador está entrenado y serializado pero no expuesto como servicio. Es la pieza que falta para que el agente lo use en producción.

### 2.5 Generador de informes con LLM
- **Descripción**: Reemplazar el template estático en `src/report/main.py` con una llamada a LLM que genere informes personalizados basados en: clasificación de riesgo, artículos relevantes del RAG, y descripción del sistema del usuario.
- **Temario**: LLMs, Prompt Engineering
- **Complejidad**: S
- **Justificación**: El informe actual es siempre el mismo. Un informe personalizado con LLM es mucho más impactante en la demo.

---

## Fase 3 — Funcionalidades Avanzadas (P2, diferenciación)

Objetivo: features que van más allá de lo esperado en un bootcamp.

### 3.1 Fine-tuning QLoRA (documentación del proceso)
- **Descripción**: Si ya se hizo fine-tuning en Colab, subir el notebook al repo y documentar en `docs/ml/finetune.md`: dataset usado, hiperparámetros, métricas antes/después, limitaciones. Si no se hizo, documentar el plan y por qué se descartó.
- **Temario**: Deep Learning, transformers, fine-tuning
- **Complejidad**: S (documentar) / L (implementar)
- **Justificación**: Las dependencias de QLoRA están en `ml.txt` pero no hay código. Incluso documentar el intento/plan demuestra conocimiento.

### 3.2 Dashboard de métricas Streamlit
- **Descripción**: Añadir una pestaña en la UI con: métricas del clasificador (F1, confusion matrix), métricas RAGAS, latencia por consulta, SHAP waterfall interactivo para la última clasificación.
- **Temario**: Visualización, ML, UI
- **Complejidad**: M
- **Justificación**: Hace el proyecto visualmente impactante en la presentación. Streamlit tiene componentes nativos para gráficas.

### 3.3 Sistema de feedback del usuario
- **Descripción**: Thumbs up/down en cada respuesta del chat. Guardar en SQLite/JSON: query, respuesta, feedback, timestamp. Permite análisis posterior de calidad percibida.
- **Temario**: APIs, evaluación de modelos
- **Complejidad**: S
- **Justificación**: Demuestra pensamiento de producto y ciclo de mejora continua. Muy fácil de implementar en Streamlit (`st.feedback`).

### 3.4 Cache de respuestas frecuentes
- **Descripción**: Cache semántico: antes de ejecutar el RAG pipeline completo, buscar en cache si hay una respuesta reciente para una query similar (cosine similarity > umbral). Usar un diccionario simple o Redis.
- **Temario**: Bases de datos vectoriales, optimización
- **Complejidad**: S
- **Justificación**: Reduce latencia y coste de LLM. Importante con el rate limiting de Groq.

### 3.5 Scripts de scraping BOE
- **Descripción**: Versionar en `scripts/` el código de scraping del BOE que generó el corpus. Incluir: extracción de artículos, limpieza HTML, generación de chunks con metadata.
- **Temario**: NLP, ETL
- **Complejidad**: M
- **Justificación**: `scripts/` está vacío. Tener el ETL versionado demuestra reproducibilidad y transparencia en el pipeline de datos.

---

## Matriz de Priorización

```
                    ALTO IMPACTO
                         │
    ┌────────────────────┼────────────────────┐
    │                    │                    │
    │  2.2 Langfuse      │  1.2 RAG Pipeline  │
    │  2.3 Fallback LLM  │  1.1 ChromaDB      │
    │  2.4 Clasificador   │  2.1 RAGAS Eval    │
    │  2.5 Informes LLM  │  1.4 Tests         │
    │  1.3 Conectar tools │                    │
    │  3.3 Feedback       │                    │
    │                    │                    │
POCO ─────────────────────────────────────── MUCHO
ESFUERZO             │                    ESFUERZO
    │                    │                    │
    │  3.4 Cache          │  3.2 Dashboard     │
    │                    │  3.5 Scraping      │
    │                    │  3.1 Fine-tuning   │
    │                    │                    │
    └────────────────────┼────────────────────┘
                         │
                    BAJO IMPACTO
```

---

## Orden de Ejecución Recomendado

1. **1.1** ChromaDB + Embeddings → **1.2** RAG Pipeline → **1.3** Conectar tools (flujo end-to-end funcionando)
2. **2.4** Clasificador como servicio → **2.5** Informes con LLM (los 3 agentes funcionan de verdad)
3. **1.4** Tests mínimos (asegurar que no se rompe nada)
4. **2.3** Fallback multi-proveedor (estabilidad para la demo)
5. **2.2** Langfuse (dashboard visual para la presentación)
6. **2.1** RAGAS eval (métricas objetivas de calidad)
7. **3.3** Feedback del usuario (toque de producto)
8. **3.2** Dashboard de métricas (impacto visual)
9. **3.1** Fine-tuning QLoRA (documentar proceso)
10. **3.4** Cache semántico, **3.5** Scraping (si queda tiempo)
