---
name: planificar
description: >
  Planificación de sprints y tareas para el equipo NormaBot. Crea planes de acción
  concretos con tareas asignadas a miembros específicos del equipo. Usar con
  /planificar [fase|tarea|sprint] para crear un plan de trabajo.
argument-hint: "[fase P0/P1/P2, tarea específica, o 'sprint' para el próximo sprint]"
allowed-tools: Read, Glob, Grep, Bash, Write, AskUserQuestion, TodoWrite
---

# Planificador de Sprints — NormaBot

Crea planes de acción concretos para el equipo. Fecha límite: **12 de marzo de 2026**.

## Contexto

Lee estos archivos antes de planificar:
- `docs/gestion-proyecto/NORMABOT_DIAGNOSIS.md` — Estado actual del código
- `docs/gestion-proyecto/NORMABOT_ROADMAP.md` — Roadmap con prioridades
- `docs/gestion-proyecto/NORMABOT_PROGRESS.md` — Qué se ha completado

## Equipo y capacidades

| Miembro | Fuerte en | Asignar tareas de |
|---------|-----------|-------------------|
| Dani | Data engineering, scraping | ChromaDB, embeddings, corpus, ingesta |
| Rubén | ML clásico, NLP, spaCy | Clasificador como servicio, features, evaluación ML |
| Maru | LangGraph, agentes, UI | Orquestador, tools, Streamlit, integración |
| Nati | DevOps, MLOps, CI/CD | Langfuse, RAGAS, tests CI, Docker, MLflow |

## Argumento recibido

$ARGUMENTS

## Proceso de planificación

### Si el argumento es "sprint" o vacío:

1. Lee el estado actual (diagnosis + progress)
2. Identifica las tareas P0 no completadas
3. Pregunta al equipo:
   - ¿En qué avanzó cada uno desde el último sprint?
   - ¿Hay bloqueos?
   - ¿Cuántas horas puede dedicar cada uno esta semana?
4. Crea un sprint plan con formato:

```markdown
## Sprint [N] — [fecha inicio] al [fecha fin]

### Objetivo del sprint
[1 frase clara]

### Tareas

#### Dani (Data + RAG)
- [ ] [Tarea concreta] — Archivo: `path/file.py` — Esfuerzo: S/M/L
- [ ] [Tarea concreta] — Archivo: `path/file.py` — Esfuerzo: S/M/L

#### Rubén (ML + NLP)
- [ ] [Tarea concreta] — Archivo: `path/file.py` — Esfuerzo: S/M/L

#### Maru (Agents + UI)
- [ ] [Tarea concreta] — Archivo: `path/file.py` — Esfuerzo: S/M/L

#### Nati (MLOps)
- [ ] [Tarea concreta] — Archivo: `path/file.py` — Esfuerzo: S/M/L

### Criterio de éxito
[Qué debe funcionar al final del sprint para considerarlo exitoso]

### Dependencias
[Qué tarea depende de cuál — quién bloquea a quién]
```

5. Actualiza `docs/gestion-proyecto/NORMABOT_PROGRESS.md` con las nuevas tareas

### Si el argumento es una fase (P0, P1, P2):

Desglosa esa fase en tareas concretas asignadas, siguiendo el roadmap.

### Si el argumento es una tarea específica:

Crea un plan detallado para esa tarea: pasos, archivos, dependencias, tests necesarios.

## Reglas

- Cada tarea debe tener: responsable, archivo(s), esfuerzo estimado
- Las dependencias entre tareas deben estar explícitas
- No asignar más de 2 tareas M o 1 tarea L por persona por sprint
- Priorizar siempre P0 > P1 > P2
- Si hay tareas bloqueantes entre miembros, proponer pair programming
