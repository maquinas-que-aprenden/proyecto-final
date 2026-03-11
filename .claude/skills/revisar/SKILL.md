---
name: revisar
description: >
  Code review con contexto de bootcamp para NormaBot. Revisa código, PRs o archivos
  específicos evaluando calidad, completitud, y alineación con los objetivos del
  proyecto. Usar con /revisar [archivo, PR, o módulo].
argument-hint: "[archivo, PR number, o módulo (rag/classifier/orchestrator)]"
context: fork
agent: tutor-asistente
allowed-tools: Read, Glob, Grep, Bash
---

# Code Review — NormaBot (Contexto Bootcamp)

Revisa código con una perspectiva de proyecto final de bootcamp de ML/IA.

## Qué revisar

$ARGUMENTS

Si no se especifica argumento, revisa los cambios no commiteados (`git diff`) y
los commits recientes.

## Criterios de revisión

### 1. Completitud funcional
- ¿El código hace lo que dice o es un stub/placeholder?
- ¿Falta conectar con otros módulos?
- ¿Hay TODOs o FIXMEs sin resolver?

### 2. Calidad de código
- ¿Sigue las convenciones del proyecto? (ver CLAUDE.md: English identifiers,
  Spanish docstrings, ruff linting)
- ¿Hay imports no usados?
- ¿Hay código duplicado entre módulos?
- ¿El manejo de errores es apropiado?

### 3. Dominio legal
- Si genera respuestas legales: ¿incluye disclaimer obligatorio?
- Si cita artículos: ¿las citas son reales o inventadas?
- Si clasifica riesgo: ¿usa las 4 categorías del EU AI Act?

### 4. Tests y robustez
- ¿Hay tests para este código?
- ¿Se manejan edge cases (input vacío, modelo no encontrado, API caída)?
- ¿Las dependencias externas (Bedrock, Groq, ChromaDB) tienen fallback?

### 5. Impacto en la presentación
- ¿Este código contribuye al demo end-to-end?
- ¿Es visible para el evaluador o es infraestructura invisible?
- ¿Merece la pena invertir más tiempo aquí o en otra cosa?

## Formato de feedback

Para cada issue encontrado:

```
### [CRÍTICO|SUGERENCIA|BIEN] — archivo:línea

**Qué**: Descripción del problema o acierto
**Por qué**: Impacto en el proyecto/presentación
**Cómo**: Solución concreta (si es un problema)
```

## Al final del review

Resume:
1. Número de issues críticos / sugerencias / aciertos
2. Si el código está listo para merge o necesita cambios
3. Prioridad de los cambios necesarios respecto al roadmap
