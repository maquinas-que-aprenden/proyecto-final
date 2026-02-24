# NormaBot — Sprint Plan Detallado

Fecha: 2026-02-24 | Deadline: 2026-03-12 (16 dias)

---

## Sprint 1 — INTEGRAR (24 feb - 2 mar)

### Objetivo del sprint

Conseguir un flujo end-to-end funcional: usuario pregunta en Streamlit, el agente ReAct usa herramientas REALES (RAG, clasificador, informes) y devuelve respuestas con citas legales.

---

### Dani (Data + RAG) — ~9h restantes (Tareas 1.1 y 1.2 completadas)

#### Tarea 1.3: Implementar generate() con LLM — Esfuerzo: L (8h)
- **Archivo**: `src/rag/main.py` nodo `generate`
- **Que hay ahora**: Concatenacion estatica de citas
- **Nota**: Decidir si usar Ollama (consistente con grade) o Bedrock (ya en infra). Generate requiere respuestas largas → puede necesitar modelo mas capaz que 3B.
- **Que hacer**:
  1. Crear prompt de generacion:
     ```
     Eres un asistente juridico. Responde usando SOLO los documentos proporcionados.
     Cita siempre ley y articulo exactos. Si no hay info suficiente, dilo.
     Contexto: {documentos}
     Pregunta: {query}
     ```
  2. Llamar a LLM con el prompt (decidir: Ollama modelo mas grande, Bedrock, u otro)
  3. Parsear respuesta: extraer `answer` y `sources`
  4. Verificar que la respuesta cita fuentes reales (no hallucina)
  5. Agregar disclaimer: "Informe preliminar generado por IA..."
- **Verificacion**: `python -m src.rag.main` con queries reales sobre EU AI Act
- **Dependencia**: Tarea 1.2 (completada)

#### Tarea 1.4: Test e2e del RAG pipeline — Esfuerzo: S (1h)
- Ejecutar 5 queries variadas contra el pipeline completo
- Verificar que las citas son reales (no inventadas)
- Documentar metricas informales (latencia, calidad respuesta)
- **Dependencia**: Tarea 1.3

---

### Ruben (ML + NLP) — ~10h

#### Tarea 2.1: Crear predict_risk() en classifier/main.py — Esfuerzo: M (5h)
- **Archivo**: `src/classifier/main.py` (reemplazar stub actual)
- **Que hay ahora**: Funcion `predict()` que usa keywords hardcodeados
- **Que hacer**:
  1. Cargar modelos serializados con joblib (lazy, singleton):
     - `src/classifier/classifier_dataset_real/model/mejor_modelo.joblib`
     - `src/classifier/classifier_dataset_real/model/mejor_modelo_tfidf.joblib`
     - `src/classifier/classifier_dataset_real/model/label_encoder.joblib`
  2. Importar `limpiar_texto` y `crear_features_manuales` de `functions.py`
  3. Pipeline: `limpiar_texto(text)` -> `tfidf.transform([text])` -> `modelo.predict()` -> `label_encoder.inverse_transform()`
  4. Retornar dict:
     ```python
     {
       "risk_level": "alto",           # str: inaceptable/alto/limitado/minimo
       "confidence": 0.87,             # float: max probability
       "probabilities": {...},         # dict: probabilidad por clase
       "description": text,            # str: input original
     }
     ```
  5. Manejar errores: si modelo no existe, log warning y devolver clasificacion por defecto
- **Verificacion**: `python -c "from src.classifier.main import predict_risk; print(predict_risk('sistema de reconocimiento facial'))"`
- **Dependencia**: Ninguna

#### Tarea 2.2: Agregar explicabilidad SHAP al predict — Esfuerzo: M (3h)
- **Archivo**: `src/classifier/main.py`
- **Que hacer**:
  1. Importar `explicar_con_shap` de `functions.py`
  2. Tras la prediccion, calcular SHAP values para la muestra
  3. Extraer top 3 features mas influyentes
  4. Agregar al dict de retorno:
     ```python
     "shap_top_features": [
       {"feature": "keyword_vigilancia", "impact": 0.32},
       {"feature": "tfidf_reconocimiento", "impact": 0.18},
       ...
     ],
     "shap_explanation": "Las palabras clave 'vigilancia' y 'reconocimiento' indican alto riesgo..."
     ```
  5. Controlar memoria: si SHAP falla por OOM, retornar sin explicabilidad
- **Verificacion**: Verificar que el dict incluye shap_top_features con datos reales
- **Dependencia**: Tarea 2.1

#### Tarea 2.3: Documentar API del clasificador — Esfuerzo: S (2h)
- Agregar docstrings completos a `predict_risk()`
- Actualizar `docs/ml/pipeline.md` con la API de servicio
- Verificar que `model_metadata.json` es coherente en las 3 variantes
- **Dependencia**: Tarea 2.2

---

### Maru (Agents + UI) — ~18h

#### Tarea 3.1: Conectar tool search_legal_docs — Esfuerzo: M (4h)
- **Archivo**: `src/orchestrator/main.py` lineas 52-66
- **Que hay ahora**: Retorna string hardcodeado
- **Que hacer**:
  1. Importar RAG pipeline: `from src.rag.main import retrieve, grade, generate`
  2. Implementar:
     ```python
     @tool
     def search_legal_docs(query: str) -> str:
         docs = retrieve(query)
         relevant = grade(query, docs)  # nota: query como primer arg (cambio tarea 1.2)
         if not relevant:
             return "No se encontraron documentos relevantes para esta consulta."
         result = generate(query, relevant)
         return result["answer"]
     ```
  3. Manejo de errores: try/except con mensaje amigable si falla ChromaDB o LLM
- **Verificacion**: `python -m src.orchestrator.main` con query legal
- **Dependencia**: Tareas 1.1-1.3 de Dani (RAG real)
- **BLOQUEADA hasta que Dani termine RAG** — mientras tanto, avanzar con tarea 3.2

#### Tarea 3.2: Conectar tool classify_risk — Esfuerzo: M (4h)
- **Archivo**: `src/orchestrator/main.py` lineas 69-83
- **Que hay ahora**: Retorna string hardcodeado
- **Que hacer**:
  1. Importar: `from src.classifier.main import predict_risk`
  2. Implementar:
     ```python
     @tool
     def classify_risk(system_description: str) -> str:
         result = predict_risk(system_description)
         response = (
             f"Clasificacion: {result['risk_level'].upper()}\n"
             f"Confianza: {result['confidence']:.0%}\n"
         )
         if result.get("shap_top_features"):
             features = ", ".join(f["feature"] for f in result["shap_top_features"][:3])
             response += f"Factores clave: {features}\n"
         if result.get("shap_explanation"):
             response += f"Explicacion: {result['shap_explanation']}\n"
         return response
     ```
  3. Manejo de errores: si modelo no cargado, mensaje explicativo
- **Verificacion**: Test con descripcion de sistema de IA
- **Dependencia**: Tareas 2.1-2.2 de Ruben (predict_risk)
- **NO BLOQUEADA**: Ruben trabaja en paralelo, Maru puede mockear mientras tanto

#### Tarea 3.3: Conectar tool generate_report — Esfuerzo: M (4h)
- **Archivo**: `src/orchestrator/main.py` lineas 86-101
- **Que hay ahora**: Retorna string hardcodeado
- **Que hacer**:
  1. Importar: `from src.report.main import generate_report`
  2. Primero clasificar el sistema, luego generar informe:
     ```python
     @tool
     def generate_report(system_description: str) -> str:
         classification = predict_risk(system_description)
         risk = classification["risk_level"]
         articles = ["Art. 6 EU AI Act", "Art. 9 EU AI Act"]  # base
         report = generate_report(system_description, risk, articles)
         return report
     ```
  3. Futuro (P1): reemplazar template estatico de report con LLM
- **Verificacion**: Test generando informe para sistema de scoring
- **Dependencia**: Tarea 3.2

#### Tarea 3.4: Test end-to-end del orquestador — Esfuerzo: M (4h)
- Probar las 3 herramientas via el agente ReAct completo
- Queries de test:
  1. "Que dice el articulo 5 del EU AI Act?" (RAG)
  2. "Clasifica mi sistema de reconocimiento facial" (Clasificador)
  3. "Genera un informe para mi chatbot de atencion al cliente" (Report)
  4. "Clasifica un sistema de scoring crediticio y dime que articulos aplican" (multi-tool)
- Verificar Langfuse captura las trazas
- Fix bugs de integracion
- **Dependencia**: Tareas 3.1-3.3

#### Tarea 3.5: Mejorar UI Streamlit — Esfuerzo: S (2h)
- Agregar spinner/loading mientras el agente procesa
- Mejorar sidebar: mostrar tools disponibles, estado del sistema
- Error handling graceful (sin tracebacks en UI)
- **Dependencia**: Tarea 3.4

---

### Nati (MLOps) — ~4h

#### Tarea 4.1: Escribir 3 smoke tests — Esfuerzo: M (3h)
- **Archivo**: `tests/test_smoke.py`
- **Tests**:
  1. `test_retrieve()`: Importar retriever, buscar "EU AI Act", verificar que devuelve >= 1 resultado con metadata
  2. `test_classify()`: Importar predict_risk, clasificar "sistema de reconocimiento facial", verificar que devuelve risk_level valido
  3. `test_generate_report()`: Importar generate_report, verificar que retorna string con disclaimer
- Usar `@pytest.mark.skipif` si falta ChromaDB o modelo joblib (CI sin datos)
- **Dependencia**: Tareas 2.1 + 1.2 (modulos reales)

#### Tarea 4.2: Integrar RAGAS en CI — Esfuerzo: S (1h)
- Agregar step en `.github/workflows/ci-develop.yml` que ejecute `eval/run_ragas.py --ci`
- Solo en merges a develop (no en cada PR)
- **Dependencia**: RAG pipeline funcional (Tarea 1.3)

---

### Criterio de exito del Sprint 1

- [ ] `python -m src.rag.main` devuelve respuestas con citas REALES de ChromaDB
- [ ] `python -m src.classifier.main` clasifica con modelo joblib REAL
- [ ] `python -m src.orchestrator.main` ejecuta las 3 tools con implementaciones REALES
- [ ] `streamlit run app.py` permite hacer preguntas y recibe respuestas reales
- [ ] `pytest tests/` pasa (minimo 3 tests)

### Dependencias (quien bloquea a quien)

```
Dia 1-2:  Dani (RAG retrieve)  |  Ruben (predict_risk + SHAP)
          ↓                    ↓
Dia 2-4:  Dani (grade+generate)|  Maru (classify_risk tool, mockea RAG)
          ↓                    ↓
Dia 4-5:  Maru (conectar search_legal_docs + report) ← necesita RAG de Dani
          ↓
Dia 5-6:  Maru (test e2e + UI) | Nati (tests + RAGAS CI)
```

---

## Sprint 2 — PULIR (3 mar - 9 mar)

### Objetivo del sprint

Calidad de presentacion: metricas objetivas, resiliencia, deploy funcional.

#### Maru — Informe con LLM + fallback multi-proveedor (~8h)
- [ ] Implementar `src/report/main.py` con Groq LLM — Archivo: `src/report/main.py` — Esfuerzo: M
  - Reemplazar template estatico con llamada a LLM
  - Prompt: recibe clasificacion + articulos + descripcion, genera informe personalizado
- [ ] Implementar fallback Groq -> Gemini -> Mistral — Archivo: `src/rag/main.py` + `src/report/main.py` — Esfuerzo: M
  - `langchain_groq.ChatGroq` (primario)
  - `langchain_google_genai.ChatGoogleGenerativeAI` (fallback 1)
  - `langchain_mistralai.ChatMistralAI` (fallback 2)
  - Retry con exponential backoff en 429
- [ ] Streaming responses en Streamlit — Archivo: `app.py` — Esfuerzo: S

#### Ruben — Documentacion ML + metricas (~4h)
- [ ] Documentar metricas del clasificador final — Archivo: `docs/ml/metricas.md` — Esfuerzo: S
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

### Objetivo del sprint

Presentacion lista: demo funcional, slides, ensayo.

#### Todo el equipo
- [ ] Preparar 5 consultas demo que muestren cada tool — Esfuerzo: S
- [ ] Preparar slides: arquitectura, metricas, screenshots, stack — Esfuerzo: M
- [ ] Ensayo de presentacion (minimo 2 pasadas) — Esfuerzo: M
- [ ] Fix de ultimo momento si algo falla en demo — Esfuerzo: S

---

## Resumen de horas por persona

| Persona | Sprint 1 | Sprint 2 | Sprint 3 | Total |
|---------|----------|----------|----------|-------|
| Dani | 19h | 4h | 2h | 25h |
| Ruben | 10h | 4h | 2h | 16h |
| Maru | 18h | 8h | 4h | 30h |
| Nati | 4h | 8h | 2h | 14h |
| **Total** | **51h** | **24h** | **10h** | **85h** |

---

## Riesgos

| Riesgo | Probabilidad | Impacto | Mitigacion |
|--------|-------------|---------|-----------|
| Groq rate limiting en demo | Alta | Alto | Grading usa Ollama (local, sin rate limit). Generate: pendiente decision LLM |
| Ollama no disponible en EC2/Docker | Media | Medio | Fallback a filtro por score en grade(). Necesita Ollama en Docker o modelo alternativo |
| ChromaDB vacio en Docker | Media | Alto | DVC pull en Dockerfile o pre-built image |
| Modelo joblib no carga en EC2 | Media | Medio | Test en Docker local primero |
| SHAP OOM en produccion | Baja | Medio | `_sparse_to_dense_safe` ya implementado |
| Bedrock no disponible | Baja | Critico | Tener API key de backup |
