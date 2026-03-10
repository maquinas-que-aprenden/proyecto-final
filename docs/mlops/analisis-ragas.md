# Análisis RAGAS — NormaBot

**Fecha:** 2026-03-10
**Datos:** [`datos-ragas/2026-03-10-logs_ragas.txt`](datos-ragas/2026-03-10-logs_ragas.txt) (Run 1) y [`datos-ragas/2026-03-10-logs_ragas_2.txt`](datos-ragas/2026-03-10-logs_ragas_2.txt) (Run 2)
**Dataset:** 14 ejemplos | **LLM evaluador:** Amazon Bedrock Nova Lite (`eu.amazon.nova-lite-v1:0`, `eu-west-1`) | **Embeddings:** `intfloat/multilingual-e5-base` (local)

---

## Resumen ejecutivo

Se realizaron dos ejecuciones de evaluación RAGAS. **Los números finales no son concluyentes**: la mayoría de los ejemplos producen NaN y quedan excluidos del cálculo de la media, lo que hace que los scores agregados no sean representativos del sistema completo. La única métrica interpretable es context_recall, que falla el umbral en ambos runs (0.44–0.52 vs. umbral 0.70), señalando gaps reales de cobertura en el corpus.

Para obtener métricas válidas se necesita cambiar el LLM evaluador (Nova Lite no es compatible con los prompts de RAGAS) y ampliar el dataset de evaluación.

---

## Configuración de cada run

| | Run 1 | Run 2 |
|---|---|---|
| Commit | `b7302ae` | `a9d7c56` |
| `RunConfig.max_workers` | 16 (por defecto) | 2 |
| Objetivo | Baseline | Reducir throttling de Bedrock |

---

## Resultados por métrica

> **Los scores finales son `nanmean`**: la media ignorando los NaN. Cuando una pregunta produce NaN, desaparece del cálculo sin dejar rastro en el número final — el resultado aparece igual de preciso que si se hubieran evaluado los 14 ejemplos, pero no lo es.
>
> El sesgo no es aleatorio: Nova Lite falla el prompt JSON de RAGAS principalmente en respuestas largas y estructuradas (listas, múltiples artículos citados), que son exactamente las preguntas más complejas y representativas del sistema. **Los casos más difíciles — donde el riesgo de alucinación es mayor — son los que quedan fuera del cálculo.**

| Métrica | Run 1 | Válidos | Run 2 | Válidos | Umbral | Estado |
|---------|-------|---------|-------|---------|--------|--------|
| context_precision | 1.0000 | 5/14 (36%) | 0.8571 | 7/14 (50%) | 0.70 | No evaluable |
| context_recall | 0.5179 | 13/14 (93%) | 0.4429 | 14/14 (100%) | 0.70 | ✗ |
| faithfulness | 0.5509 | 3/14 (21%) | 0.6484 | 5/14 (36%) | 0.80 | No evaluable |

Context recall es la única métrica con cobertura suficiente para ser interpretable. Context precision y faithfulness tienen demasiados NaN para que el nanmean sea útil.

---

## Causas de los NaN

Hay dos causas distintas:

**1. ThrottlingException** (Run 1: 17 errores, Run 2: 1 error): RAGAS lanzaba hasta 28 llamadas simultáneas a Bedrock. Nova Lite en `eu-west-1` tiene un rate limit bajo y rechazaba la mayoría. Para Run 2 se redujo la concurrencia a `max_workers=2`, lo que eliminó casi todos los errores de throttling. El pipeline tardó más (Phase A: 1m18s → 3m03s) pero la cobertura mejoró.

**2. OutputParserException — fallo estructural** (Run 1: 7 errores, Run 2: 9 errores en Phase B): Nova Lite devuelve texto en prosa en lugar del JSON que RAGAS espera. Esto no mejora reduciendo la concurrencia — es un problema de incompatibilidad entre el modelo y el framework. Afecta principalmente a Faithfulness (Phase B) y es la causa principal de que el 64% de los ejemplos sean NaN incluso en Run 2.

| Tipo de error | Phase A R1 | Phase A R2 | Phase B R1 | Phase B R2 |
|---------------|-----------|-----------|-----------|-----------|
| ThrottlingException | 10 | 1 | 7 | 0 |
| OutputParserException | 1 | 7 | 6 | 9 |

---

## Análisis por pregunta — Phase A (Retriever)

La columna "docs" indica cuántos pasó el grader de Qwen 2.5 3B. Con 9/9 se activó el fallback por score (el grader no encontró ningún documento relevante).

| # | Pregunta (resumida) | Docs | prec R1 | rec R1 | prec R2 | rec R2 | Observación |
|---|---------------------|------|---------|--------|---------|--------|-------------|
| 1 | Prácticas IA prohibidas (EU AI Act) | 9/9 (fallback) | 1.000 | 0.750 | 1.000 | 0.750 | Estable entre runs |
| 2 | IA de alto riesgo | 1/9 | 1.000 | 0.500 | 1.000 | 0.500 | Estable; solo 1 doc relevante |
| 3 | Sistema de gestión de riesgos | 3/9 | NaN | 0.750 | 1.000 | 0.750 | Run 1: throttling. Run 2: prec válida |
| 4 | Gobernanza de datos | 9/9 (fallback) | NaN | 0.750 | NaN | 0.750 | Precision no evaluada en ambos runs |
| 5 | Supervisión humana (EU AI Act) | 1/9 | 1.000 | 0.200 | 1.000 | 0.200 | Recall bajo: solo 1 doc, ground_truth amplio |
| 6 | Obligación de informar (transparencia) | 3/9 | NaN | 1.000 | NaN | 1.000 | Precision no evaluada; recall perfecto |
| 7 | Multas por incumplimiento | 9/9 (fallback) | NaN | 1.000 | NaN | 0.800 | Recall ligeramente peor en Run 2 |
| 8 | LOPD-GDD: evaluaciones de impacto | 2/9 | NaN | 0.000 | NaN | 0.000 | **Recall 0 en ambos runs: gap de cobertura** |
| 9 | Anexo III EU AI Act | 9/9 (fallback) | NaN | 0.000 | **0.000** | 0.000 | **prec=0 y rec=0: retriever no encuentra nada útil** |
| 10 | Obligaciones proveedores alto riesgo | 9/9 (fallback) | NaN | 0.750 | NaN | 0.250 | Recall cae en Run 2; inestabilidad entre runs |
| 11 | Competencias AESIA | 1/9 | NaN | 0.333 | 1.000 | **1.000** | Mejora real en Run 2: precision y recall perfectos |
| 12 | DPO en prestadores de IA | 9/9 (fallback) | NaN | NaN | NaN | 0.000 | **Recall 0: gap de cobertura en corpus** |
| 13 | Plan vigilancia poscomercialización | 9/9 (fallback) | NaN | 0.500 | NaN | 0.000 | Recall cae a 0 en Run 2 |
| 14 | Intervención humana en decisiones | 1/9 | 1.000 | 0.200 | 1.000 | 0.200 | Estable; recall bajo sistemático |

---

## Análisis por pregunta — Phase B (Faithfulness)

| # | Pregunta (resumida) | faith R1 | faith R2 | Observación |
|---|---------------------|----------|----------|-------------|
| 1 | Prácticas IA prohibidas | 0.778 | NaN | Nova Lite devolvió prosa en R2 |
| 2 | IA de alto riesgo | NaN | **0.833** | Throttling en R1; evaluado en R2 |
| 3 | Sistema de gestión de riesgos | NaN | NaN | Fallo estructural ambos runs |
| 4 | Gobernanza de datos | NaN | NaN | Fallo estructural ambos runs |
| 5 | Supervisión humana | NaN | NaN | Fallo estructural ambos runs |
| 6 | Obligación de informar | NaN | NaN | Fallo estructural ambos runs |
| 7 | Multas por incumplimiento | NaN | **0.800** | Throttling en R1; evaluado en R2 |
| 8 | LOPD-GDD: evaluaciones de impacto | NaN | **0.636** | Throttling en R1; evaluado en R2 |
| 9 | Anexo III EU AI Act | NaN | **0.083** | Throttling en R1; score muy bajo en R2 (contextos sin filtrar) |
| 10 | Obligaciones proveedores | NaN | NaN | Fallo estructural ambos runs |
| 11 | Competencias AESIA | **0.875** | **0.889** | Consistente y alto en ambos runs |
| 12 | DPO en prestadores de IA | NaN | NaN | Fallo estructural ambos runs |
| 13 | Plan vigilancia poscomercialización | NaN | NaN | Fallo estructural ambos runs |
| 14 | Intervención humana en decisiones | **0.000** | NaN | Nova Lite devolvió prosa en R2 |

---

## Conclusiones

**1. Los scores agregados no son válidos para comparar contra umbrales.** Context precision y faithfulness se calculan sobre el 36–50% de los ejemplos, con sesgo sistemático hacia los casos más simples. Usarlos para decidir si el sistema pasa o falla el umbral sería incorrecto.

**2. Context recall es la única señal fiable**, con cobertura del 93–100%. Ambos runs coinciden: el retriever no cubre bien el ground_truth en varias preguntas clave. Las preguntas con recall=0.000 en ambos runs (Q8, Q9, Q12) apuntan a gaps reales de cobertura del corpus, no a ruido de medición.

**3. El grader (Qwen 2.5 3B) falla en la mitad de las preguntas.** En 7 de 14 preguntas no encuentra ningún documento relevante y activa el fallback (devuelve los 9 docs sin filtrar). Esto distorsiona context_precision hacia abajo y context_recall hacia arriba o abajo dependiendo de si los docs sin filtrar contienen la respuesta.

**4. Faithfulness muestra señal real donde se evalúa.** Los 6 ejemplos con score válido son coherentes: AESIA (0.875/0.889) y preguntas concretas sobre normativa (0.800, 0.833) tienen buena fidelidad; el Anexo III (0.083) no, porque los contextos que llegan son el fallback de 9 docs sin filtrar.

---

## Limitaciones

- **Dataset de 14 ejemplos**: insuficiente para nanmeans estables. Un ejemplo NaN o extremo desplaza el resultado varios puntos.
- **Nova Lite como evaluador**: incompatible con los prompts JSON de RAGAS (diseñados para OpenAI). El 64% de los ejemplos de Faithfulness producen NaN no porque el sistema falle, sino porque el evaluador no sigue el formato. Además, usar el mismo modelo para generar y evaluar introduce sesgo de autoevaluación.
- **Grader Qwen 2.5 3B**: falla en el 50% de las preguntas, siempre las mismas. Puede ser insuficiente para razonar sobre relevancia en texto legal denso con referencias cruzadas y terminología normativa.
- **Varianza entre runs**: Q10 (recall 0.75 → 0.25) y Q13 (recall 0.50 → 0.00) son inestables entre runs, lo que sugiere variabilidad adicional en las respuestas del LLM evaluador.

---

## Mejoras necesarias para obtener métricas válidas

### 1. Cambiar el LLM evaluador (impacto alto)

Nova Lite no es adecuado como evaluador RAGAS. Produce NaN en la mayoría de los ejemplos de Faithfulness porque ignora los prompts JSON del framework. La solución es usar un LLM evaluador separado del LLM de producción — **GPT-4o-mini** es la opción más directa: sigue bien instrucciones JSON, está explícitamente soportado por RAGAS, y el coste por evaluación es marginal (fracciones de céntimo por pregunta). Alternativamente, un modelo local de 7-8B (Llama 3.1 8B, Mistral 7B) evitaría dependencia de APIs externas.

### 2. Ampliar el dataset con generación automática (impacto alto)

14 preguntas escritas manualmente tienen dos problemas: son pocas para estadística estable, y tienden a cubrir los casos que el sistema debería responder bien en lugar de los gaps reales del corpus. RAGAS incluye `TestsetGenerator` (`ragas.testset`), que genera preguntas, respuestas de referencia y ground truths automáticamente a partir de los documentos del corpus, incluyendo preguntas simples, de razonamiento y multi-contexto. Con 50-100 ejemplos generados desde el corpus real la cobertura sería proporcional al contenido indexado — incluyendo los artículos que hoy dan recall=0. El dataset generado se versiona en DVC y se reutiliza sin coste adicional en runs futuros. Para la generación también conviene usar un modelo que siga bien instrucciones JSON, no Nova Lite.

### 3. Investigar el grader (impacto medio)

El grader falla siempre en las mismas preguntas (obligaciones, sanciones, anexos). Las hipótesis a investigar son: (a) **tamaño del modelo** — 3B parámetros puede ser insuficiente para razonar sobre relevancia en texto legal con referencias cruzadas; (b) **idioma** — el corpus mezcla español y fragmentos del AI Act en otras lenguas; (c) **longitud del chunk** — la señal de relevancia puede estar enterrada en chunks largos. El primer paso sería loguear los pares (pregunta, chunk) donde el grader devuelve 0 y comparar contra un modelo más grande (7-8B) sobre los mismos pares.
