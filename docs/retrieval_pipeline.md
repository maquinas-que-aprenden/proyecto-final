# Retrieval Pipeline – NormaBot

## 1. Objetivo

Este documento describe el pipeline completo de recuperación (Retrieval) implementado para NormaBot, incluyendo:

- Corpus utilizados
- Estrategia de chunking
- Generación de embeddings
- Vectorización en ChromaDB
- Retrieval base
- Retrieval con priorización suave
- Evaluación con queries complejas

---

## 2. Corpus utilizados

El sistema integra múltiples fuentes legales:

- EU AI Act
- BOE (normativa relacionada)
- LOPD / RGPD
- Documentación asociada a AESIA

Todos los documentos fueron procesados en formato estructurado para permitir recuperación semántica unificada.

---

## 3. Estrategia de Chunking

El chunking se realizó con los siguientes principios:

- División por bloques semánticos coherentes.
- Tamaño controlado para evitar fragmentación excesiva.
- Preservación de metadatos relevantes.

Cada chunk incluye metadata como:

- `source`
- `document`
- `article`
- Identificador único (`id`)

El resultado final se almacenó en:processed/chunks_legal/

---

## 4. Embeddings

Modelo utilizado: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2

Características:

- Multilingüe
- 384 dimensiones
- Adecuado para búsqueda semántica legal

Los embeddings fueron generados y almacenados junto con metadata.

---

## 5. Vectorización en ChromaDB

Se utilizó ChromaDB como vectorstore persistente.

Ruta: processed/vectorstore/chroma

Colección utilizada: normabot_legal_chunks

El vectorstore contiene todos los chunks embebidos y permite consultas semánticas eficientes.

---

## 6. Retrieval Base

Modo BASE:

- Recuperación estándar por similitud semántica.
- Top-K configurable.
- Sin priorización por fuente.

Este modo sirve como baseline de comparación.

---

## 7. Retrieval con Prioridad Suave (SOFT)

Se implementó una heurística que:

1. Detecta fuentes relevantes según la query.
2. Recupera Top-K global.
3. Reordena suavemente priorizando fuentes detectadas.
4. Mantiene mezcla sin duplicados.

Este enfoque no bloquea fuentes alternativas, solo ajusta el ranking.

---

## 8. Evaluación con Queries Complejas

Se definió un conjunto de queries complejas para:

- Probar análisis cruzado entre corpus.
- Evaluar consistencia del Top-1.
- Medir overlap Top-5.
- Detectar posibles mejoras o degradaciones.

Resultados observados:

- No se detectaron degradaciones.
- La priorización suave no alteró significativamente el Top-1 en el dataset actual.
- El sistema se comporta de manera estable.

---

## 9. Estructura del Pipeline

El flujo completo es:

1. Chunking
2. Generación de embeddings
3. Persistencia en ChromaDB
4. Retrieval BASE
5. Retrieval SOFT
6. Comparativa y validación

---

## 10. Limitaciones

- Evaluación heurística basada en Top-1 y overlap.
- No se realizó re-ranking con modelo cross-encoder.
- Dataset limitado al corpus actualmente integrado.

---

## 11. Reproducibilidad

Orden recomendado de ejecución:

1. Notebook 1 – Chunking
2. Notebook 2 – Embeddings
3. Notebook 3 – Test Retrieval
4. Notebook 4 – RAG Queries Complejas

El sistema puede reproducirse ejecutando los notebooks en ese orden.

---

## 12. Conclusión

El pipeline de retrieval de NormaBot está:

- Estructuralmente estable
- Modular
- Reproducible
- Preparado para integración con capas superiores (LLM, agentes, UI)

---

## 13. Módulo reutilizable

La lógica de retrieval ha sido encapsulada en:

src/retrieval/retriever.py

Este módulo permite a otros componentes del proyecto importar directamente la función de búsqueda:

```python
from src.retrieval.retriever import search

La función principal expuesta es: search(query: str, mode: str = "soft", k: int = 5)

Esto permite reutilizar el corpus procesado sin depender de notebooks.

Eso deja claro:

- Dónde está el módulo
- Cómo se usa
- Que ya no depende del entorno experimental


Este documento cubre la implementación correspondiente al módulo de recuperación semántica.