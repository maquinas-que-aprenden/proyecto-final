# NormaBot — Evaluación RAG/LLMs (Bootcamp Rubric)

**Fecha**: 2026-03-09
**Rama**: develop
**Commit**: 2148da95
**Nota**: Este documento evalúa la categoría RAG/LLMs. Para el estado operativo actual, ver NORMABOT_DIAGNOSIS.md y NORMABOT_PROGRESS.md.

---

## 1. Retrieval with Real Data (Not Hardcoded) — OK

### 1.1 ChromaDB Real Retrieval
**Status**: ✓ FUNCIONAL

**Evidence**:
- `src/retrieval/retriever.py:25-32`
  - PersistentClient lazy initialization
  - Collection name: `normabot_legal_chunks`
  - Actual query to ChromaDB: `collection.query(query_embeddings=[...], n_results=k)`

**Function Flow**:
1. `src/retrieval/retriever.py:166` — `search(query, mode="soft", k=DEFAULT_K)` is the main API
2. Routes to `search_base()` (line 113) or `search_soft()` (line 125)
3. Both call `_embed_query(query)` → `_get_embed_model().encode()`
4. Then call `_get_collection().query()` with real embeddings

**Key Details**:
- Embeddings are computed with `intfloat/multilingual-e5-base` (same model used for indexing)
- Query prefix: `f"query: {query}"` (E5 convention)
- Search mode "soft" prioritizes: exact article matches → source-based hits → semantic ranking
- Langfuse observability integrated (line 165: `@observe` decorator)

### 1.2 Data Pipeline Functional
**Status**: ✓ FUNCIONAL

**Evidence**:
- `data/ingest.py` (354 lines)
  - Reads HTML/PDF from `data/raw/` (4 sources: BOE, EU AI Act, AESIA, LOPD)
  - Chunks via regex patterns + RecursiveCharacterTextSplitter
  - Output: `data/processed/chunks_legal/chunks_final_all_sources.jsonl`

- `data/index.py` (124 lines)
  - Loads chunks from JSONL
  - Generates embeddings: `SentenceTransformer(MODEL_NAME).encode([...])`
  - Populates ChromaDB: `col.upsert(ids=..., documents=..., embeddings=..., metadatas=...)`

**Pipeline Verification** (data/ingest.py:340-348):
```python
max_chunk_size = max(sizes)  # Assert <= 2000 chars
min_chunk_size = min(sizes)  # Assert >= 80 chars
```

### 1.3 Retrieval from RAG Module
**Status**: ✓ FUNCIONAL

**Evidence** (`src/rag/main.py:51-82`):
```python
@observe(name="rag.retrieve")
def retrieve(query: str, k: int = 9) -> list[dict]:
    """Recupera documentos de ChromaDB y los formatea para grade()."""
    try:
        results = search(query, k=k, mode="soft")  # ← Real ChromaDB call
    except Exception:
        langfuse_context.update_current_observation(...)
        return []
    
    docs = [
        {
            "doc": r["text"],
            "metadata": r.get("metadata", {}),
            "score": max(0.0, 1.0 - r.get("distance", 1.0)),
        }
        for r in results
    ]
    return docs
```

**Key Points**:
- Calls `src.retrieval.retriever.search()` (real ChromaDB)
- Returns unfiltered list (filtering happens in `grade()`)
- Error handling: graceful fallback (returns empty list)
- Langfuse observable

---

## 2. Embeddings and Vector Store Functional — OK

### 2.1 Embeddings Model
**Status**: ✓ FUNCIONAL

**Evidence**:
- Model: `intfloat/multilingual-e5-base` (384-dim, multilingual)
- Used consistently in retriever: `src/retrieval/retriever.py:14`
- Used consistently in indexing: `data/index.py:24`

**E5 Convention Applied**:
- Query: `f"query: {text}"` (retriever.py:48)
- Document: `f"passage: {text}"` (data/index.py:45)

### 2.2 ChromaDB Vector Store
**Status**: ✓ FUNCIONAL

**Configuration**:
- Path: `data/processed/vectorstore/chroma`
- Client: `chromadb.PersistentClient(path=str(CHROMA_DIR))`
- Collection: `normabot_legal_chunks`
- Lazy initialization with thread-safe singleton (lock in retriever.py:22)

**Indexing Verification** (data/index.py:80-89):
```python
for start in range(0, n, BATCH_SIZE):
    end = min(start + BATCH_SIZE, n)
    col.upsert(
        ids=ids[start:end],
        documents=texts[start:end],
        embeddings=embeddings[start:end].tolist(),
        metadatas=metas[start:end],
    )
```

**Metadata Stored**:
- `source` (boe, eu_ai_act, aesia, lopd_rgpd)
- `unit_id` (article number or section ID)
- `unit_title` (human-readable label)
- `doc_title`, `doc_date`, `file` (source provenance)
- All used for re-ranking and citation

---

## 3. Document Grading (Relevance) — OK

### 3.1 Grading with LLM
**Status**: ✓ FUNCIONAL (with score-based fallback)

**Evidence** (`src/rag/main.py:90-148`):
```python
@observe(name="rag.grade")
def grade(query: str, docs: list[dict], threshold: float = 0.3) -> list[dict]:
    """Evalúa relevancia de cada documento con LLM local (Ollama).
    Fallback a filtro por score si Ollama no está disponible."""
    if not docs:
        return []
    
    try:
        llm = _get_grading_llm()  # Ollama Qwen 2.5 3B
    except Exception:
        logger.warning("Ollama no disponible, usando fallback por score")
        return _grade_by_score(docs, threshold)  # Fallback
    
    relevant = []
    for doc in docs:
        doc_text = doc["doc"][:MAX_DOC_CHARS_GRADING]  # 3000 chars
        prompt = GRADING_PROMPT.format(document=doc_text, query=query)
        try:
            response = llm.invoke(prompt)
            answer = response.content.strip().lower()
            if answer.startswith("si") or answer.startswith("sí"):
                relevant.append(doc)
        except Exception:
            logger.warning("Error en grading LLM, incluyendo doc por score")
            if doc["score"] >= threshold:
                relevant.append(doc)
    
    # Fallback if grader returns nothing
    if not relevant:
        relevant = _grade_by_score(docs, threshold)
        logger.warning("Grader devolvió 0 relevantes — fallback a filtro por score")
    
    return relevant
```

### 3.2 Ollama Configuration
**Status**: ✓ FUNCIONAL

**Evidence** (`src/rag/main.py:36-48`):
```python
def _get_grading_llm():
    """Devuelve el LLM local para grading (Qwen 2.5 3B via Ollama)."""
    global _grading_llm
    if _grading_llm is None:
        _grading_llm = ChatOllama(
            model="qwen2.5:3b",
            temperature=0,
            num_predict=10,  # Max 10 tokens ("si" or "no")
            num_ctx=4096,
        )
    return _grading_llm
```

**Grading Prompt** (src/rag/main.py:22-31):
- Permissive (responde "si" si el documento toca el tema)
- Only "no" if completely irrelevant
- Fallback: if Ollama crashes or model not found, use score threshold (0.3)

### 3.3 Fallback Mechanism
**Status**: ✓ FUNCIONAL

**Two-level Fallback**:
1. If Ollama unavailable → use `_grade_by_score()` (line 85-87)
2. If LLM call fails for a single doc → include if score >= threshold (line 124-126)
3. If grader returns 0 docs → fallback to score filter (line 130-131)

**Score Calculation** (src/rag/main.py:72):
```python
"score": max(0.0, 1.0 - r.get("distance", 1.0))
```
(Converts ChromaDB distance to [0,1] similarity)

---

## 4. Generation with LLM and Citation Handling — OK

### 4.1 Orchestrator LLM Integration
**Status**: ✓ FUNCIONAL

**Evidence** (`src/orchestrator/main.py:392-412`):
```python
def _build_agent():
    """Construye el agente ReAct con Bedrock Nova Lite, herramientas y memoria."""
    llm = ChatBedrockConverse(
        model=BEDROCK_MODEL_ID,  # eu.amazon.nova-lite-v1:0
        region_name=BEDROCK_REGION,
        temperature=0.0,
    )
    tools = [
        search_legal_docs,
        classify_risk,
        save_user_preference,
        get_user_preferences,
    ]
    return create_react_agent(
        llm,
        tools,
        prompt=SYSTEM_PROMPT,
        checkpointer=_get_checkpointer(),
        store=_get_store(),
        pre_model_hook=pre_model_hook,
    )
```

**LLM Stack**:
- **Orchestrator**: Bedrock Nova Lite v1 (generates final answer)
- **Grading**: Ollama Qwen 2.5 3B (local, for document relevance classification)
- **Both** observable via Langfuse

### 4.2 Citation Handling (Side-Channel)
**Status**: ✓ FUNCIONAL

**Pattern**: Citas transportadas via `_tool_metadata` ContextVar (no reformulated by LLM)

**Evidence** (`src/orchestrator/main.py:51-65`):
```python
_tool_metadata: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "tool_metadata", default=None
)

def _get_tool_metadata() -> dict[str, Any]:
    """Devuelve (o inicializa) el dict de metadatos de la invocación actual."""
    meta = _tool_metadata.get(None)
    if meta is None:
        meta = {"citations": [], "risk": None, "report": None}
        _tool_metadata.set(meta)
    return meta
```

**Where Citations Are Deposited** (`src/orchestrator/main.py:167-176`):
```python
@tool
@observe(name="tool.search_legal_docs")
def search_legal_docs(query: str) -> str:
    """Busca normativa, artículos, definiciones y conceptos legales..."""
    ...
    relevant = grade(query, docs)
    ...
    # Side-channel: depositar citas verificadas
    meta = _get_tool_metadata()
    for d in relevant:
        source_meta = d.get("metadata", {})
        if source_meta:
            meta["citations"].append({
                "source": source_meta.get("source", ""),
                "unit_title": source_meta.get("unit_title", ""),
                "unit_id": source_meta.get("unit_id", ""),
            })
    
    return format_context(relevant)
```

**Citation Rendering in UI** (`app.py:39-46`):
```python
citations = metadata.get("citations", [])
if citations:
    with st.expander(f"Fuentes legales verificadas ({len(citations)})"):
        for c in citations:
            unit = c.get("unit_title") or c.get("unit_id", "")
            label = f"{c.get('source', '')} - {unit}".strip(" -")
            if label:
                st.markdown(f"- {label}")
```

**Design Benefit**: 
- LLM sees formatted context (src/rag/main.py:151-160)
- LLM generates answer from that context
- Tool deposits verified citations in metadata (never reformulated)
- UI renders citations WITHOUT trusting LLM parsing

### 4.3 Context Formatting
**Status**: ✓ FUNCIONAL

**Evidence** (`src/rag/main.py:151-160`):
```python
def format_context(docs: list[dict]) -> str:
    """Formatea los documentos relevantes como contexto para el orchestrator."""
    blocks = []
    for i, d in enumerate(docs, 1):
        meta = d.get("metadata", {})
        source = meta.get("source", "")
        unit = meta.get("unit_title") or meta.get("unit_id", "")
        header = f"[{i}] {source} — {unit}".strip(" —")
        blocks.append(f"{header}\n{d['doc']}")
    return "\n\n".join(blocks)
```

**Flow**:
1. Retrieved docs passed to `grade()`
2. Relevant docs passed to `format_context()`
3. Formatted context returned to orchestrator tool
4. Orchestrator (Nova Lite) generates answer using this context

---

## 5. RAG Quality Evaluation (RAGAS) — OK

### 5.1 RAGAS Pipeline
**Status**: ✓ FUNCIONAL

**Evidence** (`eval/run_ragas.py` + `eval/helpers.py`):

**Phase A (Retriever)**: 
- Metrics: `context_precision` (>= 0.70), `context_recall` (>= 0.70)
- Source: `eval/helpers.py:293-351` (`run_ragas_retriever()`)

**Phase B (E2E)**:
- Metrics: `faithfulness` (>= 0.80)
- Source: `eval/helpers.py:354-406` (`run_ragas_e2e()`)

### 5.2 Dataset
**Status**: ✓ FUNCIONAL

**Evidence** (`eval/dataset.json`, 50+ examples):
- `question`: Legal question in Spanish
- `ground_truth`: Authoritative answer from EU AI Act articles
- `contexts`: Reference documents (from actual EU AI Act text)

**Example from dataset.json (line 1-8)**:
```json
{
  "question": "¿Qué prácticas de IA están prohibidas según el EU AI Act?",
  "ground_truth": "El artículo 5 del EU AI Act prohíbe...",
  "contexts": ["Reglamento (UE) 2024/1689... Artículo 5..."]
}
```

### 5.3 Metrics Computation
**Status**: ✓ FUNCIONAL

**Phase A Flow** (`eval/helpers.py:41-90`):
```python
def get_retriever_rows(dataset: list[dict]) -> list[dict]:
    """Recupera y clasifica documentos para cada pregunta sin invocar al agente."""
    for idx, item in enumerate(dataset, 1):
        question = item["question"]
        docs = retrieve(question)  # Real retrieval
        relevant = grade(question, docs)  # Real grading
        contexts = [d["doc"] for d in relevant]
        rows.append({
            "question": question,
            "contexts": contexts,
            "ground_truth": item["ground_truth"],
        })
    return rows
```

**Phase B Flow** (`eval/helpers.py:93-181`):
```python
def get_agent_answers(dataset, retriever_rows=None):
    """Invoca el agente para cada pregunta del dataset y recoge la respuesta."""
    for idx, item in enumerate(dataset, 1):
        question = item["question"]
        if use_agent:
            result = agent_run(question, session_id=f"eval-{uuid.uuid4().hex[:8]}")
            answer = result["messages"][-1].content
        else:
            answer = item.get("ground_truth", "")
        
        # Reutilizar contextos de Phase A para comparabilidad
        if question in retriever_index:
            contexts = retriever_index[question]
        ...
        rows.append({
            "question": question,
            "answer": answer,
            "contexts": contexts,
            "ground_truth": item["ground_truth"],
        })
    return rows
```

### 5.4 RAGAS LLM Configuration
**Status**: ✓ FUNCIONAL (with Nova Lite JSON workaround)

**Evidence** (`eval/helpers.py:219-270`):
```python
def get_ragas_llm():
    """Devuelve un LLM compatible con RAGAS usando Bedrock Nova Lite."""
    from langchain_aws import ChatBedrockConverse
    from ragas.llms import LangchainLLMWrapper
    
    class _NovaChatWrapper(ChatBedrockConverse):
        """Subclase que normaliza el JSON de Nova Lite para RAGAS."""
        
        def _clean(self, result):
            cleaned = []
            for gen in result.generations:
                if isinstance(gen, ChatGeneration):
                    clean_text = _fix_nova_json(gen.message.content)
                    new_msg = AIMessage(content=clean_text, ...)
                    cleaned.append(ChatGeneration(text=clean_text, message=new_msg, ...))
            result.generations = cleaned
            return result
        
        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            return self._clean(super()._generate(...))
        
        async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
            return self._clean(await super()._agenerate(...))
    
    llm = _NovaChatWrapper(
        model=os.getenv("BEDROCK_MODEL_ID", "eu.amazon.nova-lite-v1:0"),
        region_name=os.getenv("AWS_REGION", "eu-west-1"),
        temperature=0.0,
    )
    return LangchainLLMWrapper(llm)
```

**JSON Normalization Fix** (`eval/helpers.py:188-216`):
```python
def _fix_nova_json(text: str) -> str:
    """Corrige el JSON que devuelve Nova Lite para que RAGAS pueda parsearlo."""
    # Nova Lite confunde el formato con JSON Schema y devuelve:
    # {"properties": {"statements": [...]}, "type": "object"}
    # en vez de:
    # {"statements": [...]}
    
    text = re.sub(r"```(?:json)?\s*([\s\S]*?)```", r"\1", text).strip()
    
    try:
        data = json.loads(text)
        if (isinstance(data, dict) and 
            isinstance(data.get("properties"), dict) and 
            data.get("type") == "object"):
            return json.dumps(data["properties"])
    except (json.JSONDecodeError, ValueError):
        pass
    
    return text
```

### 5.5 Thresholds and KPIs
**Status**: ✓ FUNCIONAL

**Evidence** (`eval/helpers.py:14-28`):
```python
THRESHOLDS_RETRIEVER = {
    "context_precision": 0.70,
    "context_recall": 0.70,
}

THRESHOLDS_E2E = {
    "faithfulness": 0.80,
}

THRESHOLDS = {**THRESHOLDS_RETRIEVER, **THRESHOLDS_E2E}
```

**Metrics Logged to**:
- MLflow: `eval/helpers.py:408-461` (`log_to_mlflow()`)
- Langfuse: `eval/helpers.py:463-495` (`log_to_langfuse()`)

### 5.6 Caching and Rate-Limit Mitigation
**Status**: ✓ FUNCIONAL

**Evidence** (`eval/helpers.py:498-531`):
```python
def save_answers_cache(rows: list[dict], git_sha: str, suffix: str = "") -> Path:
    """Guarda filas en caché para evitar re-ejecutar el retriever o el agente."""
    tag = f"_{suffix}" if suffix else ""
    cache_path = Path(__file__).parent / f"answers_cache_{git_sha[:8]}{tag}.json"
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump({"git_sha": git_sha, "rows": rows}, f, ...)
    return cache_path

def load_answers_cache(git_sha: str, suffix: str = "") -> list[dict] | None:
    """Carga caché si existe y coincide el SHA. Devuelve None si no hay caché."""
    tag = f"_{suffix}" if suffix else ""
    cache_path = Path(__file__).parent / f"answers_cache_{git_sha[:8]}{tag}.json"
    if not cache_path.exists():
        return None
    with open(cache_path, encoding="utf-8") as f:
        data = json.load(f)
    if data.get("git_sha") != git_sha:
        logger.warning("Caché obsoleta — ignorando")
        return None
    return data["rows"]
```

**Flow** (`eval/run_ragas.py:70-73`):
```python
retriever_rows = load_answers_cache(git_sha, suffix="retriever")
if retriever_rows is None:
    retriever_rows = get_retriever_rows(dataset)
    save_answers_cache(retriever_rows, git_sha, suffix="retriever")
```

**Benefit**: Cache per git SHA ensures consistent comparisons; avoids re-running expensive retrieval/agent calls.

### 5.7 Error Handling
**Status**: ✓ FUNCIONAL

**Evidence** (`eval/run_ragas.py:75-82`):
```python
try:
    retriever_metrics = run_ragas_retriever(build_ragas_dataset(retriever_rows))
except Exception as e:
    logger.error("Error en Phase A (retriever): %s", e)
    if ci_mode:
        return 1
    retriever_metrics = {"context_precision": float("nan"), "context_recall": float("nan")}
```

**Threshold Check** (`eval/helpers.py:534-550`):
```python
def check_thresholds(metrics: dict) -> list[str]:
    """Comprueba si alguna métrica está por debajo del umbral."""
    failures = []
    for metric, threshold in THRESHOLDS.items():
        if metric not in metrics:
            continue
        value = metrics[metric]
        if np.isnan(value):
            failures.append(f"{metric}: NaN (métrica no calculada correctamente)")
        elif value < threshold:
            failures.append(f"{metric}: {value:.4f} < {threshold} (umbral mínimo)")
    return failures
```

---

## 6. Summary Table

| Component | Status | File Path | Key Evidence |
|-----------|--------|-----------|--------------|
| **Real Retrieval** | ✓ OK | `src/retrieval/retriever.py:166` | `search()` calls ChromaDB PersistentClient with real embeddings |
| **Embeddings Model** | ✓ OK | `src/retrieval/retriever.py:14` | `intfloat/multilingual-e5-base` (384-dim, E5 convention) |
| **Vector Store** | ✓ OK | `src/retrieval/retriever.py:25-32` | ChromaDB PersistentClient, lazy init, thread-safe |
| **Document Grading** | ✓ OK | `src/rag/main.py:90-148` | Ollama Qwen 2.5 3B, fallback to score threshold |
| **LLM Generation** | ✓ OK | `src/orchestrator/main.py:394-398` | Bedrock Nova Lite v1, ReAct agent |
| **Citation Handling** | ✓ OK | `src/orchestrator/main.py:51-176` | Side-channel metadata (ContextVar), not reformulated by LLM |
| **RAGAS Phase A** | ✓ OK | `eval/helpers.py:293-351` | Context Precision + Recall (KPI >= 0.70) |
| **RAGAS Phase B** | ✓ OK | `eval/helpers.py:354-406` | Faithfulness (KPI >= 0.80) |
| **Dataset** | ✓ OK | `eval/dataset.json` | 50+ examples with ground truth |
| **Caching** | ✓ OK | `eval/helpers.py:498-531` | Answers cached by git SHA |

---

## 7. Known Limitations and Design Decisions

### 7.1 Ollama Grading (Local LLM)
- **Why**: Avoids API keys, rate limits, network latency for binary classification (5 calls/query)
- **Model**: Qwen 2.5 3B (chosen over Llama 3.2 3B and Gemma 2 2B for Spanish support)
- **Fallback**: If Ollama unavailable, uses score threshold (0.3)
- **Trade-off**: Requires local Ollama running (`brew services start ollama` on macOS)

### 7.2 Citation Side-Channel
- **Why**: Prevents LLM hallucinating or reformulating legal citations
- **Method**: ContextVar `_tool_metadata` transports citations outside LLM context
- **Result**: UI renders verified citations from tool outputs, not from LLM parsing
- **Benefit**: Citations sourced directly from ChromaDB metadata, not reformulated by LLM (minimizes hallucination risk)

### 7.3 RAGAS Metrics
- **Phase A (retriever)**: Evaluates **context precision** (retrieved docs are relevant) + **context_recall** (relevant docs are retrieved)
  - Threshold: >= 0.70 each
  - Does NOT require Bedrock for questions/contexts, but DOES require it for LLM-based evaluation
- **Phase B (E2E)**: Evaluates **faithfulness** (answer grounded in context)
  - Threshold: >= 0.80
  - Requires full agent response
- **Excluded**: `answer_relevancy` metric — Nova Lite incompatible with RAGAS prompt format

### 7.4 Nova Lite JSON Workaround
- **Issue**: Nova Lite wraps metrics output in JSON Schema format
- **Solution**: `_fix_nova_json()` normalizes `{"properties": {...}, "type": "object"}` → `{...}`
- **Status**: Workaround applied, metrics compute correctly

---

## 8. Comparison vs. Previous Diagnosis (2026-02-27)

**No changes to RAG/LLM stack since last audit**:
- ✓ Retriever: `src/retrieval/retriever.py` unchanged (184 lines)
- ✓ RAG grade/retrieve: `src/rag/main.py` unchanged (175 lines)
- ✓ RAGAS evaluation: Completed Phase A+B with caching (2026-03-07 → 2026-03-09)

**What Changed Upstream**:
- Orchestrator: +209 lines (memory + metadata side-channel for citations)
- Report module eliminated (was redundant, now deterministic `src/checklist/main.py`)
- App.py: +58 lines (citation rendering)

**Result**: RAG quality evaluation framework fully operational with caching and rate-limit mitigation.

---

## 9. Conclusion

**RAG/LLMs Category**: **FULLY FUNCTIONAL** ✓

- Real retrieval with ChromaDB (not hardcoded)
- Functional embeddings and vector store
- Document grading with LLM + graceful fallback
- Generation with LLM + verified citations
- RAGAS evaluation with Phase A+B + caching
- Known limitations documented and addressed

**Recommendation**: Ready for bootcamp evaluation. All components demonstrated working (smoke tests pass, eval pipeline executable).

