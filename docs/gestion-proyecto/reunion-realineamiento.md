# Reunión de Realineamiento — NormaBot

**Fecha:** [próxima reunión disponible]
**Duración:** 30-40 minutos
**Objetivo:** Alinear al equipo sobre el estado real del proyecto, asignar tareas claras, y definir el plan para los 18 días restantes hasta la presentación (12 de marzo).

---

## Contexto para compartir antes de la reunión

> Hemos hecho un diagnóstico técnico del proyecto. Tenemos **dos zonas muy diferentes**:
> lo que funciona de verdad (clasificador ML, MLOps, CI/CD, Docker, infra) y lo que
> son stubs/placeholders (RAG, ChromaDB, informes, observabilidad, tools del orquestador).
> El producto core — que un usuario pueda preguntar sobre normativa legal y recibir una
> respuesta real — no funciona todavía. Necesitamos alinear y priorizar.

---

## Agenda (30 min)

### 1. Estado real de cada módulo (10 min)

Cada persona responde **en 2 minutos** sobre su área. No demos, solo estado honesto.

**Dani (Data + RAG):**
- [ ] ¿Dónde está el corpus legal? ¿En S3? ¿DVC? ¿Local? ¿Existe?
- [ ] ¿Has empezado a implementar ChromaDB + embeddings? Si sí, ¿qué funciona?
- [ ] ¿`src/rag/main.py` y `src/data/main.py` siguen siendo stubs o hay código real?
- [ ] ¿Tienes bloqueos? (acceso a datos, dependencias, dudas técnicas)

**Rubén (ML + NLP):**
- [ ] El clasificador está maduro en notebooks. ¿Hay un modelo serializado (.joblib) listo?
- [ ] ¿Existe una función `predict_risk(text) -> dict` que el orquestador pueda llamar?
- [ ] ¿Los notebooks de fine-tuning (QLoRA) produjeron resultados? ¿Merece la pena documentar?
- [ ] ¿Hay algo que puedas hacer para ayudar a Dani con el RAG?

**Maru (Agents + UI):**
- [ ] El orquestador ReAct funciona pero las 3 tools son stubs. Para conectarlas necesito que Dani y Rubén expongan sus módulos como funciones invocables.
- [ ] La UI de Streamlit funciona pero es muy básica. ¿Queremos mejorarla o priorizar backend?
- [ ] He montado un sistema de tutoría en Claude Code (skills + hooks) para que todos tengamos orientación. Lo explico en 1 minuto.

**Nati (MLOps + Observabilidad):**
- [ ] ¿Langfuse está solo en requirements o hay algo implementado?
- [ ] ¿Has probado RAGAS para evaluar la calidad del RAG?
- [ ] Los tests en CI están comentados. ¿Puedes escribir tests mínimos y activar el job?
- [ ] ¿El deploy a EC2 sigue funcionando?

### 2. Mapa de dependencias (5 min)

Compartir este diagrama con el equipo:

```
SEMANA 1 (22-28 feb):
═══════════════════════

Dani ──→ Corpus legal en ChromaDB + RAG básico
              │
Rubén ──→ predict_risk() como servicio
              │
              ▼
SEMANA 2 (1-7 mar):
═══════════════════

Maru ──→ Conectar tools del orquestador (depende de Dani + Rubén)
              │
Nati ──→ Tests + Langfuse + descomentar CI
              │
              ▼
SEMANA 3 (8-12 mar):
═══════════════════

TODOS ──→ Pulir demo, preparar presentación, RAGAS eval
```

**Mensaje clave:** Dani tiene la tarea más bloqueante. Si el RAG no avanza, Maru no puede conectar el orquestador, y no hay demo. ¿Necesita Dani ayuda?

### 3. Acuerdos y asignación (10 min)

Definir para cada persona:

| Persona | Tarea prioritaria | Entregable concreto | Fecha |
|---------|-------------------|---------------------|-------|
| Dani | ChromaDB + RAG básico | `retrieve()` devuelve docs reales de ChromaDB | 27 feb |
| Rubén | Clasificador como servicio | `predict_risk(text) -> {"risk_level": ..., "explanation": ...}` | 25 feb |
| Maru | Conectar orquestador | Tools llaman a RAG, classifier, y report reales | 28 feb |
| Nati | Tests + CI activo | 3+ tests en `tests/`, job de pytest descomentado | 27 feb |

### 4. Compromisos rápidos (5 min)

- [ ] ¿Todos de acuerdo con las prioridades?
- [ ] ¿Alguien necesita pair programming o ayuda?
- [ ] ¿Cuándo es la siguiente check-in? (propuesta: jueves)
- [ ] ¿Todos instalan Claude Code y prueban `/tutor`?

---

## Preguntas decisivas que deben responderse

1. **¿Existe el corpus legal?** Si no existe, es el bloqueante #1 y Dani necesita ayuda urgente para generarlo (scraping BOE o dataset existente).

2. **¿Enfocamos en demo o en completitud?** Con 18 días, recomiendo: demo funcional end-to-end con un subconjunto de artículos > sistema completo que no funciona.

3. **¿Quién presenta qué?** Cada persona debería poder explicar su módulo. Esto motiva ownership.

---

## Después de la reunión

1. Actualizar `NORMABOT_PROGRESS.md` con los acuerdos
2. Crear issues en GitHub para cada tarea asignada
3. Cada miembro puede usar `/tutor` en Claude Code para orientación diaria
4. Siguiente check-in: [fecha]

---

## Sistema de tutoría Claude Code (1 min para explicar al equipo)

Hemos montado un sistema de skills en `.claude/` que todo el equipo puede usar:

- **`/tutor`** → "¿Qué debería hacer hoy?" (orientación general)
- **`/diagnostico`** → "¿Qué funciona de verdad en el código?" (auditoría)
- **`/planificar sprint`** → "¿Cuál es el plan para esta semana?" (tareas por persona)
- **`/progreso`** → "¿Cómo vamos?" (actualiza tracking)
- **`/evaluar`** → "¿Qué nota sacaríamos hoy?" (auto-evaluación vs rúbrica)
- **`/revisar [archivo]`** → "¿Está bien mi código?" (code review)

Además, al abrir el proyecto Claude te recuerda el deadline y los skills disponibles,
y si editas código en `src/` te recuerda escribir tests.
