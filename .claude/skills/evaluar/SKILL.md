---
name: evaluar
description: >
  Auto-evaluación del proyecto NormaBot contra los criterios de un bootcamp de ML/IA.
  Revisa el proyecto como lo haría un evaluador externo e identifica gaps para la
  presentación. Usar antes de la entrega para saber dónde estamos respecto a la rúbrica.
allowed-tools: Read, Glob, Grep, Bash, AskUserQuestion
---

# Auto-Evaluación — NormaBot

Evalúa el proyecto como lo haría un tribunal de bootcamp de ML/IA.

## Argumentos

$ARGUMENTS

## Rúbrica de Evaluación

Lee `docs/evaluacion/rubric.md` si existe. Si no, usa esta rúbrica genérica de bootcamp:

### Categorías de evaluación

#### 1. Producto funcional (30%)
- [ ] El sistema responde preguntas legales con citas reales
- [ ] El clasificador clasifica sistemas de IA por riesgo
- [ ] Se generan informes de cumplimiento
- [ ] La UI es usable y el flujo es coherente
- [ ] Hay un demo funcional end-to-end

#### 2. ML/NLP (25%)
- [ ] Pipeline de ML completo (datos → features → modelo → evaluación)
- [ ] Justificación de elecciones técnicas (por qué XGBoost, por qué TF-IDF)
- [ ] Métricas de evaluación apropiadas (no solo accuracy)
- [ ] Manejo de datos desbalanceados
- [ ] Explicabilidad (SHAP u otra técnica)

#### 3. RAG / LLMs (20%)
- [ ] RAG implementado con retrieval real (no hardcoded)
- [ ] Embeddings y vector store funcionales
- [ ] Grading de documentos (relevancia)
- [ ] Generación con LLM y citas
- [ ] Evaluación de calidad del RAG (RAGAS o similar)

#### 4. MLOps / Ingeniería (15%)
- [ ] CI/CD funcional
- [ ] Tests automatizados
- [ ] Tracking de experimentos (MLflow)
- [ ] Containerización (Docker)
- [ ] Observabilidad (Langfuse o similar)

#### 5. Presentación / Documentación (10%)
- [ ] Documentación clara del proyecto
- [ ] Decisiones técnicas documentadas
- [ ] README actualizado
- [ ] Diagrama de arquitectura
- [ ] Demo preparada

## Proceso de evaluación

### 1. Escanear el proyecto

Para cada categoría, revisa el código real (no la documentación) y marca cada
punto como:
- **OK**: Implementado y funcional
- **PARCIAL**: Existe pero incompleto o con limitaciones
- **FALTA**: No implementado
- **N/A**: No aplica

### 2. Puntuar

Asigna una puntuación estimada por categoría (0-10) basada en lo que realmente
funciona en el código.

### 3. Identificar gaps críticos

Lista los 3-5 gaps más importantes que afectan la nota, ordenados por:
1. Impacto en la puntuación
2. Esfuerzo para cerrar
3. Tiempo restante

### 4. Generar recomendaciones

Para cada gap, propón:
- Qué hacer (concreto, con archivos y funciones)
- Quién debería hacerlo (del equipo)
- Cuánto esfuerzo (S/M/L)
- Si es alcanzable antes del 12 de marzo

### 5. Formato de salida

```markdown
## Auto-Evaluación NormaBot — [fecha]

### Puntuación estimada

| Categoría | Peso | Puntuación | Notas |
|-----------|------|-----------|-------|
| Producto funcional | 30% | X/10 | ... |
| ML/NLP | 25% | X/10 | ... |
| RAG/LLMs | 20% | X/10 | ... |
| MLOps/Ingeniería | 15% | X/10 | ... |
| Presentación/Docs | 10% | X/10 | ... |
| **TOTAL** | | **X/10** | |

### Gaps críticos
[lista priorizada]

### Plan de acción para subir nota
[recomendaciones concretas]
```

## Regla importante

Sé honesto y constructivo. El objetivo no es desmoralizar al equipo sino darles
una hoja de ruta clara para maximizar la nota en el tiempo restante.
