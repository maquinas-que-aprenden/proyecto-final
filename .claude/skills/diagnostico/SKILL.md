---
name: diagnostico
description: "Auditoría técnica del estado actual del proyecto NormaBot. Escanea el código fuente, identifica qué es funcional vs stub vs vacío, y actualiza el diagnóstico. Usar cuando se necesite saber el estado real del código."
context: fork
agent: auditor
allowed-tools: Read, Glob, Grep, Bash, Write
---

# Diagnóstico Técnico de NormaBot

Realiza una auditoría completa del estado del código. Tu objetivo es generar un informe
actualizado y preciso.

## Proceso

### 1. Escanear todos los módulos fuente

Para cada archivo en `src/`:
- Lee el contenido completo
- Clasifica como: **FUNCIONAL** (código real, ejecutable), **STUB** (placeholder/hardcoded),
  o **PARCIAL** (mezcla de real y stub)
- Cuenta líneas de código real vs stub
- Identifica imports que se usan vs que son decorativos

### 2. Verificar tests

- Revisa `tests/` — ¿hay archivos de test reales?
- Revisa `.github/workflows/` — ¿los jobs de test están activos o comentados?
- Revisa `eval/` — ¿hay evaluación RAGAS implementada?

### 3. Verificar integraciones

- ¿Las tools del orquestador (`src/orchestrator/main.py`) llaman a implementaciones reales o stubs?
- ¿ChromaDB está instanciado de verdad o es simulado?
- ¿Langfuse está integrado o es stub?
- ¿El clasificador tiene una función `predict_risk()` expuesta para el orquestador?

### 4. Verificar datos

- ¿Hay corpus legal en `data/` o archivos DVC que lo referencien?
- ¿Hay modelos serializados en `src/classifier/model/`?
- ¿Los notebooks se ejecutaron (tienen output) o están vacíos?

### 5. Generar informe

Actualiza `docs/gestion-proyecto/NORMABOT_DIAGNOSIS.md` con:

```markdown
# NormaBot — Diagnóstico Técnico

Fecha: [fecha actual]

## 1. Mapa del Estado Actual

### Componentes FUNCIONALES
| Componente | Ubicación | Estado |
|---|---|---|
[tabla]

### Componentes STUB
[tabla]

### Componentes VACÍOS
[tabla]

## 2. Cambios desde el último diagnóstico
[lista de qué cambió]

## 3. Siguiente paso bloqueante
[la tarea P0 más urgente]

## 4. Resumen Ejecutivo
[3-5 líneas sobre el estado general]
```

## Criterios de clasificación

- **FUNCIONAL**: El código hace lo que dice. Importa dependencias reales, procesa datos,
  devuelve resultados correctos. Ejemplo: `src/classifier/functions.py`
- **STUB**: El código devuelve datos hardcodeados o simulados. No procesa entrada real.
  Ejemplo: `src/rag/main.py` con retrieve() que devuelve docs fijos.
- **PARCIAL**: Parte del código es real (ej: el schema de entrada) pero la lógica core
  es stub. Ejemplo: orquestador con agent real pero tools fake.
- **VACÍO**: Solo tiene `.gitkeep` o no existe.

## Importante

- NO modifiques código fuente. Solo lee y reporta.
- Sé honesto. Si algo no funciona, dilo. El equipo necesita verdad, no optimismo.
- Compara con el diagnóstico anterior si existe para mostrar progreso.
