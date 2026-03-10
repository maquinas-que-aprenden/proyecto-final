**Transcripción depurada (reunión equipo — Proyecto Final Bootcamp)**

Participantes (según contexto de la conversación): Persona A, Persona D, Persona B, Persona C.

Objetivo de la reunión: sincronizar avances del Sprint, estado de ML/MLflow, dataset y trazabilidad (Git/DVC/S3), y roadmap de embeddings + vector store + RAG/agentes.

![ref1]

**1) Estado general y avances (ML + tracking)**

- Persona D comenta que ha dedicado muchas horas y que ya subió a una PR lo que lleva hecho.
- Hito: hay un modelo registrado en MLflow y se están generando y subiendo artefactos a S3 (AWS).
- Se menciona trabajo de ajuste del entorno: rehacer requirements, reinstalar dependencias y reconfigurar el venv.

![ref1]

**2) Discusión sobre NER y cambios en split (train/test/val)**

- Persona D explica que no incluyó NER inicialmente porque pensaba que no aportaría valor.
- Consultó con varias herramientas (p.ej. ChatGPT/Claude) y concluye que NER no aporta significado útil para este caso, por lo que deciden no meterlo.
- Hito: se implementó el cambio recomendado de dividir en Train / Test / Validation (ya aplicado).

![ref1]

**3) Métricas “demasiado buenas” (riesgo de dataset “demasiado limpio”)**

- Se revisan resultados del modelo y se comenta que las métricas son muy altas (≈95% y/o “sospechosas”).
- Se visualiza/queda registrado que existe matriz de confusión y otras métricas.
- Decisión / acción sugerida: ajustar el dataset para hacerlo más realista:
  - Añadir más filas (más ejemplos) en lugar de “cambiarlo todo”.
  - Pedir ejemplos con distintos estilos de redacción para reducir “overfitting” al estilo original.
  - Re-ejecutar notebooks (mencionan 3–4 notebooks) tras ampliar dataset.

![ref1]

**4) Dataset y fuentes (incluyendo RGPD) + chunking**

- Persona A explica que:
  - Descargó “data sucia/raw” y luego se dio cuenta de que faltaba incluir normativa LOPDGDD / RGPD.
  - En el roadmap, la RGPD aparecía más adelante (día/paso 6), así que no mezclarla desde el inicio terminó siendo coherente con el plan.
- Se mencionan conjuntos de chunks/datasets:
  - Un dataset “actual” para embeddings (p.ej. Chunks Final Old / Chunking Old — nombres aproximados del audio).
  - Un dataset “con todas las fuentes” que incluye RGPD (p.ej. Chunks Final All Sources).
- Hito técnico: Persona A ya tiene generados JSON finales de chunks, además de carpetas con raw y procesados.

![ref1]

**5) Qué se sube a Git vs qué va a S3 (DVC y trazabilidad)**

- Persona A plantea dudas sobre GitHub, PRs y qué debe subirse:
  - ¿subir solo el dataset final?
  - ¿subir también raw/procesados para demostrar trazabilidad?
- Acuerdo técnico (consenso):
  - GitHub: código + documentación técnica + notebooks (p.ej. notebook de chunking) + datasets finales necesarios.
  - Datos pesados (raw, procesados intermedios, versiones): idealmente S3 y trazados con DVC (“Git de los datos”).
- Se aclara que Git “no debería” contener tantos datos; y que DVC permite reconstruir el pipeline y versionar datasets.
- Pregunta abierta: si los profesores deben acceder a S3.
  - Se comenta que se puede dar acceso, pero también se valora si es demasiado lío; en cualquier caso, se subraya la necesidad de trazabilidad.

![ref1]

**6) Vector store (ChromaDB u otra) y si debe estar “desplegada”**

- Se debate si la vector store debe:
  - estar local,
  - o estar en un servidor,
  - o versionarse como artefacto (índice) en S3.
- Conclusión práctica: la vector store se comporta como un índice relativamente estático:
  - se genera,
  - y solo se actualiza cuando entran documentos nuevos,
  - por lo que tiene sentido guardar versiones (p.ej. en S3 con DVC) en vez de montarla como servicio dinámico.
- Se menciona que la actualización diaria podría ser “overkill” y que podría ser una mejora futura (p.ej. scraping condicional por keywords).

![ref1]

**7) Reparto de roadmap (embeddings → vector store → RAG)**

- Se aclara el flujo del roadmap:
  - Persona A hará embeddings y poblar ChromaDB (vector store) como parte de sus pasos del Sprint.
  - Persona C trabajará la parte RAG encima de esos datos (cuando la vector store esté lista).
  - Persona D tiene partes de infraestructura/observabilidad/trazabilidad (MLflow, S3, DVC, evaluación tipo RAGAS, IaC).

![ref1]

**8) Infraestructura: VM vs Serverless (coste y caso de uso)**

- Persona D explica que tiene una VM pequeña en free tier (coste bajo), con coste principal por IP pública.
- Para MLflow, una VM levantada cuando se use es suficiente; se puede apagar/encender para ahorrar.
- Se aclara que serverless (Lambda/Cloud Functions) encaja mejor con tareas puntuales (jobs/eventos), no con una UI/servicio tipo MLflow siempre “stateful”.
- Nota operativa: si la VM se apaga, la IP pública puede cambiar salvo que se pague IP fija.

![ref1]

**9) Avance Persona C (agentes + RAG pipeline)**

- Persona C comenta que:
  - hizo comentarios en PRs,
  - y está montando estructuras de agentes/flujo:
    - un “estado” con campos (menciona risk\_level, source, documents que conectan con inputs de otros),
    - “tres grafos/agentes” (clasificador / report / etc.) en modo “mock” todavía,
    - un pipeline RAG con:
      - recepción de query,
      - recuperación de documentos (vector DB mock),
      - filtro de relevancia (score/LLM “mock” por ahora),
      - transformación de consulta si los docs no son relevantes,
      - generación de respuesta con documentos relevantes.
- Comentario: necesita integrar llamadas reales al modelo (dejar de mockear) cuando toque según roadmap.

![ref1]

**10) Cierre y próximos pasos**

- Se acuerda cerrar por hoy y continuar asíncrono (mensajes) y/o próxima reunión.
- Persona D seguirá con:
  - revisar PRs,
  - evaluación (RAGAS),
  - mejoras de trazabilidad (DVC),
  - y soporte de infraestructura.
- Persona A seguirá con:
  - embeddings + vector store,
  - y resolver el “cómo subir” (Git vs S3/DVC).
- Persona C seguirá con:
  - integrar el modelo real en su pipeline,
  - y avanzar con RAG/agentes según roadmap.

![ref1]

**Hitos importantes (para trazabilidad de aprendizajes)**

1. Modelo registrado en MLflow y artefactos subidos a S3 (primer tracking end-to-end).
1. Split Train/Test/Validation implementado (mejora de rigor experimental).
1. Decisión consciente de NO usar NER por baja aportación al caso (criterio técnico).
1. Identificación de métricas “sospechosamente altas” → necesidad de dataset más realista (aprendizaje sobre calidad de datos y generalización).
1. Consolidación del enfoque Git (código) vs DVC+S3 (datos) para trazabilidad reproducible.
1. Definición práctica de vector store como índice versionable (no necesariamente servicio dinámico).
1. Alineación del roadmap: Persona A (embeddings/vector store) → Persona C (RAG/agentes) → Persona D (infra/observabilidad/evaluación).
1. Clarificación de VM vs serverless y su encaje real para MLflow y tareas.

![ref2]

**Acciones acordadas (lista operativa)**

- Dataset (ML):
  - Añadir filas con variación de estilo; re-ejecutar notebooks y reevaluar métricas.
- Repositorio:
  - Subir a GitHub: notebook chunking + datasets finales necesarios + código/documentación.
  - Mantener raw/procesados y versiones en S3 con DVC.
- Vector store:
  - Generar y versionar (S3/DVC) en vez de desplegar como servicio dinámico (salvo decisión futura).
- RAG/Agentes:
  - Sustituir “mocks” por llamadas reales cuando el modelo y vector store estén listos.
- Infra:
  - Mantener VM para MLflow; apagar/encender según uso; gestionar cambio de IP si aplica.

![ref2]

## <a name="_vxhiyppjvvb5"></a>**Resumen de la reunión**
- Se revisó el enfoque de despliegue automatizado: crear una imagen (build) que se pueda instalar directamente en AWS y que, al llegar a main, se despliegue sin pasos manuales. La idea es que lo que entra en main ya esté probado y “listo para tirar”.
- Se debatió la organización del repositorio, especialmente dónde colocar los notebooks (posible carpeta notebooks), y cómo presentar el proyecto sin necesidad de ejecutar notebooks en develop/main más allá de lo imprescindible.
- Se cambió al Dataset #2 (más real/“orgánico”) y se observó un efecto claro:
  - Con el dataset anterior (más sintético), las métricas eran excesivamente buenas.
  - Con el dataset nuevo, los resultados del clasificador pasaron a ser bastante malos, lo que activó una discusión para entender la causa en lugar de desechar el trabajo.
- Se comentó que el cambio de dataset provocó muchas roturas y una PR muy grande (mucho código copiado/adaptado). Se planteó que idealmente se habría separado en ramas, pero se decidió revisar/probar la PR tal como está para no complicar más el merge, y luego ya separar si hace falta.
- Se planteó una estrategia para no “tirar” el avance:
  - Mantener el modelo ML de clasificación (XGBoost) entrenado con el dataset sintético (buenas métricas) para predecir la etiqueta (aceptable/riesgo alto/riesgo bajo, etc.).
  - Usar un segundo paso con un modelo LLM fine-tuneado para generar la explicación/justificación de la etiqueta. Aquí surgió que el fine-tuning en la especificación es ambiguo y se discutieron ubicaciones posibles (orquestador vs generación de reportes), descartando su encaje directo en la parte de RAG de relevancia de documentos.
- Se revisó MLflow: hubo un problema de acceso/visualización (posible IP diferente o VM caída), porque no se veían los experimentos esperados. Se acordó revisar logs/estado de la máquina y volver a ejecutar.
- Se acordó el plan operativo inmediato:
  - Revisar comentarios pendientes en la PR (CodeRabbit), aplicar lo necesario, y avisar cuando esté lista para merge.
  - Una vez mergeada, ejecutar todos los cuadernos para validar el pipeline con el nuevo dataset.
  - En paralelo, investigar por qué el dataset orgánico da malos resultados (posibles causas: traducción con IA, distribución de clases, ruido, diferencia de dominio), consultando a compañeros/profesores si hace falta.
- Quedó pendiente que se compartan los nombres exactos de los modelos (el “bueno” y el “malo”, p.ej. el nuevo vive en Classifier 2) para poder invocarlos y comparar en pruebas. Se cierra con coordinación asíncrona durante el finde y próxima sincronización el lunes

## <a name="_cnqrtyfq2bnd"></a>**Resumen de la reunión**
- Se acordó que los notebooks no son el formato adecuado para producción: para ver resultados rápido sirven, pero para integración, tests y despliegue es mejor pasar chunking/embeddings a scripts .py (con requirements + data.txt/listado de fuentes). Se propuso que esta conversión la haga Claude/Cloud Code para acelerar.
- Se aclaró el flujo “producción” de datos:
  - La ingesta/actualización (nuevo BOE, nuevos docs) no debe ejecutarse cada vez que se levanta el chat/app.
  - Debe ser un proceso separado (tipo job) que corre solo cuando hay novedades y actualiza chunks/embeddings/vectorstore.
  - Como mejora futura, se habló de automatizarlo con eventos (detectar BOE nuevo → descargar a S3 → trigger serverless → procesar → guardar outputs).
- Se revisó el estado del repo y PRs:
  - Se detectaron duplicaciones y notebooks repetidos (algunos se pueden borrar).
  - Se compartió la práctica de usar los prompts de CodeRabbit para que Claude resuelva refactors/fixes más rápido, e incluso agrupar varios prompts.
- Se coordinó el merge y la visión global:
  - Objetivo inmediato: mergear PRs pendientes, sincronizar todos con develop y pedir al tutor un análisis global del estado (qué falta, qué refactorizar, qué conectar).
  - A partir de ese feedback, reasignar tareas para el resto de semana y preparar el cierre para despliegue (idealmente “cerrado” a finales de mes para empezar con deploy con margen).
- Se comentó el avance del modelo:
  - Para mejorar el clasificador, se probó fusionar dataset sintético + real en un dataset combinado (más muestras → mejores resultados).
  - Se discutió mantener datasets separados (sintético/real) como referencia y trabajar con el fusionado como dataset principal, dejando la comparativa como parte didáctica.
- Hubo un incidente de Git/ramas:
  - Se creó una rama (dataset-fusion) que estaba muy por detrás de develop (143 commits).
  - Se identificó la causa: develop local desactualizado vs origin/develop.
  - Se corrigió sincronizando develop y se indicó el flujo: hacer checkout a la rama y rebase/merge con develop antes de seguir, para evitar conflictos futuros.
  - Se acordó que la autora lo termina en privado y avisa al grupo cuando quede listo.
- Cierre:
  - Se deja como prioridad: terminar merges esta noche, luego enviar todo al tutor para visión integral, y al día siguiente decidir dirección de trabajo con el estado ya limpio.

## <a name="_5d448ji6m4s5"></a>**Resumen de la reunión**
- Se revisó el estado actual del proyecto y la PR más reciente, que ya integra el flujo RAG + orquestador + clasificador + report. Hubo trabajo en paralelo (Persona C y Persona B) y se decidió comparar implementaciones y fusionar lo mejor de ambas en una única versión para que, al mergear, ya se pueda probar el flujo completo pasando por las 3 “tools” según el tipo de pregunta (búsqueda legal → RAG, clasificación de riesgo → modelo, informe → report).
- Se habló de observabilidad/monitorización:
  - Interés en usar Langfuse para ver trazas por nodo y métricas; si no, como fallback se pueden añadir logs propios.
  - Se identificó la necesidad de tener métricas no solo de “funciona/no funciona”, sino de calidad: que el RAG recupere documentos relevantes y que las respuestas sean fieles.
- Se aclararon tests pendientes del roadmap:
  - “E2E del RAG pipeline” entendido como pruebas con varias queries contra el flujo para verificar citas reales, respuestas coherentes y métricas informales.
  - Se discutió si el test es solo de la “caja RAG” o de todo el agente; consenso: principalmente validar la parte RAG (recuperación + filtrado + generación con citas).
- Decisiones técnicas comentadas:
  - Se eligió un modelo de Amazon (Nova Lite) para ciertas llamadas por simplicidad de credenciales/coste, y un modelo local más ligero para filtros binarios de relevancia cuando aplique.
  - Se recordó el ajuste de parámetros tipo K para evitar ruido y mejorar la recuperación.
- Se definió la línea de trabajo inmediata:
  - Mergear y probar end-to-end lo que ya hay antes de añadir ampliaciones.
  - Implementar la evaluación del RAG con RAGAS (métricas tipo faithfulness, context recall/precision, answer relevancy) y, si se puede, registrar trazas/métricas en Langfuse.
  - Mejoras “de impacto” propuestas para el backlog (no necesariamente todas ya):
    - Análisis de sesgos/errores del clasificador (por tipo de sistema/área legal).
    - Feedback del usuario por respuesta (para ciclo de mejora continua).
    - Dash/visualización de métricas (posiblemente en Streamlit), humanizando el significado de las métricas para que se entiendan.
- Se comentó que para la recta final conviene preparar materiales (demo/vídeo/presentación), pero se prioriza primero que el sistema esté estable y probado. Se estimó que las mejoras pueden ir esta semana y la próxima centrarse en cierre, documentación y demo, siempre que el end-to-end sea sólido.
- Gestión de PRs y conflictos:
  - Para evitar duplicidad, se acordó que Persona C elimine/evite cambios redundantes (p.ej., borrar un main duplicado) y mergear en el orden que minimice conflictos.
  - Los conflictos detectados parecían menores y se resolverán al actualizar la rama y hacer un check final con Claude/CodeRabbit si hace falta.
  - Plan: Persona C avisa cuando esté lista la PR; Persona D la despliega y se coordinan pruebas al día siguiente.

**Resumen de la reunión**

- Se confirmó que Langfuse ya está funcionando y permite ver trazas por ejecución: entradas, pasos por componentes (p. ej. classifier, predict\_risk, rag.retrieve, etc.) y errores. Se observó un caso donde Chroma no estaba disponible, y Langfuse ayudó a detectarlo (solo se ejecutó parte del flujo).
- Se aclaró el alcance: Langfuse = observabilidad, pero no evaluación. Para evaluar calidad (si “da lo que tiene que dar”) sigue faltando integrar métricas / RAGAS u otro sistema de evaluación.
- Se gestionó acceso: se pidió y compartió código de un solo uso de Bitwarden para que todos puedan acceder a Langfuse y ver estadísticas.
- Cambios de despliegue (infra):
  - Se ajustó el despliegue por problemas de recursos: la imagen era pesada (Ollama), se amplió el disco a 20 GB y se corrigió el montaje del disco.
  - Se actualizó el playbook de Ansible (preconfiguración) y se fijaron dependencias/versiones necesarias para Chroma: la versión usada para crear el vectorstore debe ser compatible con la usada para leerlo.
- Observabilidad avanzada / mejora futura:
  - Se propuso añadir tracking por sesión en Langfuse (un usuario con varias preguntas agrupadas).
  - Se sugirió incluir feedback del usuario (thumbs up/down) tras cada respuesta: si Langfuse está activo se registra; si no, no rompe nada. Se debatió su utilidad (más valioso en la parte generativa de reportes que en clasificaciones “no creativas”), pero se mantiene como mejora y elemento presentable.
- Testing:
  - Se comentó que, por ahora, se han hecho smoke tests manuales (y logs del contenedor Docker). Langfuse permite verificar si el flujo pasa por donde debe.
  - Plan operativo: mergear primero PRs de infra + observabilidad (menos riesgo), luego fixes, levantar nueva imagen y re-probar. Si hace falta, añadir tests en Python más adelante.
- Problema crítico detectado en RAG (performance/calidad):
  - Una ejecución tardó muchísimo y se sospecha un mismatch de embeddings/modelo entre ingest/index (hecho por una persona) y retriever (hecho por otra).
  - Síntoma: recupera documentos pero los trata “todos iguales”/no discrimina bien → posible incompatibilidad de embeddings.
  - Acción: forzar explícitamente el mismo modelo de embeddings en ingest, index y retriever. Hay una solución propuesta por Claude; se aplicará y se re-testeará.
- Clasificador (ML):
  - Se revisó la interpretación de outputs: probabilidades por clase (mínimo/limitado/alto/inaceptable) y valores de “confidence”.
  - Se detectó confusión sobre qué modelo está usando realmente (parece que el mejor era Logistic Regression, pero a veces termina usando XGBoost).
  - Acción: ajustar main.py para forzar/cargar correctamente el modelo elegido o hacerlo configurable por variables de entorno, y loguear en Langfuse qué modelo se usó en cada ejecución.
- Report (generación de informe):
  - Se vio que no aparece traza de Langfuse para report → falta instrumentación/logs.
  - Acción: añadir tracking de Langfuse al flujo de report y, si procede, dashboards en Langfuse (más adelante).
- Coordinación y próximas acciones:
  - Prioridad inmediata: aprobar PRs, especialmente la de ML y la de infra/observabilidad, para que Persona D pueda re-probar el despliegue con trazas nuevas.
  - Tras estabilizar y tener observabilidad, se abordará mejora de salidas y registro de iteraciones (y posibles guardrails/validaciones simples).
- Organización:
  - Se acordó una reunión el sábado a las 19:00 (por disponibilidad de Persona B; situación familiar). Se seguirá coordinando por chat.

## <a name="_5k66yja4ccqf"></a>**Resumen de la reunión**
- Se revisaron mejoras opcionales para aumentar el impacto del proyecto una vez esté estable (post “versión 1”):
  - Análisis de sesgos del clasificador: ampliar el análisis actual (métricas por etiqueta) con desglose por subcategorías (si existe metadata/columnas), interpretación escrita de errores (p. ej. confusiones entre clases), intervalos de confianza y recomendaciones.
    - Acción: Persona C se lo asigna; se hará en un notebook nuevo y en una rama independiente desde develop (si no aporta o falla, no se mergea).
  - Sistema de feedback del usuario + memoria conversacional: se habló de thumbs up/down y comentario opcional, y memoria por sesión.
    - Estado: Persona D comenta que se retiró temporalmente de su PR por incompatibilidades de versión de Langfuse y porque no estaba funcionando bien el tracking por sesión.
    - Se discutió el coste/infra: ambas cosas probablemente requieren persistencia en BD, pero al ser demo puede ser una BD simple (pendiente de decidir).
    - Acción: Persona C se pone memoria conversacional (al menos intra-sesión) y feedback como opción si encaja.
  - Mejoras del Report: posibilidad de incluir sugerencias para hacer el sistema “aceptable” cuando salga “inaceptable” (recomendaciones prácticas derivadas del contexto).
- Guardrails/seguridad:
  - Se comentó que, usando Nova, ya hay guardrails del propio modelo; se deja en standby por retorno limitado frente al esfuerzo.
- Prioridad alta propuesta: Fine-tuning del modelo de “grading” del RAG (el que decide si los documentos recuperados son relevantes/no relevantes):
  - Motivo: es una tarea binaria y específica, donde el fine-tuning puede aportar puntos.
  - Responsable: se pidió a Persona B que lo lidere (tiene mejor GPU/capacidad).
  - Ubicación técnica: el modelo actual se llama desde SRC/RAG/... (función get\_llm) usando Qwen; la idea es sustituirlo por el modelo fine-tuneado.
  - Organización: crear una rama específica y una carpeta propia en SRC similar a classifier (data + notebook + artefactos del modelo). Se mencionó usar LoRA/QLoRA y reutilizar queries existentes como base.
  - Apoyo: se pidió ayuda para:
    - generar dataset sintético de entrenamiento,
    - preparar consultas “sesudas” para evaluar el modelo fine-tuneado.
- Documentación y calidad:
  - Documentar prompts: registrar versión actual de prompts, iteraciones y resultados (para mostrar proceso y control de alucinaciones). Se ofreció a Persona D y Persona A participar.
  - Documentar “grading” como reranking: revisar los issues 73 y 75 (Persona A se lo lleva para entenderlo y documentarlo).
- Plan de trabajo / estabilidad:
  - Antes de meter mejoras, se acordó cerrar una “versión 1” estable: fixes → merge de PRs → build de nueva imagen Docker → redeploy y re-probar.
  - Se decidió esperar el review del CodeRabbit antes de mergear (para evitar rehacer PRs por issues críticos).
- Datos del proyecto:
  - Se aclaró que el corpus actual está centrado en IA, y además se recordó que el roadmap contemplaba también sector financiero y protección de datos.
  - Persona A revisará si hay más fuentes relevantes para regulación IA/finanzas/privacidad y lo irá comunicando.
- Acciones inmediatas:
  - Persona C: abrir rama para notebook de sesgos y avanzar memoria/feedback según viabilidad.
  - Persona B: revisar y liderar fine-tuning del grading (con apoyo del equipo).
  - Persona A: revisar issues 73/75 (grading/reranking), explorar datos adicionales, y compartir su repo de la práctica de “derecha” como referencia (ya lo dejó en Discord).
  - Persona D: resolver lo pendiente de PRs, esperar CodeRabbit, mergear y re-desplegar para re-probar el sistema completo.

## <a name="_fp11j2fwmjrc"></a>**Resumen de la reunión (último tramo)**
- GPU / coste
  - Se asume que no se va a “forzar” GPU salvo necesidad.
  - Se comenta que un modelo fine-tuneado y cuantizado podría incluso bajar peso/parámetros y aliviar recursos.
- Tema claves / acceso AWS (EC2 + SSH)
  - Persona D recuerda revisar claves SSH para que el equipo pueda desplegar aunque ella no esté.
  - Ya se añadieron claves (incluida la de Persona C). Con permisos para listar/iniciar/parar/reiniciar EC2, pero para entrar hace falta la clave SSH.
  - Persona B tuvo un fallo con “Enter Passphrase” / directorios en Windows; se deja para resolverlo luego (probable ruta distinta en Windows).
- Reparto de trabajo (bugs / issues)
  - Se acuerda dividirse y trabajar cada uno en su rama.
  - Persona C está documentando causa raíz de cada bug en un .md para no parchear a ciegas (evitar “parche → salen 3 bugs nuevos”).
- Deadline y preparación de entrega
  - Quieren reservar mínimo 3 días para preparar presentación + defensa (preguntas posibles, detalles técnicos).
  - Objetivo: domingo “cerrado” (tener versión estable), luego días para estudiar y preparar el pitch.
- Problemas específicos discutidos
  - No determinismo / citas reinventadas: al citar artículos, el LLM “reinterpreta” y devuelve algo no determinista. Persona C separa “fuente estricta de artículos reales” vs “respuesta del LLM”.
  - Bug del “grader demasiado restrictivo” (rechaza artículos aplicables, p.ej. art. 26): se asigna para revisarlo (afecta calidad del RAG).
  - Confusión “inaceptable” vs “alto riesgo” en el clasificador (override):
    - Hay un mecanismo de override: si detecta palabras muy específicas del EU AI Act, se impone una clase por encima del modelo ML.
    - Se debate si esto es “demasiado parche” y si la frontera legal es realmente ambigua; incluso se considera que, en legal, ser más conservador (predicción más restrictiva) puede ser aceptable.
    - Plan: ampliar dataset con más ejemplos de esas categorías y reentrenar/ajustar en rama; si no mejora, se descarta.
- Plan inmediato acordado
  - Persona C: hoy se centra en ampliar dataset para mejorar la distinción alto riesgo vs inaceptable + revisar bugs 1/3.
  - Persona A: revisar issues 4 y 5 (más “suaves”), y revalidar issue 73 (grading/prompt engineering) ahora que se re-chunkeó y cambió data.
  - Persona B: revisar lo de observación (trazas/diagnóstico) y también el tema de clave SSH en su entorno.
- Despliegue
  - Se pospone desplegar hasta que haya claridad de causa raíz y fixes más sólidos.
  - Aun así, con el acceso que da Persona D, podrían desplegar mañana/pasado si hace falta, pero Persona C pide un día para analizar bien antes de tocar más producción.

## <a name="_xkibwcnitx3h"></a>**Resumen (reunión / avance técnico)**
### <a name="_ieys38sf93hv"></a>**1) Experimentos del clasificador (alto riesgo vs inaceptable)**
- Se probó ampliar el dataset y crear reglas regex (variantes con guiones, tildes, etc.) para mejorar robustez.
- Resultado: no mejora el F1; en algunos intentos se queda igual o baja.
- Conclusión: el modelo sigue sin aprender bien los casos “inaceptable” incluso con ejemplos muy literales del anexo; se mantiene el override como solución práctica.
- Idea propuesta: usar umbral de confianza: si la confianza es baja, ir al lado más restrictivo (clasificar como inaceptable “en caso de duda”).
### <a name="_avqco27j6dc9"></a>**2) Enfoque general sobre bugs**
- Se asume que siempre habrá bugs; la prioridad es que no escondan incoherencias graves.
- Los bugs actuales son más específicos (antes eran “gruesos”). Cambios en una pieza (retriever/grader/vectorstore) pueden disparar efectos colaterales.
### <a name="_iuuk4y21duc6"></a>**3) Bug 1: “doble llamada al clasificador / herramienta de report”**
- Se detecta un problema de arquitectura: hay un orquestador con LLM y además una tool “Generate report” que también es una llamada LLM → redundante.
- Propuesta (implementada en una rama):
  - Eliminar la tool de “report” (evita caja negra sobre caja negra y distorsión).
  - Quedarse con 1 agente orquestador + 2 tools principales (RAG/búsqueda y clasificador).
  - Mover al clasificador la parte de recomendaciones/sugerencias (deterministas) basadas en gaps legales detectados.
### <a name="_r293cziuj5bi"></a>**4) Fine-tuning (rama ya lista)**
- Se comenta que la rama de Fine-Tuning está completa y puede “lucir” en el proyecto.
- Dudas: introducir muchos cambios a la vez sin despliegues rápidos hace difícil aislar qué rompe qué.
- Se sugiere ir con cambios más controlados, pero el FT queda como opción fuerte si aporta mejora.
### <a name="_ru46y5gsjont"></a>**5) RAG / grader y evaluación**
- Se revisa el bug del grader demasiado restrictivo y el fallback cuando se quedan 0 documentos.
- Se acuerda dejarlo en stand-by hasta que Persona D implemente RAGAS, porque:
  - Sin evaluación, no se sabe si “0 docs” es porque no existen o porque el grader falla.
  - RAGAS serviría para medir utilidad real del RAG y comparar antes/después (distinto a métricas internas del fine-tuning).
### <a name="_gbbninjjvgb3"></a>**6) Bug 3 (artículo 10 confuso: LOPD vs Data Governance / EU)**
- Caso: al pedir “artículo 10”, a veces recupera el de otra norma (por densidad semántica de “datos”).
- Se plantea que faltan señales/metadata para forzar la fuente correcta:
  - Añadir/usar metadata de norma/fuente + artículo.
  - Forzar en la query “artículo X de [norma]”.
- Se reconoce que estos solapes son normales en RAG (equilibrios imperfectos); no se considera bloqueante para defensa si se explica.
### <a name="_pfxdxk4881d6"></a>**7) Idea futura: agente de actualización normativa**
- Propuesta ambiciosa: un agente separado que detecte cambios en fuentes (p.ej. BOE), genere DIF + resumen, y deje la actualización en estado pendiente para aprobación humana.
- Se discute el riesgo ético: si actualiza solo, un error se propaga. Solución: human-in-the-loop (aprobación manual).
- Se deja como exploración/posible mejora; mañana se puede pensar arquitectura sin implementar.
### <a name="_5bna6uxseyov"></a>**8) Operativa (PRs / revisión / despliegue)**
- Se decide no mergear cambios grandes sin validación de Persona D (no está hasta jueves).
- PRs relevantes mencionadas:
  - Refactor (p.ej. PR 103/104/106) y memoria chat (PR 82) pendientes de visto bueno.
- Se comenta tooling:
  - CodeRabbit: gratis en repos públicos.
  - Ruff: lint para errores mecánicos (imports no usados, etc.), está en manos de Persona D.
### <a name="_pax8958t18r"></a>**9) Próximos pasos**
- Hasta que vuelva Persona D: avanzar en discusión de arquitectura y preparar qué se quiere cerrar de aquí al domingo.
- Objetivo de calendario: cerrar estable domingo y reservar días para preparación de defensa/presentación.

### <a name="_vswvopqh5yun"></a>**1) Tema central: decidir foco por tiempo**
- Se mencionó la idea que se había comentado días atrás: hacer que la herramienta se actualice sola (agente/automatización de actualización).
- Persona D puso foco en que, por tiempo, lo prioritario es: desplegar lo que hay ahora y probar (“asegurar lo que tenemos”) antes de abrir más caminos.
### <a name="_1s375achbu8k"></a>**2) Estado del trabajo técnico**
- Persona B comentó que hoy no avanzó en features nuevas: se dedicó a asegurar el estado actual y a pasarle cosas a Claude para que revise bugs.
- Se habló de que hay muchas PRs y bastante refactor/limpieza en marcha.
### <a name="_cio1ptc2c8z4"></a>**3) Acciones acordadas (corto plazo)**
- Probar y mergear lo que ya está listo.
- Persona D se compromete a probar la parte de RAGAS/evaluación (o “la evaluación”) y, si no cuadra, se ajusta después.
- Se revisan comentarios menores en PR y se sigue por chat; no hace falta reunión larga para eso.
### <a name="_9v5e664jpqlh"></a>**4) Cierre**
- Se da por hecho que, después de varios días de iteraciones, “muy mal se tiene que dar” para que los bugs principales no estén ya encarrilados.
- Se corta la reunión para ejecutar pruebas/merges y seguir coordinando por chat.

## <a name="_i5h6r4pe9ft8"></a>**Resumen de la reunión**
### <a name="_is48mdns5dch"></a>**1) Estado del modelo BERT**
- Persona B ya dejó montada la versión con BERT.
- La sensación general es que mejora algo las métricas, pero sigue existiendo una limitación importante: tanto el dataset de entrenamiento como parte de la validación son sintéticos, así que hay que mencionar esa debilidad en la presentación.
### <a name="_mn94ra3xnvu4"></a>**2) Qué hizo Persona B hoy**
- Integró BERT en el mismo punto donde estaba el modelo anterior, sin cambiar demasiado la estructura.
- Reequilibró el dataset y además hizo una aumentación por paráfrasis:
  - cada fila se multiplicó por 5,
  - expresando la misma idea de formas distintas,
  - con el objetivo de que el modelo aprenda mejor el significado y no solo palabras concretas.
- También avanzó en la PR del fine-tuning.
- Queda una duda técnica: Persona C advierte que esa multiplicación/paráfrasis podría estar generando dependencia artificial entre ejemplos y quizá más overfitting, así que se plantea comparar con el dataset sin esa aumentación.
### <a name="_mtojfse170yg"></a>**3) Interpretación del informe de evaluación / RAGAS**
- Persona D comenta que hay varios puntos abiertos y que no está del todo claro cómo cerrarlo todo sin volver a probar.
- La lectura compartida del informe fue esta:
  - Context Recall bajo: el retriever está trayendo pocos documentos útiles; posible solución: subir K.
  - Faithfulness bajo: el grader/filtrado está siendo demasiado restrictivo, llega poco contexto al orquestador y entonces el sistema alucina o inventa.
  - Answer Relevancy: podría mejorar con el fine-tuning del modelo que se usa en esa parte.
- Se concluye que no parece que haya que rehacer nada desde cero, sino afinar hiperparámetros, prompt y retrieval.
### <a name="_8ddqd4c6g49g"></a>**4) Decisiones técnicas para cerrar**
- Antes de meter cosas más grandes, acuerdan probar esta combinación:
  - subir K en el retriever,
  - mejorar el prompt,
  - y evaluar si con eso el bug 5 queda suficientemente cubierto.
- Persona A se encarga de esa parte en su rama del bug 5.
- Persona B revisa los comentarios de CodeRabbit en la PR de BERT.
- Persona D volverá a lanzar el despliegue mañana por la mañana, no esta noche, para poder hacerlo con más calma.
### <a name="_xz1y5sl6s6ys"></a>**5) Fine-tuning**
- El fine-tuning sigue sobre la mesa como mejora real, sobre todo para el bloque donde podría subir la relevancia de respuestas.
- Pero el acuerdo implícito es no meter demasiados cambios a la vez sin probar primero el ajuste de K + prompt.
### <a name="_5dru6xppe81o"></a>**6) Reflexión sobre el clasificador**
- Persona C comenta que, si hubiera más tiempo, probablemente rehacería la parte de clasificación con:
  - un dataset mucho más grande,
  - más equilibrado,
  - menos dependiente de generación rápida con LLM,
  - y quizá mezclado con datos más reales o mejor revisados.
- Se plantea esto como aprendizaje y mejora futura, más que como algo a rehacer ya.
### <a name="_jqbgylxu3p20"></a>**7) Cierre y plan de trabajo**
- Objetivo inmediato:
  - dejar hoy listas las PRs de Persona B y Persona A,
  - que Persona D haga el despliegue mañana por la mañana,
  - y volver a reunirse mañana por la tarde sobre las 17:00 para cerrar.
- Si todo sale bien, a partir de ahí se pasa ya a:
  - presentación,
  - posible vídeo demo,
  - narrativa tipo producto/cliente,
  - y costes / arquitectura / aprendizajes.
### <a name="_htabume469z8"></a>**8) Presentación**
- Recordaron que la defensa tiene dos capas:
  - una más orientada a producto / cliente,
  - y otra más académica/técnica.
- También quieren incluir:
  - costes,
  - decisiones técnicas,
  - historial de cambios y aprendizajes,
  - y aprovechar lo ya documentado en commits, PRs y resúmenes de reuniones.

<a name="_m9rlzu3yrbac"></a>**Resumen de la reunión**

<a name="_6asiiodeiftn"></a>**1) Estado de la evaluación (RAGAS)**

- El sistema seguía ejecutando la evaluación durante horas y finalmente terminó fallando por timeout tras más de 4 horas.
- El proceso estaba tardando mucho porque:
  - el grader (LLaMA) estaba tardando ~10 minutos por pregunta,
  - la evaluación tenía 16 preguntas,
  - y además se ejecutaban llamadas adicionales para calcular métricas.
- Se detectó que muchas consultas estaban cayendo en fallback, lo que indica que:
  - el grader está descartando demasiados documentos, o
  - el modelo no está clasificando bien la relevancia.
-----
<a name="_4dlrb17cazg9"></a>**2) Diagnóstico técnico del problema**

El equipo intenta identificar dónde está fallando el pipeline RAG.

<a name="_sv5323i5z8z1"></a>**Posibles causas analizadas**

1. Chunks
   1. Probablemente no es el problema.
   1. Ya se habían obtenido respuestas correctas anteriormente.
   1. Además el tamaño está dentro del límite del modelo.
1. Retriever
   1. Parece que sí recupera documentos.
   1. Su función es traer documentos semánticamente relacionados.
1. Grader (modelo LLM)
   1. Es el principal sospechoso.
   1. Está rechazando muchos documentos relevantes.
   1. Por eso el sistema cae frecuentemente en fallback por score.
1. Dataset de evaluación
   1. Algunas respuestas esperadas no están exactamente escritas igual que en la normativa.
   1. Eso puede afectar la evaluación semántica.
-----
<a name="_55intksbozwz"></a>**3) Cómo funciona realmente el flujo RAG (según la discusión)**

El pipeline se resumió así:

1. Usuario hace una query
1. Retriever busca documentos en la base vectorial
1. Grader (LLM) decide si esos documentos son relevantes
1. Si los descarta todos → fallback
1. El sistema responde usando otra lógica o puntuación semántica

Problema actual:

- El grader está siendo demasiado estricto
- Muchos documentos válidos se descartan
- Por eso aparecen muchos warnings y fallback
-----
<a name="_shlc9pugwiro"></a>**4) Propuestas técnicas que se discutieron**

Varias ideas para intentar mejorar el comportamiento:

<a name="_48kv8lkoq076"></a>**Ajustes posibles**

- Loggear mejor:
  - qué chunks recupera el retriever
  - qué decide el grader
- Analizar una sola query para ver el flujo completo.
- Revisar si la respuesta esperada del test coincide realmente con el artículo legal.
- Ajustar el score threshold del fallback.
- Cambiar modelo del grader.
- Usar GPU para acelerar pruebas.

<a name="_qh4c33t72m62"></a>**Propuesta concreta de Persona B**

- Probar la versión con BERT + fine-tuning
- Si funciona mal → rollback a la versión actual.
-----
<a name="_ilboze5qb0h8"></a>**5) Decisión estratégica del equipo**

El grupo reconoce que:

- El proyecto era muy ambicioso.
- El sistema completo tiene muchos puntos de fallo encadenados:
  - dataset sintético
  - clasificación
  - RAG retrieval
  - LLM grader
- Arreglarlo bien requeriría mucho más tiempo.

Por eso se plantea un cambio de enfoque:

<a name="_756m1vsytlp4"></a>**En la presentación**

En lugar de fingir que todo funciona perfecto:

- explicar qué se intentó construir
- mostrar dónde falla
- explicar por qué falla
- demostrar que se entienden bien los conceptos

Esto se considera incluso valioso académicamente.

-----
<a name="_5tqfai8kfi5y"></a>**6) Preparación de la presentación**

Se empieza a organizar la defensa final.

<a name="_tc8luqne0a0q"></a>**Duración**

- 15 min presentación
- 15 min preguntas

<a name="_5alcpikqcq7b"></a>**Posible reparto**

- Pitch inicial: Persona A
- Demo: alguien con GPU disponible
- Parte técnica: repartir entre los demás
- Conclusiones / mejoras futuras: grupo

<a name="_rc6zrikxwt52"></a>**Estrategia**

- presentar el proyecto como MVP
- explicar arquitectura
- justificar decisiones técnicas
- hablar de costes, escalabilidad y mejoras futuras
-----
<a name="_ri91fnemv5qf"></a>**7) Plan inmediato**

1. Probar merge de las ramas nuevas (BERT / mejoras).
1. Desplegar una nueva versión para test.
1. Si funciona mal → rollback.
1. Empezar a preparar la presentación final.
-----
✔ Conclusión de la reunión:

El equipo acepta que el sistema no está completamente optimizado, pero decide enfocarse en explicar correctamente el aprendizaje técnico, la arquitectura y los problemas encontrados, en lugar de intentar forzar un resultado perfecto a última hora.


[ref1]: data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAjcAAAAICAYAAAAFm97/AAAABHNCSVQICAgIfAhkiAAAAAlwSFlzAAAOxAAADsQBlSsOGwAAADJJREFUeJztzjERAAAIBCDtH/HDaArPBRJQBQAAAAAAAOc6yXwnAAAAAAAAAAAAAIAfC1PtA5IGL5gkAAAAAElFTkSuQmCC
[ref2]: data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAjcAAAAICAYAAAAFm97/AAAABHNCSVQICAgIfAhkiAAAAAlwSFlzAAAOxAAADsQBlSsOGwAAADJJREFUeJztzjERAAAIBCDtX+U7agrPBRJQBQAAAAAAAOc6yXwnAAAAAAAAAAAAAIAfC+rzAwUxxmqQAAAAAElFTkSuQmCC
