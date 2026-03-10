# Plan: Integrar Bedrock Nova Lite en route_query del orquestador

## Contexto

El nodo `route_query` en `src/agents/graph.py` clasifica la query del usuario en 3 categorías (`rag`, `classifier`, `report`) usando una heurística de keywords. Se quiere reemplazar por una llamada a un LLM para mejorar la clasificación de intenciones.

**Decisión**: Amazon Bedrock con Nova Lite v1.
- Sin API keys de terceros (usa IAM de AWS ya configurado).
- Coste ~$6.60/mes para 1000 queries/día.
- Sin infraestructura adicional que gestionar.
- Modelo: `eu.amazon.nova-lite-v1:0` (inference profile EU, datos en la UE).
- Soporta tool calling, lo que permite evolucionar a un orquestador agéntico (ReAct) en el futuro.

---

## Archivos a modificar

| Archivo | Cambio |
|---|---|
| `requirements.txt` | Añadir `langchain-aws>=0.2.9` |
| `src/agents/graph.py` | Reemplazar `route_query` con llamada a Bedrock |
| `infra/terraform/iam-bedrock.tf` | Nueva política IAM para Bedrock (devs) |
| `tests/test_route_query.py` | Crear tests unitarios e integración |

---

## Paso 1: Dependencia

Añadir a `requirements.txt`:
```
langchain-aws>=0.2.9
```

---

## Paso 2: IAM — Política de Bedrock

Nuevo archivo `infra/terraform/iam-bedrock.tf` con:
- Política `NormaBot-Bedrock-Invoke-Policy`:
  - `bedrock:InvokeModel` y `bedrock:InvokeModelWithResponseStream` sobre:
    - `arn:aws:bedrock:eu-west-1:<account_id>:inference-profile/eu.amazon.nova-lite-v1:0`
  - `bedrock:GetInferenceProfile` sobre el inference profile
- Attach al grupo `NormaBot-Devs` (desarrollo local)

---

## Paso 3: Código — `src/agents/graph.py`

### 3.1 Nuevos imports
```python
import logging
import os
from langchain_aws import ChatBedrockConverse
from langchain_core.messages import HumanMessage, SystemMessage
```

### 3.2 Configuración
```python
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "eu.amazon.nova-lite-v1:0")
BEDROCK_REGION = os.environ.get("AWS_REGION", "eu-west-1")
VALID_ROUTES = {ROUTE_RAG, ROUTE_CLASSIFIER, ROUTE_REPORT}
DEFAULT_ROUTE = ROUTE_RAG
```

### 3.3 Prompt del sistema
Prompt en español que:
- Describe las 3 categorías con ejemplos concretos de queries.
- Instruye responder ÚNICAMENTE con una palabra: `rag`, `classifier` o `report`.
- Categorías:
  - `rag`: preguntas sobre normativa, artículos, definiciones, conceptos legales.
  - `classifier`: clasificar un sistema de IA concreto por nivel de riesgo.
  - `report`: generar informe de cumplimiento para un sistema.

### 3.4 Inicialización LLM
- Singleton lazy (`_router_llm`) — no se crea en import, solo en primer uso.
- `ChatBedrockConverse(model=..., region_name=..., temperature=0.0, max_tokens=10)`

### 3.5 Parsing de respuesta (`_parse_route`)
1. Match exacto (respuesta es literalmente una de las 3 rutas).
2. Substring match (el LLM añadió texto extra).
3. Fallback a `rag` si no se reconoce nada + log warning.

### 3.6 Nueva `route_query`
- Llama al LLM con `SystemMessage` + `HumanMessage(query)`.
- Parsea la respuesta con `_parse_route`.
- **Si falla** (excepción): cae a `_fallback_route` que es la heurística actual de keywords.
- Log de la decisión tomada.

### 3.7 `_fallback_route`
La heurística actual de keywords se conserva como fallback en caso de error de Bedrock.

---

## Paso 4: Tests — `tests/test_route_query.py`

- **TestParseRoute**: tests puros de parsing (sin LLM, sin AWS).
  - Match exacto, con whitespace, con texto extra, case insensitive, fallback.
- **TestFallbackRoute**: tests de la heurística de keywords.
- **TestRouteQueryWithMock**: mock del LLM para verificar el flujo completo.
  - Ruta feliz: LLM responde correctamente.
  - Error: LLM falla, cae a fallback.
- **test_route_query_live** (`@pytest.mark.integration`): test real contra Bedrock con queries de ejemplo.

---

## Paso 5: Activar modelo en Bedrock (manual)

En la consola AWS > Bedrock > Model access > eu-west-1: habilitar Amazon Nova Lite. Es instantáneo para modelos de Amazon.

---

## Verificación

1. `pip install -r requirements.txt`
2. `pytest tests/test_route_query.py -v` (tests unitarios, sin AWS)
3. `python -m src.orchestrator.main` (smoke test con 3 queries reales)
4. Verificar en logs que las rutas son correctas:
   - "¿Qué dice el artículo 5 del EU AI Act?" -> `rag`
   - "Clasifica mi sistema de reconocimiento facial" -> `classifier`
   - "Genera un informe de cumplimiento para mi chatbot" -> `report`

---

## Arquitectura del orquestador: grafo determinista vs agente

### Opción A: Grafo determinista + LLM clasificador (implementación actual)

```
START -> route_query (LLM clasifica) -> agente elegido -> synthesize -> END
```

- El LLM solo clasifica la query en 3 categorías. El grafo sigue un camino fijo.
- 1 sola llamada al LLM por query.
- No maneja multi-intent (ej: "Clasifica mi sistema y genera un informe" -> solo va a uno).
- Modelo mínimo: Nova Micro v1.
- Coste estimado: ~$0.19/mes para 1000 queries/día.

### Opción B: Orquestador agéntico (ReAct + tool calling)

```
START -> LLM (piensa) -> herramienta A -> LLM (ve resultado) -> herramienta B -> ... -> END
```

- El LLM razona, elige herramientas, ve resultados y decide el siguiente paso.
- 3-5 llamadas al LLM por query.
- Maneja multi-intent y casos ambiguos.
- Modelo mínimo: **Nova Lite v1** (tool calling fiable).
- Coste estimado: ~$6.60/mes para 1000 queries/día.
- Se implementa con `create_react_agent` de LangGraph + tools.

### Comparación Bedrock vs modelo local (para agente)

| | Bedrock Nova Lite v1 | Local (Ollama + Llama 3.1 8B) |
|---|---|---|
| Coste/mes (1K queries/día) | ~$6.60 | ~$30-60 (EC2 t3.medium/large) |
| Infra | Ninguna | Docker + gestión de modelo |
| Latencia por llamada | ~200-500ms | ~1-3s (CPU) |
| Tool calling | Fiable | Poco fiable en modelos <8B |
| RAM necesaria | 0 (serverless) | 4-8GB mínimo |

Bedrock sigue siendo más barato para el volumen esperado. El break-even con local sería a ~140K queries/día.

### Decisión

Se elige **Nova Lite v1** como modelo único. Permite comenzar con la Opción A (grafo determinista) y evolucionar a Opción B (agente ReAct) sin cambiar de modelo ni de política IAM, ya que Nova Lite v1 soporta tool calling.

Bedrock es la mejor opción frente a un modelo local dado el volumen y la infraestructura disponible (EC2 free tier 1GB).

---

## Notas

- Nova Lite no está nativamente en eu-west-1, pero el inference profile EU (`eu.amazon.nova-lite-v1:0`) redirige transparentemente a regiones EU. Los datos no salen de la UE.
- Se puede cambiar de modelo cambiando solo la variable de entorno `BEDROCK_MODEL_ID`.
- `langchain-aws >= 0.2.9` recomendado (fix de issue #604 con inference profiles).

### Modelos descartados

| Modelo | Razón |
|---|---|
| Nova Micro v1 | $0.035/1M tokens, más barato pero sin soporte fiable de tool calling. No permite evolucionar a agente |
| Nova 2 Pro | Preview, no apto para producción |
| Nova 2 Sonic | Speech-to-speech, no aplica (input es texto) |
| Nova Act | Servicio de automatización de navegador, no es un modelo Bedrock |
| Nova Premier | Sin inference profile EU (datos saldrían de la UE). $2.50/1M tokens |
| Nova Pro v1 | $0.80/1M tokens, overkill para clasificación/tool calling simple |
