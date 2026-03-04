# NormaBot — Analisis de causa raiz: bugs E2E

## Bug: Doble llamada al clasificador

**Estado**: Resuelto
**Detectado en**: Q4 via Langfuse
**Impacto**: Latencia duplicada en clasificacion, spans redundantes en trazas

### Evidencia (Langfuse)

Dos spans `classifier.predict_risk` con el mismo input, separados por 11ms:

| Span ID      | startTime           | Nota      |
|--------------|---------------------|-----------|
| `dc6dc9a3`   | 16:52:48.713Z       | original  |
| `ed12a05b`   | 16:52:48.724Z       | duplicado |

### Causa raiz

Cuando la query del usuario activaba multiples tools (ej: "Clasifica un sistema de scoring crediticio y dime que articulos aplican"):

1. **Bedrock Nova Lite devolvia 2+ tool_calls en un solo `AIMessage`** — tipicamente `classify_risk` + `generate_report`.
2. **LangGraph `ToolNode` ejecutaba TODOS los tool_calls en paralelo** — comportamiento por diseno de `create_react_agent`.
3. **Ambos tools invocaban `predict_risk` internamente**:
   - `classify_risk` → `_cached_predict_risk()` → `predict_risk()`
   - `generate_report` → `_cached_predict_risk()` → `predict_risk()`
4. **`lru_cache` NO protege contra ejecucion concurrente** — ambos threads veian cache miss porque ninguno habia retornado aun.
5. **Resultado**: dos spans `classifier.predict_risk` con el mismo input.

### Por que `lru_cache` no basta

`functools.lru_cache` es thread-safe para lectura/escritura del dict interno, pero **no bloquea llamadas concurrentes para la misma key**:

```
Thread A: lru_cache("scoring...") → cache MISS → ejecuta predict_risk() ...
Thread B: lru_cache("scoring...") → cache MISS (A no termino) → ejecuta predict_risk() ...
Thread A: ... retorna → guarda en cache
Thread B: ... retorna → sobreescribe cache (mismo valor)
```

### Por que no se resuelve a nivel Bedrock

`ChatBedrockConverse` **no soporta `parallel_tool_calls=False`** (parametro exclusivo de OpenAI). La API Converse de Bedrock solo expone `toolChoice` (`auto`/`any`/specific tool).

### Resolucion: eliminar `generate_report`, enriquecer `classify_risk`

**Problema de fondo**: `generate_report` era un tool redundante — llamaba a un segundo LLM (Bedrock) para formatear informes, cuando el agente ReAct ya usa el mismo modelo. Ademas, internamente llamaba al clasificador y al retriever, duplicando trabajo de los otros tools.

**Solucion aplicada**: Eliminar `generate_report` como tool y enriquecer `classify_risk` para que devuelva clasificacion + checklist de cumplimiento completo. El agente ReAct queda con 2 tools:

- `search_legal_docs` — RAG sobre el corpus legal
- `classify_risk` — Clasificacion ML + checklist determinista (sin LLM)

El checklist (`src/checklist/main.py`) usa:
- **SHAP top features** → recomendaciones especificas mapeadas al Anexo III
- **Distribucion de probabilidades** → deteccion de casos borderline
- **Mapping determinista** risk_level → obligaciones legales (Arts. 5, 9-15, 43, 50, 95)

Flujo anterior (causaba doble llamada):
```
LLM → tool_calls en paralelo:
  classify_risk("scoring...")     → predict_risk() ← span 1
  generate_report("scoring...")   → predict_risk() ← span 2 (duplicado)
                                  → Bedrock LLM (redundante)
```

Flujo nuevo (un solo tool con clasificacion):
```
LLM → classify_risk("scoring...") → predict_risk() + checklist determinista
LLM → search_legal_docs(...)      → RAG (solo si necesita contexto legal)
LLM → sintetiza respuesta final
```

### Archivos involucrados

| Archivo | Cambio |
|---------|--------|
| `src/orchestrator/main.py` | Eliminado `generate_report`, enriquecido `classify_risk` |
| `src/checklist/__init__.py` | Nuevo modulo |
| `src/checklist/main.py` | Logica determinista de checklist (obligaciones, SHAP, borderline) |
| `src/report/main.py` | Eliminado (sin callers tras el refactor) |
| `tests/test_checklist.py` | Tests unitarios del checklist |
| `tests/test_orchestrator.py` | Actualizado para 2 tools |
| `app.py` | Sidebar actualizado |
