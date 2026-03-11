# AGENTS.md — Sistema de Tutoría NormaBot

Este documento describe la arquitectura del sistema de tutoría basado en Claude Code
que ayuda al equipo a mantener el foco, priorizar tareas, y entregar un producto
funcional para la presentación del **12 de marzo de 2026**.

---

## Visión General

```
┌─────────────────────────────────────────────────────┐
│                     /tutor                          │
│            (Skill orquestador principal)             │
│                                                     │
│  Lee estado → Diagnostica → Pregunta → Planifica    │
└──────────┬──────────┬──────────┬──────────┬─────────┘
           │          │          │          │
     ┌─────▼────┐ ┌──▼───┐ ┌───▼──┐ ┌────▼─────┐
     │/diagnostico│/planificar│/progreso│/evaluar  │
     │  (fork)  │ │      │ │(fork)│ │          │
     └────┬─────┘ └──────┘ └──┬───┘ └──────────┘
          │                    │
     ┌────▼────────────────────▼────┐
     │      Agente: auditor         │
     │   (Haiku, read-only)         │
     └──────────────────────────────┘

     ┌──────────────┐
     │  /revisar    │
     │   (fork)     │
     └──────┬───────┘
            │
     ┌──────▼──────────────────────┐
     │  Agente: tutor-asistente    │
     │  (Sonnet, read-only)        │
     └─────────────────────────────┘
```

### Hooks automáticos

```
SessionStart ──→ session-context.sh ──→ Inyecta deadline, equipo, skills disponibles
PostToolUse  ──→ remind-tests.sh    ──→ Recuerda tests al editar src/
Stop         ──→ prompt hook        ──→ Sugiere /progreso tras cambios significativos
```

---

## Skills

### `/tutor` — Orquestador Principal

**Archivo:** `.claude/skills/tutor/SKILL.md`

El punto de entrada del sistema de tutoría. Cuando un miembro del equipo no sabe
qué hacer, invoca `/tutor` y recibe orientación basada en el estado actual del
proyecto.

**Flujo:**
1. Lee archivos de estado (`docs/gestion-proyecto/NORMABOT_DIAGNOSIS.md`, `docs/gestion-proyecto/NORMABOT_PROGRESS.md`, `docs/gestion-proyecto/NORMABOT_ROADMAP.md`)
2. Resume el estado actual en 3-5 líneas
3. Identifica el siguiente paso más importante (prioridad P0 > P1 > P2)
4. Hace preguntas al equipo para ajustar el plan
5. Propone acciones concretas con responsable y plazo

**Uso:**
```
/tutor                    # Orientación general
/tutor RAG                # Ayuda específica con el módulo RAG
/tutor estoy bloqueado    # Ayuda para desbloquear
/tutor qué hago hoy       # Plan del día
```

**Se activa automáticamente cuando:** el usuario pide ayuda con el proyecto, menciona
la presentación, expresa confusión sobre prioridades, o pregunta "qué debería hacer".

---

### `/diagnostico` — Auditoría Técnica

**Archivo:** `.claude/skills/diagnostico/SKILL.md`

Ejecuta un escaneo completo del código fuente y clasifica cada módulo como
FUNCIONAL, STUB, PARCIAL, o VACÍO. Actualiza `docs/gestion-proyecto/NORMABOT_DIAGNOSIS.md`.

**Ejecución:** Se ejecuta en un subagente `auditor` (fork) para no contaminar
el contexto principal.

**Uso:**
```
/diagnostico              # Auditoría completa
```

**Salida:** Actualiza `docs/gestion-proyecto/NORMABOT_DIAGNOSIS.md` con tablas de estado y comparación
con el diagnóstico anterior.

---

### `/planificar` — Planificación de Sprints

**Archivo:** `.claude/skills/planificar/SKILL.md`

Crea planes de acción concretos con tareas asignadas a miembros específicos del equipo.

**Uso:**
```
/planificar sprint        # Planificar el próximo sprint
/planificar P0            # Desglosar fase P0 en tareas
/planificar ChromaDB      # Plan detallado para implementar ChromaDB
```

**Salida:** Sprint plan con tareas, responsables, esfuerzo, dependencias, y criterio
de éxito. Actualiza `docs/gestion-proyecto/NORMABOT_PROGRESS.md`.

---

### `/progreso` — Tracking de Avance

**Archivo:** `.claude/skills/progreso/SKILL.md`

Revisa la actividad reciente (git log, branches, PRs) y el estado del código
para actualizar el tracking de progreso.

**Ejecución:** Se ejecuta en un subagente `auditor` (fork).

**Uso:**
```
/progreso                 # Actualizar y reportar progreso
```

**Salida:** Actualiza `docs/gestion-proyecto/NORMABOT_PROGRESS.md` con items completados, en progreso,
pendientes, y métricas (días restantes, componentes funcionales, tests).

---

### `/evaluar` — Auto-Evaluación

**Archivo:** `.claude/skills/evaluar/SKILL.md`

Evalúa el proyecto contra una rúbrica de bootcamp de ML/IA. Identifica gaps
y propone un plan para maximizar la nota.

**Uso:**
```
/evaluar                  # Auto-evaluación completa
/evaluar ML               # Evaluar solo la parte de ML
```

**Salida:** Puntuación estimada por categoría, gaps críticos, y plan de acción.

---

### `/revisar` — Code Review

**Archivo:** `.claude/skills/revisar/SKILL.md`

Revisa código con perspectiva de proyecto final de bootcamp: completitud funcional,
calidad, dominio legal, tests, e impacto en la presentación.

**Ejecución:** Se ejecuta en un subagente `tutor-asistente` (fork).

**Uso:**
```
/revisar src/rag/main.py  # Revisar archivo específico
/revisar orchestrator     # Revisar módulo completo
/revisar                  # Revisar cambios no commiteados
```

---

## Agentes

### `auditor`

**Archivo:** `.claude/agents/auditor.md`
**Modelo:** Haiku (rápido y económico)
**Tools:** Read, Glob, Grep, Bash (solo lectura)

Agente especializado en escanear el código y reportar su estado. Usado por
`/diagnostico` y `/progreso`. Nunca modifica código fuente — solo puede escribir
en archivos de tracking (`docs/gestion-proyecto/NORMABOT_*.md`).

### `tutor-asistente`

**Archivo:** `.claude/agents/tutor-asistente.md`
**Modelo:** Sonnet (equilibrado)
**Tools:** Read, Glob, Grep, Bash (solo lectura)

Agente de apoyo para code reviews y análisis técnico. Usado por `/revisar`.
Evalúa código contra las convenciones del proyecto y los criterios del bootcamp.

---

## Hooks

### Session Context (`SessionStart`)

**Script:** `.claude/hooks/session-context.sh`

Al inicio de cada sesión, inyecta:
- Días restantes hasta la presentación
- Equipo y roles
- Skills disponibles
- Referencia a archivos de estado del proyecto

### Test Reminder (`PostToolUse` → `Edit|Write`)

**Script:** `.claude/hooks/remind-tests.sh`

Cuando se edita un archivo en `src/`, verifica si existe un test correspondiente
en `tests/`. Si no existe, genera un recordatorio.

### Progress Check (`Stop`)

**Tipo:** Prompt hook (evaluado por LLM)

Al terminar una respuesta, si se detectan cambios significativos en `src/`,
sugiere ejecutar `/progreso` para actualizar el tracking.

---

## Archivos de Estado

El sistema de tutoría mantiene tres archivos de estado en `docs/gestion-proyecto/`:

| Archivo | Actualizado por | Contenido |
|---------|----------------|-----------|
| `docs/gestion-proyecto/NORMABOT_DIAGNOSIS.md` | `/diagnostico` | Mapa del estado actual: qué funciona, qué es stub, qué falta |
| `docs/gestion-proyecto/NORMABOT_ROADMAP.md` | `/planificar` | Roadmap priorizado con fases P0/P1/P2 y estimaciones |
| `docs/gestion-proyecto/NORMABOT_PROGRESS.md` | `/progreso`, `/planificar` | Tracking: completado, en curso, pendiente, decisiones |

---

## Flujo de Trabajo Recomendado

### Al inicio de cada sesión de trabajo

```
/tutor                    # "¿Qué debería hacer hoy?"
```

### Al empezar un sprint

```
/diagnostico              # Saber dónde estamos
/planificar sprint        # Crear plan de acción
```

### Después de implementar algo

```
/revisar [archivo]        # Code review
/progreso                 # Actualizar tracking
```

### Antes de la presentación

```
/evaluar                  # ¿Dónde estamos respecto a la rúbrica?
/planificar sprint        # Sprint final con lo que falta
```

---

## Configuración

### Estructura de archivos

```
.claude/
├── settings.json              # Hooks del proyecto (compartido vía git)
├── settings.local.json        # Settings locales (gitignored)
├── skills/
│   ├── tutor/SKILL.md         # /tutor — Orquestador principal
│   ├── diagnostico/SKILL.md   # /diagnostico — Auditoría técnica
│   ├── planificar/SKILL.md    # /planificar — Planificación de sprints
│   ├── progreso/SKILL.md      # /progreso — Tracking de avance
│   ├── evaluar/SKILL.md       # /evaluar — Auto-evaluación
│   └── revisar/SKILL.md       # /revisar — Code review
├── agents/
│   ├── auditor.md             # Agente read-only para diagnóstico
│   └── tutor-asistente.md     # Agente de apoyo para reviews
└── hooks/
    ├── session-context.sh     # Contexto al inicio de sesión
    ├── remind-tests.sh        # Recordatorio de tests
    └── track-progress.sh      # (documentación del prompt hook)
```

### Para que funcione en todo el equipo

1. Commitear `.claude/` al repositorio (excepto `settings.local.json`)
2. Cada miembro necesita Claude Code instalado
3. Los hooks se activan automáticamente al abrir el proyecto
4. Los skills están disponibles para todos vía `/skill-name`
