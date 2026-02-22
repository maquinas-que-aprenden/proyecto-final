# NormaBot – Proyecto Final Bootcamp IA

## Descripción

NormaBot es un sistema de recuperación semántica aplicado a normativa relacionada con Inteligencia Artificial y regulación legal.

Este repositorio contiene la implementación del pipeline de retrieval, incluyendo procesamiento de corpus, generación de embeddings y validación mediante queries complejas.

---

## Módulo Retrieval

El módulo de retrieval incluye:

- Chunking estructurado de corpus legales
- Generación de embeddings multilingües
- Persistencia en ChromaDB
- Retrieval base por similitud semántica
- Retrieval con priorización suave por fuente
- Evaluación con queries complejas

La documentación técnica completa se encuentra en:

docs/retrieval_pipeline.md

---

## Estructura relevante

notebooks/  
Desarrollo experimental y validación del pipeline.

processed/  
Artefactos generados (chunks, vectorstore, evaluaciones).

docs/  
Documentación técnica del sistema.

---

Este README resume el estado actual del módulo de Retrieval dentro del proyecto NormaBot.