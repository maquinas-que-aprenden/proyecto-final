---
name: progreso
description: "Tracking del progreso del proyecto NormaBot. Revisa el estado actual del código y git, actualiza el archivo de progreso, y reporta avances y bloqueos. Usar cuando se quiera saber cómo va el proyecto."
context: fork
agent: auditor
allowed-tools: Read, Glob, Grep, Bash, Write
---

# Tracking de Progreso — NormaBot

Revisa el estado actual y actualiza el tracking de progreso.

## Proceso

### 1. Revisar git

Ejecuta estos comandos para entender la actividad reciente:

```bash
# Commits recientes (últimos 7 días, todos los autores)
git log --oneline --all --since="7 days ago" --format="%h %an %s"

# Ramas activas
git branch -a --sort=-committerdate | head -20

# PRs abiertos (si gh está disponible)
gh pr list --state open 2>/dev/null || echo "gh no disponible"

# Issues abiertos
gh issue list --state open 2>/dev/null || echo "gh no disponible"
```

### 2. Escanear cambios en módulos clave

Para cada módulo (`src/rag`, `src/data`, `src/orchestrator`, `src/report`,
`src/observability`, `src/classifier`, `tests/`, `eval/`):
- ¿Cambió desde el último diagnóstico?
- ¿Sigue siendo stub o se implementó?
- ¿Hay código nuevo sin commitear?

### 3. Actualizar docs/gestion-proyecto/NORMABOT_PROGRESS.md

Lee el archivo actual y actualiza con:

```markdown
# NormaBot — Tracking de Progreso

Última actualización: [fecha]

## Completado
| Fecha | Item | Responsable | Notas |
|---|---|---|---|
[items ya completados + nuevos detectados]

## En Progreso
| Item | Responsable | Estado | Bloqueos |
|---|---|---|---|
[detectar de git branches activas y PRs abiertos]

## Pendiente (próximos pasos)
[lista priorizada de lo que falta, basada en docs/gestion-proyecto/NORMABOT_ROADMAP.md]

## Métricas
- Días restantes: [calcular hasta 12 de marzo 2026]
- Componentes funcionales: [N de M]
- Tests: [N archivos de test]
- Coverage estimado: [% o "sin tests"]

## Decisiones Tomadas
| Fecha | Decisión | Justificación |
|---|---|---|
[mantener historial]
```

### 4. Generar resumen

Al final, genera un resumen breve (5-10 líneas) del estado:
- Qué avanzó desde el último tracking
- Qué está bloqueado
- Cuál es la prioridad inmediata
- Días restantes hasta la presentación
