# NormaBot — Agentic RAG sobre Normativa Española

## Qué es este proyecto

NormaBot es un sistema **Agentic RAG** que permite consultar en lenguaje natural el BOE, el EU AI Act y regulaciones sectoriales, clasificar sistemas de IA por nivel de riesgo y generar informes de cumplimiento. Deploy en EC2 (AWS) con Docker.

## Arquitectura

Un **agente ReAct** (LangGraph `create_react_agent`) orquestado por **Amazon Bedrock (Nova Lite v1)** que razona sobre la consulta del usuario y decide qué herramientas usar:

1. **search_legal_docs**: búsqueda normativa (Corrective RAG). Flujo previsto: Retrieve → Grade → Transform query → Web fallback → Generate → Self-reflection. ChromaDB como vector store. Grading híbrido: filtro determinista primero (metadata + umbral score), seguido de LLM como juez binario.
2. **classify_risk**: clasificación de riesgo ML (XGBoost + TF-IDF). Clasifica sistemas de IA en 4 niveles del EU AI Act (inaceptable, alto, limitado, mínimo).
3. **generate_report**: informes de cumplimiento con citas legales exactas.

Flujo: Consulta → Agente ReAct (Bedrock) → Tool(s) correspondiente(s) → Respuesta con fuentes + riesgo + recomendaciones.

## Estructura del proyecto

```
proyecto-final/
├── app.py                      # Streamlit UI (chat con orquestador)
├── src/
│   ├── orchestrator/main.py    # Agente ReAct (Bedrock Nova Lite + tools)
│   ├── agents/state.py         # AgentState TypedDict para LangGraph
│   ├── rag/main.py             # Corrective RAG pipeline (stub)
│   ├── data/main.py            # Embeddings + ChromaDB (stub)
│   ├── classifier/             # Notebooks ML 1-12 (dataset artificial)
│   │   └── classifier_2/       # Notebooks ML 0-12 (dataset Hugging Face)
│   ├── report/main.py          # Informes de cumplimiento (stub)
│   ├── ui/main.py              # UI mock consola (no se usa)
│   └── observability/main.py   # Langfuse trazas (stub)
├── infra/
│   ├── terraform/              # EC2, S3, IAM, VPC, Bedrock
│   └── ansible/                # Playbooks deploy MLflow + NormaBot
├── data/                       # Corpus legal (datos en S3 vía DVC)
├── eval/                       # RAGAS + DeepEval (pendiente)
├── scripts/                    # Utilidades (pendiente)
├── tests/                      # pytest (pendiente)
├── docs/                       # Specs, decisiones, reuniones, MLOps, ML
├── requirements/               # Separados: base, app, dev, ml, infra
├── Dockerfile                  # python:3.12-slim, Streamlit en :8080
├── docker-compose.yml
└── .github/workflows/          # ci-develop.yml + cicd-main.yml
```

## Stack tecnológico

- **LLM**: Amazon Bedrock — Nova Lite v1 (`eu.amazon.nova-lite-v1:0`, región eu-west-1)
- **Agentes**: LangGraph (`create_react_agent`) + LangChain
- **Vector store**: ChromaDB (pendiente de implementar)
- **Embeddings**: `paraphrase-multilingual-MiniLM-L12-v2` (pendiente de implementar)
- **ML**: scikit-learn, XGBoost, Grid Search, Stratified k-fold (k=5)
- **Fine-tuning**: QLoRA con bitsandbytes + HuggingFace PEFT, Mistral-7B, en Google Colab T4
- **MLOps**: MLflow (desplegado en EC2 con Docker + NGINX), DVC (versionado corpus con S3)
- **Observabilidad**: Langfuse Cloud (región EU) — configurado, integración pendiente
- **CI/CD**: GitHub Actions → GHCR → SSH deploy a EC2
- **IaC**: Terraform + Ansible
- **UI**: Streamlit
- **Deploy**: EC2 (AWS), Docker Compose, NGINX reverse proxy

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
| Dataset clasificación riesgo (artificial) | Elaboración propia | Etiquetado manual |
| Dataset clasificación riesgo (HF) | Hugging Face | Descarga |
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

# App local
streamlit run app.py --server.port=8080

# Docker
docker build -t normabot .
docker run -p 8080:8080 normabot
```

## Consideraciones importantes

- **Alucinaciones**: el dominio legal exige citas exactas. Siempre usar Corrective RAG con self-reflection. Toda respuesta debe incluir artículos fuente del BOE/EU AI Act.
- **Disclaimer obligatorio**: "Informe preliminar, consulte profesional jurídico" en toda respuesta generada.
- **Clasificador**: dos experimentos con datasets diferentes (artificial y Hugging Face). Usar `class_weight='balanced'`, augmentation con paráfrasis, y documentar como limitación conocida.
- **Explicabilidad**: SHAP para features relevantes del clasificador ML.

## Equipo (4 personas, 17 días hábiles)

- **Dani** (@danyocando-git): Data + RAG Engineer (scraping BOE, chunking, ChromaDB, deploy AWS)
- **Rubén** (@Rcerezo-dev): ML + NLP Engineer (clasificador riesgo, SHAP, fine-tuning QLoRA)
- **Maru** (@mariaeugenia-alvarez): Agents + UI Lead (LangGraph, orquestador, Streamlit)
- **Nati** (@natgarea): MLOps + Observabilidad (Terraform, Ansible, CI/CD, Langfuse)
