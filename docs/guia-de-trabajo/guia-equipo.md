# Guía de trabajo
Esta guía define cómo colaboramos para asegurar que el proyecto avance de forma organizada.

## 1. GitFlow: uso de Ramas
* Nadie trabaja directamente en main o develop.
* Las ramas deben nacer de develop y usar los siguientes prefijos:
    * feature/: Nuevas funcionalidad (ej. feature/agente-rag).
    * bugfix/: Corrección de errores en desarrollo.
    * hotfix/: Errores críticos detectados en producción (salen de main).
    * release/: Preparación para paso a producción.
    * docs/: Para documentación.
    * chores/: Para tareas que no entran dentro de lo anterior.

## 2. Gestión de Issues
* Antes de empezar cualquier tarea, debe existir una Issue en GitHub.
* Título: Claro y conciso (ej. "Scraping de artículos del BOE").
* Descripción: Qué se quiere conseguir y, si es posible, una pequeña lista de tareas.
* Asignación: Asígnate la Issue a ti mismo para que el resto sepa en qué estás trabajando.

### Cierre de tareas
Las tareas se cierran cuando el compañero que se encargue de ella ha comprobado que funciona, ha documentado las decisiones relevantes a la tarea, se ha validado por al menos 2 compañeros y ha sido mergeada a la rama que corresponda.

## 3. Pull Requests (PRs) y Validación
* El paso de una rama de trabajo a develop (o de develop a main) se hace mediante un PR.
* Se requieren al menos 2 aprobaciones de compañeros para poder mergear.
* Es obligatorio cubrir los puntos del template que aparece al abrir el PR que apliquen:
    * Confirmar que las decisiones se han documentado.
    * Asegurar que el código pasa los tests locales.
    * Indicar si el cambio afecta a otros módulos (ML, RAG, UI u MLOps).

## 4. Documentación de Decisiones
* Si durante una reunión o por Discord acordamos un cambio debe quedar documentado.