# NormaBot — Agentic RAG sobre Normativa Española

## Qué es este proyecto

NormaBot es un sistema **Agentic RAG** que permite consultar en lenguaje natural el BOE, el EU AI Act y regulaciones sectoriales, clasificar sistemas de IA por nivel de riesgo y generar informes de cumplimiento. Deploy en AWS SageMaker.

## Arquitectura

3 agentes orquestados por **LangGraph** con routing condicional:

1. **Agente RAG Normativo** (Corrective RAG): Retrieve → Grade → Transform query → Web fallback → Generate → Self-reflection. ChromaDB como vector store. **Grading híbrido**: filtro determinista primero (metadata + umbral score) para descartar irrelevantes sin consumir cuota LLM, seguido de LLM como juez binario solo para los documentos que pasen el primer filtro. Decisión motivada por el dominio legal (requiere precisión en citas) y el rate limiting de Groq.
2. **Agente Clasificador de Riesgo** (ML): XGBoost clasifica sistemas de IA en 4 niveles del EU AI Act (inaceptable, alto, limitado, mínimo).
3. **Agente de Informes**: genera informes de cumplimiento con citas legales exactas.

Flujo: Consulta → Orquestador LangGraph → Agente(s) correspondiente(s) → Respuesta con fuentes + riesgo + recomendaciones.

## Estructura del proyecto

```
proyecto-final/
├── app.py                  # Streamlit UI (chat + clasificador + informes)
├── src/
│   ├── agents/             # LangGraph: grafo de estados, routing, 3 agentes
│   ├── rag/                # Corrective RAG pipeline, ChromaDB, retrieval
│   ├── classifier/         # XGBoost clasificador riesgo, SHAP, MLflow tracking
│   └── nlp/                # spaCy NER legal, fine-tuning QLoRA
├── data/                   # Corpus legal (BOE, EU AI Act, AESIA, LOPD)
├── eval/                   # RAGAS + DeepEval: evaluación automática RAG
├── scripts/                # Scraping BOE, ETL, utilidades
├── tests/                  # pytest (unitarios + E2E)
├── docs/                   # Especificaciones del proyecto
├── Dockerfile              # Docker para AWS SageMaker (python:3.12-slim, puerto 8080)
├── docker.compose.yml
└── requirements.txt
```

## Stack tecnológico (todo gratuito)

- **LLM**: Groq API (Llama 3.3 70B, 14.400 req/día) → Gemini fallback → Mistral fallback
- **Agentes**: LangGraph + LangChain
- **Vector store**: ChromaDB (embebido, persistido)
- **Embeddings**: `paraphrase-multilingual-MiniLM-L12-v2` (sentence-transformers, CPU)
- **ML**: scikit-learn, XGBoost, Grid Search, Stratified k-fold (k=5)
- **NLP**: spaCy (`es_core_news_lg`) para NER legal
- **Fine-tuning**: QLoRA con Unsloth, Llama 3.2 3B, en Google Colab T4
- **MLOps**: MLflow (tracking + registry), DVC (versionado corpus con Google Drive)
- **Observabilidad**: Langfuse (trazas LLM), EvidentlyAI (drift), RAGAS + DeepEval (eval RAG)
- **CI/CD**: GitHub Actions (test → lint → RAGAS eval → build Docker → deploy AWS SageMaker)
- **UI**: Streamlit
- **Deploy**: AWS SageMaker

## Lenguaje y convenciones

- **100% Python** (3.12)
- Linter: **ruff**
- Tests: **pytest**
- Schemas/validación: **Pydantic**
- Idioma del código: inglés para nombres de variables/funciones, español para docstrings y comentarios donde sea necesario (el dominio es legislación española)
- Commits y PRs en español

## Datos

Todas las fuentes son públicas y gratuitas:

| Dato | Fuente | Obtención |
|------|--------|-----------|
| BOE (legislación IA, datos, financiero) | boe.es | Scraping |
| EU AI Act (Reglamento UE 2024/1689) | EUR-Lex | Público |
| Guías AESIA + sandbox | aesia.gob.es | Público |
| Dataset clasificación riesgo (200-300 desc.) | Elaboración propia | Etiquetado manual |
| Artículos BOE etiquetados (~500) | BOE + manual | Etiquetado manual |
| LOPD-GDD, RGPD | boe.es / aepd.es | Público |
| Regulación sectorial (banca, seguros) | BOE / CNMV / BdE | Scraping |

Chunking: por artículo/sección (no por tokens arbitrarios). Metadata: ley, artículo, fecha, BOE número.

## KPIs objetivo

- RAGAS Faithfulness: **>= 0.80**
- RAGAS Answer Relevance: **>= 0.85**
- F1-macro clasificador riesgo: **>= 0.80**
- Latencia respuesta: **<= 5s**
- CI/CD funcional: **100%**

## Comandos principales

```bash
# Tests
pytest tests/ -v

# Lint
ruff check .

# Evaluación RAG
python eval/run_ragas.py

# App local
streamlit run app.py --server.port=8080

# Docker
docker build -t normabot .
docker run -p 8080:8080 normabot
```

## Consideraciones importantes

- **Alucinaciones**: el dominio legal exige citas exactas. Siempre usar Corrective RAG con self-reflection. Toda respuesta debe incluir artículos fuente del BOE/EU AI Act.
- **Disclaimer obligatorio**: "Informe preliminar, consulte profesional jurídico" en toda respuesta generada.
- **Rate limiting**: implementar fallback multi-proveedor (Groq → Gemini → Mistral) y cache de respuestas frecuentes.
- **Clasificador**: dataset pequeño (200-300 ejemplos). Usar `class_weight='balanced'`, augmentation con paráfrasis, y documentar como limitación conocida.
- **Explicabilidad**: SHAP para features relevantes del clasificador ML.

## Equipo (4 personas, 17 días)

- **Persona A**: Data + RAG Engineer (scraping BOE, chunking, ChromaDB, deploy AWS)
- **Persona B**: ML + NLP Engineer (clasificador riesgo, NER spaCy, fine-tuning QLoRA)
- **Persona C**: Agents + UI Lead (LangGraph, 3 agentes, Streamlit)
- **Persona D**: MLOps + Observabilidad (MLflow, DVC, CI/CD, Langfuse, RAGAS eval)
