# Reuniones

## Fecha: 2026-02-16 19:00-20:00
* Hablamos uno a uno de en qué estamos trabajando.
* Discutimos dudas sobre el trabajo de los demás.
* Hablamos del [diagrama de arquitectura](arquitectura-inicial.png) y lo repasamos conjuntamente.
* Planteamos en qué vamos a trabajar a continuación cada uno.

## Fecha: 2026-02-17 19:00-20:00
* Revisamos avances individuales del sprint y alineamos roadmap.
* **Hito:** Primer modelo registrado en MLflow con artefactos en S3 (primer ciclo de tracking completo).
* Detectamos métricas sospechosamente altas en ML => Acordamos ampliar el dataset con más variedad de estilos y re-ejecutar notebooks.
* Aclaramos qué va a GitHub (código, notebooks, documentación) y qué a S3+DVC (datos en todas sus versiones => raw, procesados y finales).
* Decidimos que, al menos de momento, no vamos a actualizar el vector store continuamente, por lo que se puede versionar en S3+DVC, y no hace falta desplegar ChromaDB en un servidor.

**Relacionado**: [Gestión de datos -- Normabot](gestion-datos-normabot.pdf)