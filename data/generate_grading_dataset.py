#!/usr/bin/env python3
"""
generate_grading_dataset.py — Genera el dataset de relevancia para el grader RAG de NormaBot.

Escribe data/processed/grading_dataset.jsonl con pares (query, documento, label)
para entrenar el clasificador de relevancia Qwen 2.5 3B.

Fuentes:
  - 10 queries de data/eval/rag_complex_queries_results.json
  - 100 queries adicionales sobre EU AI Act, RGPD/LOPD y AESIA

Formato de salida (una línea por ejemplo):
  {"query": "...", "document": "...", "label": "relevante|no relevante"}

Ejecutar:
  python data/generate_grading_dataset.py
"""

import json
import random
from pathlib import Path

random.seed(42)

# ============================================================
# 1. BIBLIOTECA DE FRAGMENTOS DOCUMENTALES
# ============================================================
# Fragmentos representativos de cada artículo/fuente.
# Los textos son fieles al contenido de las fuentes pero sintetizados
# para el propósito de entrenamiento.

DOCS: dict[str, dict] = {

    # ---- EU AI ACT — Artículo 5: Prohibiciones ----
    "eu5_subliminal": {
        "source": "eu_ai_act",
        "text": (
            "Artículo 5.1.a) Reglamento (UE) 2024/1689 (EU AI Act) — Prácticas de IA prohibidas. "
            "Queda prohibida la comercialización, puesta en servicio o utilización de sistemas de IA "
            "que empleen técnicas subliminales que actúen más allá de la conciencia de una persona, "
            "o técnicas deliberadamente manipuladoras o engañosas, con el objetivo de distorsionar "
            "materialmente el comportamiento de dicha persona de un modo que le cause o pueda causarle "
            "a ella o a terceros un perjuicio significativo."
        ),
    },
    "eu5_scoring_social": {
        "source": "eu_ai_act",
        "text": (
            "Artículo 5.1.c) EU AI Act — Prácticas de IA prohibidas. "
            "Queda prohibida la utilización de sistemas de IA por poderes públicos para evaluar o clasificar "
            "a personas físicas o grupos basándose en su comportamiento social o características personales "
            "cuando produzca trato desfavorable en contextos sin relación con aquellos en que se generaron "
            "los datos, o trato injustificado o desproporcionado respecto a la gravedad de su comportamiento."
        ),
    },
    "eu5_biomet_remota": {
        "source": "eu_ai_act",
        "text": (
            "Artículo 5.1.h) EU AI Act — Prácticas de IA prohibidas. "
            "Queda prohibida la utilización de sistemas de identificación biométrica remota en tiempo real "
            "en espacios de acceso público con fines de aplicación de la ley, salvo en casos estrictamente "
            "delimitados: búsqueda de víctimas de secuestro o trata, prevención de amenazas terroristas "
            "inminentes, o localización de personas buscadas por delitos punibles con pena privativa de libertad "
            "de al menos cuatro años. En esos casos se exige autorización judicial previa."
        ),
    },
    "eu5_vulnerabilidades": {
        "source": "eu_ai_act",
        "text": (
            "Artículo 5.1.b) EU AI Act — Prácticas de IA prohibidas. "
            "Queda prohibida la comercialización o utilización de sistemas de IA que aprovechen "
            "vulnerabilidades de personas derivadas de su edad, discapacidad o situación socioeconómica, "
            "con la intención de distorsionar materialmente su comportamiento de un modo que les cause "
            "o pueda causarles a ellas o a terceros un perjuicio significativo."
        ),
    },
    "eu5_categorizacion_biomet": {
        "source": "eu_ai_act",
        "text": (
            "Artículo 5.1.g) EU AI Act — Prácticas de IA prohibidas. "
            "Quedan prohibidos los sistemas de categorización biométrica que clasifiquen individualmente "
            "a personas físicas para deducir o inferir su raza, opiniones políticas, afiliación sindical, "
            "creencias religiosas o filosóficas, vida sexual u orientación sexual. "
            "Se exceptúa el etiquetado o filtrado lícito de conjuntos de datos biométricos en el contexto "
            "de la aplicación de la ley con arreglo al Derecho de la Unión."
        ),
    },
    "eu5_prediccion_riesgo": {
        "source": "eu_ai_act",
        "text": (
            "Artículo 5.1.d) EU AI Act — Prácticas de IA prohibidas. "
            "Queda prohibida la utilización de sistemas de IA con fines de evaluación del riesgo "
            "o predicción del riesgo de comisión de infracciones penales por personas físicas, "
            "basándose únicamente en la elaboración de perfiles o en la evaluación de rasgos y "
            "características de la personalidad. "
            "La prohibición no se aplica a los sistemas de IA utilizados como apoyo a la evaluación "
            "del riesgo humana basada en hechos objetivos y verificables."
        ),
    },

    # ---- EU AI ACT — Artículo 6 + Anexo III: Alto riesgo ----
    "eu6_clasificacion": {
        "source": "eu_ai_act",
        "text": (
            "Artículo 6 EU AI Act — Reglas de clasificación de los sistemas de IA como de alto riesgo. "
            "Un sistema de IA se considerará de alto riesgo cuando: a) sea un componente de seguridad de un "
            "producto cubierto por la legislación de armonización de la Unión del Anexo I; y b) ese producto "
            "esté sujeto a evaluación de conformidad con terceros. Asimismo, los sistemas de IA enumerados "
            "en el Anexo III se considerarán de alto riesgo, excepto si el proveedor demuestra que no plantean "
            "un riesgo significativo para la salud, la seguridad o los derechos fundamentales."
        ),
    },
    "eu_anex3_rrhh": {
        "source": "eu_ai_act",
        "text": (
            "Anexo III, punto 4 EU AI Act — Sistemas de IA de alto riesgo: empleo y gestión de trabajadores. "
            "Se consideran de alto riesgo los sistemas de IA utilizados para: a) el reclutamiento o la selección "
            "de personas, en particular para publicar anuncios de trabajo, filtrar solicitudes o evaluar candidatos "
            "en entrevistas; b) decisiones sobre la promoción, rescisión contractual o asignación de tareas "
            "mediante seguimiento del comportamiento o el rendimiento individual."
        ),
    },
    "eu_anex3_educacion": {
        "source": "eu_ai_act",
        "text": (
            "Anexo III, punto 3 EU AI Act — Sistemas de IA de alto riesgo: educación y formación profesional. "
            "Se consideran de alto riesgo los sistemas de IA utilizados para: a) determinar el acceso o admisión "
            "de personas a instituciones educativas; b) evaluar resultados de aprendizaje que condicionen el acceso "
            "a la educación; c) evaluar el nivel educativo apropiado y orientar el proceso de aprendizaje; "
            "d) supervisar y detectar comportamientos prohibidos en el marco de exámenes."
        ),
    },
    "eu_anex3_credito": {
        "source": "eu_ai_act",
        "text": (
            "Anexo III, punto 5.b) EU AI Act — Sistemas de IA de alto riesgo: servicios financieros. "
            "Se consideran de alto riesgo los sistemas de IA utilizados para evaluar la solvencia crediticia "
            "de personas físicas o establecer su puntuación de crédito, excepto los sistemas destinados "
            "únicamente a detectar fraude financiero."
        ),
    },
    "eu_anex3_infraestructura": {
        "source": "eu_ai_act",
        "text": (
            "Anexo III, punto 2 EU AI Act — Sistemas de IA de alto riesgo: infraestructuras críticas. "
            "Se consideran de alto riesgo los sistemas de IA destinados a ser utilizados como componentes "
            "de seguridad en la gestión y el funcionamiento de infraestructuras críticas: "
            "redes de suministro de agua, gas, calefacción y electricidad; tráfico ferroviario; "
            "infraestructura digital crítica."
        ),
    },
    "eu_anex3_judicial": {
        "source": "eu_ai_act",
        "text": (
            "Anexo III, punto 8 EU AI Act — Sistemas de IA de alto riesgo: administración de justicia. "
            "Se consideran de alto riesgo los sistemas de IA utilizados para: a) asistir a autoridades "
            "judiciales en la investigación e interpretación de hechos y la aplicación del Derecho; "
            "b) influir en el resultado de elecciones o referendos, o en el comportamiento electoral "
            "de las personas físicas."
        ),
    },
    "eu_anex3_migracion": {
        "source": "eu_ai_act",
        "text": (
            "Anexo III, punto 7 EU AI Act — Sistemas de IA de alto riesgo: migración, asilo y fronteras. "
            "Se consideran de alto riesgo los sistemas de IA utilizados para: a) evaluación del riesgo "
            "de personas que soliciten visado, asilo o quieran cruzar una frontera; b) verificación de "
            "documentos de viaje; c) sistemas de detección biométrica en puntos de paso fronterizo."
        ),
    },
    "eu_anex3_sanidad": {
        "source": "eu_ai_act",
        "text": (
            "Anexo III, punto 1 y Anexo I, sección A EU AI Act — Sistemas de IA de alto riesgo en sanidad. "
            "Los sistemas de IA como componentes de seguridad de productos sanitarios regulados por el "
            "Reglamento (UE) 2017/745 (MDR) y el Reglamento (UE) 2017/746 (IVDR) se consideran de alto riesgo. "
            "Esto incluye sistemas de apoyo al diagnóstico por imagen, sistemas de triage automatizado "
            "y herramientas de decisión clínica que tengan impacto directo en el paciente."
        ),
    },

    # ---- EU AI ACT — Artículos 9–15: Requisitos técnicos ----
    "eu9_gestion_riesgos": {
        "source": "eu_ai_act",
        "text": (
            "Artículo 9 EU AI Act — Sistema de gestión de riesgos. "
            "Para los sistemas de IA de alto riesgo se establecerá, aplicará, documentará y mantendrá "
            "un sistema de gestión de riesgos que consista en un proceso iterativo continuo a lo largo "
            "de todo el ciclo de vida. Comprenderá: a) identificación y análisis de riesgos razonablemente "
            "previsibles; b) estimación de los riesgos que se produzcan cuando el sistema se ponga en servicio; "
            "c) adopción de medidas de gestión del riesgo apropiadas; d) revisión y actualización periódica."
        ),
    },
    "eu10_datos": {
        "source": "eu_ai_act",
        "text": (
            "Artículo 10 EU AI Act — Datos y gobernanza de datos. "
            "Los sistemas de IA de alto riesgo que utilicen entrenamiento de modelos se desarrollarán "
            "sobre conjuntos de datos de entrenamiento, validación y prueba que satisfagan criterios de "
            "calidad y se sometan a prácticas de gobernanza adecuadas. Estas prácticas incluirán: "
            "diseño de la elección de datos, recopilación, preparación, examen de posibles sesgos "
            "que puedan afectar a la salud, la seguridad o los derechos fundamentales."
        ),
    },
    "eu11_doc_tecnica": {
        "source": "eu_ai_act",
        "text": (
            "Artículo 11 EU AI Act — Documentación técnica. "
            "La documentación técnica de un sistema de IA de alto riesgo se elaborará antes de su "
            "introducción en el mercado y se mantendrá actualizada. Demostrará que el sistema cumple "
            "los requisitos del Capítulo 2 y facilitará a las autoridades la información necesaria "
            "para evaluar el cumplimiento. Como mínimo incluirá los elementos del Anexo IV: "
            "descripción general, diseño del sistema, información sobre datos de entrenamiento, "
            "medidas de supervisión humana y especificaciones de rendimiento."
        ),
    },
    "eu12_logs": {
        "source": "eu_ai_act",
        "text": (
            "Artículo 12 EU AI Act — Registro. "
            "Los sistemas de IA de alto riesgo permitirán el registro automático de eventos (logs) "
            "a lo largo de su vida útil, de forma proporcional a la finalidad prevista. "
            "Como mínimo se registrará: a) el período de cada uso; b) la base de datos de referencia "
            "utilizada en la verificación; c) los datos de entrada que hayan dado un resultado positivo; "
            "d) la identificación de las personas implicadas en la verificación de resultados. "
            "Los logs se conservarán durante el período establecido por la normativa aplicable."
        ),
    },
    "eu13_transparencia_desplegador": {
        "source": "eu_ai_act",
        "text": (
            "Artículo 13 EU AI Act — Transparencia y provisión de información a los desplegadores. "
            "Los sistemas de IA de alto riesgo se diseñarán para que su funcionamiento sea suficientemente "
            "transparente para permitir a los desplegadores interpretar y utilizar adecuadamente los resultados. "
            "Irán acompañados de instrucciones de uso que incluirán: identidad del proveedor, "
            "finalidad prevista y condiciones de uso, nivel de exactitud, medidas de supervisión humana "
            "y los riesgos previsibles para la salud, seguridad y derechos fundamentales."
        ),
    },
    "eu14_supervision_humana": {
        "source": "eu_ai_act",
        "text": (
            "Artículo 14 EU AI Act — Supervisión humana. "
            "Los sistemas de IA de alto riesgo se diseñarán para que personas físicas puedan supervisarlos "
            "de forma eficaz durante el período de uso. Las medidas incluirán: a) posibilidad de comprender "
            "las capacidades y limitaciones del sistema; b) posibilidad de detectar e interpretar "
            "disfunciones; c) posibilidad de desconectar el sistema mediante un botón de parada; "
            "d) posibilidad de no tener en cuenta, anular o revertir las decisiones automatizadas."
        ),
    },
    "eu15_exactitud": {
        "source": "eu_ai_act",
        "text": (
            "Artículo 15 EU AI Act — Exactitud, solidez y ciberseguridad. "
            "Los sistemas de IA de alto riesgo alcanzarán un nivel apropiado de exactitud, solidez "
            "y ciberseguridad a lo largo de su ciclo de vida. Los niveles de exactitud e indicadores "
            "pertinentes se indicarán en las instrucciones de uso. Los sistemas serán resilientes "
            "frente a errores, fallos o inconsistencias y frente a intentos no autorizados de alterar "
            "su uso, comportamiento o rendimiento (resiliencia ante ataques adversariales)."
        ),
    },

    # ---- EU AI ACT — Artículos 16–26: Obligaciones ----
    "eu16_obligaciones_prov": {
        "source": "eu_ai_act",
        "text": (
            "Artículo 16 EU AI Act — Obligaciones de los proveedores de sistemas de IA de alto riesgo. "
            "Los proveedores: a) garantizarán el cumplimiento de los requisitos del Capítulo 2; "
            "b) indicarán su nombre y datos de contacto en el sistema; c) establecerán un sistema "
            "de gestión de la calidad; d) mantendrán la documentación técnica; e) conservarán los logs; "
            "f) garantizarán que el sistema supere la evaluación de conformidad; g) se registrarán "
            "en la base de datos de la UE y elaborarán la declaración UE de conformidad."
        ),
    },
    "eu17_sgc": {
        "source": "eu_ai_act",
        "text": (
            "Artículo 17 EU AI Act — Sistema de gestión de la calidad. "
            "Los proveedores establecerán un sistema de gestión de la calidad que incluirá: "
            "a) estrategia de cumplimiento normativo; b) técnicas y procedimientos para el diseño, "
            "control y verificación del sistema; c) procedimientos de examen, ensayo y validación; "
            "d) canales para notificación de incidentes graves; e) sistema de gestión de registros "
            "con la documentación técnica y los logs requeridos."
        ),
    },
    "eu25_cadena_valor": {
        "source": "eu_ai_act",
        "text": (
            "Artículo 25 EU AI Act — Responsabilidades a lo largo de la cadena de valor de IA. "
            "Cualquier distribuidor, importador, desplegador u otro tercero asumirá las obligaciones "
            "del proveedor cuando: a) comercialice o ponga en servicio el sistema con su nombre o marca; "
            "b) modifique de forma significativa el sistema de IA de alto riesgo; "
            "c) modifique la finalidad prevista de un sistema no clasificado como de alto riesgo "
            "hasta convertirlo en uno de alto riesgo."
        ),
    },
    "eu26_desplegadores": {
        "source": "eu_ai_act",
        "text": (
            "Artículo 26 EU AI Act — Obligaciones de los desplegadores de sistemas de IA de alto riesgo. "
            "Los desplegadores adoptarán medidas técnicas y organizativas para utilizar el sistema "
            "conforme a las instrucciones de uso. Asignarán la supervisión humana a personas competentes "
            "y con la autoridad necesaria. Informarán a los empleados afectados antes del despliegue. "
            "Los desplegadores del sector público notificarán a la autoridad de vigilancia del mercado "
            "cuando hayan utilizado el sistema y lo registrarán en la base de datos de la UE."
        ),
    },

    # ---- EU AI ACT — Evaluación de conformidad ----
    "eu43_conformidad": {
        "source": "eu_ai_act",
        "text": (
            "Artículo 43 EU AI Act — Evaluación de conformidad. "
            "Para sistemas de IA de alto riesgo del Anexo III, la evaluación de conformidad se realizará "
            "como control interno (Anexo VI), salvo sistemas de identificación biométrica o categorización "
            "biométrica, que requerirán participación de un organismo notificado (Anexo VII). "
            "Los sistemas que superen la evaluación llevarán el marcado CE. El procedimiento de evaluación "
            "deberá repetirse cuando el sistema sufra una modificación sustancial."
        ),
    },
    "eu47_declaracion": {
        "source": "eu_ai_act",
        "text": (
            "Artículo 47 EU AI Act — Declaración UE de conformidad. "
            "El proveedor elaborará una declaración UE de conformidad por escrito para cada sistema "
            "de IA de alto riesgo y la mantendrá durante diez años desde la introducción en el mercado. "
            "Contendrá: nombre y dirección del proveedor, descripción y finalidad del sistema, "
            "afirmación de que cumple el Reglamento y la legislación de armonización aplicable, "
            "lista de normas armonizadas o especificaciones comunes aplicadas."
        ),
    },
    "eu49_registro": {
        "source": "eu_ai_act",
        "text": (
            "Artículo 49 EU AI Act — Registro. "
            "Antes de introducir en el mercado un sistema de IA de alto riesgo del Anexo III, "
            "el proveedor lo registrará en la base de datos de la UE. "
            "Los desplegadores del sector público también registrarán el uso de dichos sistemas. "
            "Los datos registrados son accesibles al público, salvo información confidencial, "
            "e incluyen nombre del proveedor, descripción del sistema, estado de conformidad "
            "y el número de identificación del organismo notificado si ha intervenido."
        ),
    },

    # ---- EU AI ACT — Transparencia riesgo limitado ----
    "eu50_transparencia_limitado": {
        "source": "eu_ai_act",
        "text": (
            "Artículo 50 EU AI Act — Obligaciones de transparencia para determinados sistemas de IA. "
            "Los proveedores garantizarán que los sistemas de IA que interactúen directamente con personas "
            "informen a estas de que están interactuando con una IA, salvo que sea evidente por el contexto. "
            "Los proveedores y desplegadores de sistemas que generen contenidos sintéticos (audio, imagen, "
            "vídeo, texto) adoptarán medidas técnicas para marcar dichos contenidos como generados por IA, "
            "garantizando la detección mediante técnicas de marca de agua."
        ),
    },

    # ---- EU AI ACT — Modelos de IA de uso general (GPAI) ----
    "eu51_gpai_riesgo_sistemico": {
        "source": "eu_ai_act",
        "text": (
            "Artículo 51 EU AI Act — Clasificación de modelos GPAI con riesgo sistémico. "
            "Un modelo de IA de uso general (GPAI) se clasificará con riesgo sistémico si tiene "
            "capacidades de alto impacto, incluyendo cuando la computación utilizada para su entrenamiento "
            "supera 10^25 operaciones de punto flotante (FLOPs). "
            "La Comisión podrá también designar modelos con riesgo sistémico que no alcancen ese umbral "
            "pero presenten capacidades o impacto equivalente."
        ),
    },
    "eu53_obligaciones_gpai": {
        "source": "eu_ai_act",
        "text": (
            "Artículo 53 EU AI Act — Obligaciones para los proveedores de modelos GPAI. "
            "Los proveedores de modelos GPAI: a) elaborarán y mantendrán documentación técnica del modelo; "
            "b) publicarán información para que los proveedores aguas abajo puedan cumplir sus obligaciones; "
            "c) establecerán una política de cumplimiento con legislación de derechos de autor; "
            "d) publicarán un resumen del contenido utilizado para el entrenamiento; "
            "e) registrarán el modelo en la base de datos de la UE."
        ),
    },
    "eu55_gpai_obligaciones_sistemico": {
        "source": "eu_ai_act",
        "text": (
            "Artículo 55 EU AI Act — Obligaciones adicionales para modelos GPAI con riesgo sistémico. "
            "Los proveedores de modelos GPAI con riesgo sistémico también deberán: "
            "a) realizar una evaluación del modelo conforme a protocolos estandarizados; "
            "b) evaluar y mitigar posibles riesgos sistémicos; "
            "c) notificar a la Comisión los incidentes graves y posibles medidas correctoras; "
            "d) garantizar la protección cibernética del modelo y sus infraestructuras."
        ),
    },

    # ---- EU AI ACT — Sanciones ----
    "eu99_sanciones_prohibiciones": {
        "source": "eu_ai_act",
        "text": (
            "Artículo 99.3 EU AI Act — Multas por incumplimiento de prohibiciones (Art. 5). "
            "El incumplimiento de la prohibición de las prácticas de IA del artículo 5 estará sujeto "
            "a multas de hasta 35.000.000 EUR o, si el infractor es una empresa, del 7 % de su "
            "volumen de negocio mundial total anual del ejercicio anterior, si esta cuantía es superior."
        ),
    },
    "eu99_sanciones_requisitos": {
        "source": "eu_ai_act",
        "text": (
            "Artículo 99.4 EU AI Act — Multas por incumplimiento de otros requisitos. "
            "El incumplimiento de cualquier otro requisito u obligación del Reglamento distinto del Art. 5 "
            "estará sujeto a multas de hasta 15.000.000 EUR o, si el infractor es una empresa, del 3 % "
            "de su volumen de negocio mundial total anual del ejercicio anterior. "
            "Para las PYME y empresas emergentes los límites máximos se reducen a la mitad."
        ),
    },
    "eu99_criterios": {
        "source": "eu_ai_act",
        "text": (
            "Artículo 99.6 EU AI Act — Criterios para la graduación de las sanciones. "
            "Al determinar el importe de la multa se considerarán: a) la naturaleza, gravedad y duración "
            "de la infracción; b) si el infractor ha actuado intencionalmente o por negligencia; "
            "c) las medidas adoptadas para mitigar los daños; d) el grado de responsabilidad; "
            "e) el historial previo de infracciones; f) el tamaño del infractor, especialmente si es PYME."
        ),
    },
    "eu101_multas_gpai": {
        "source": "eu_ai_act",
        "text": (
            "Artículo 101 EU AI Act — Multas a los proveedores de modelos GPAI. "
            "La Comisión podrá imponer multas a proveedores de modelos GPAI que incumplan "
            "deliberada o negligentemente el Reglamento. Las multas no excederán del 3 % del "
            "volumen de negocio mundial total anual del ejercicio anterior o 15.000.000 EUR, "
            "la cantidad que sea superior."
        ),
    },

    # ---- EU AI ACT — Plazos ----
    "eu113_plazos": {
        "source": "eu_ai_act",
        "text": (
            "Artículo 113 EU AI Act — Entrada en vigor y aplicación. "
            "El Reglamento es aplicable a partir del 2 de agosto de 2026. "
            "No obstante: las prohibiciones del artículo 5 aplican desde el 2 de febrero de 2025; "
            "las disposiciones sobre modelos GPAI aplican desde el 2 de agosto de 2025; "
            "los requisitos para sistemas de IA de alto riesgo del Anexo I (productos seguros) "
            "aplican desde el 2 de agosto de 2027."
        ),
    },

    # ---- EU AI ACT — Vigilancia poscomercialización e incidentes ----
    "eu72_vigilancia": {
        "source": "eu_ai_act",
        "text": (
            "Artículo 72 EU AI Act — Vigilancia poscomercialización. "
            "Los proveedores de sistemas de IA de alto riesgo establecerán un sistema de vigilancia "
            "poscomercialización proporcional a la naturaleza del sistema y sus riesgos. "
            "El sistema recabará, documentará y analizará datos durante todo el ciclo de vida del sistema "
            "para detectar incidentes o deficiencias de funcionamiento y adoptar las medidas correctoras "
            "necesarias de forma oportuna."
        ),
    },
    "eu73_incidentes": {
        "source": "eu_ai_act",
        "text": (
            "Artículo 73 EU AI Act — Notificación de incidentes graves. "
            "Los proveedores notificarán a las autoridades de vigilancia del mercado cualquier incidente "
            "grave. La notificación se realizará sin demora injustificada y, como máximo, en 15 días "
            "desde que el proveedor tenga conocimiento del incidente, o en 24 horas si existe riesgo "
            "grave e inminente para la salud, la seguridad o los derechos fundamentales. "
            "Los proveedores adoptarán las medidas correctoras necesarias."
        ),
    },

    # ---- EU AI ACT — Sandbox ----
    "eu57_sandbox": {
        "source": "eu_ai_act",
        "text": (
            "Artículo 57 EU AI Act — Entornos de prueba de reglamentación de IA (sandboxes). "
            "Las autoridades nacionales competentes establecerán al menos un sandbox regulatorio de IA "
            "a nivel nacional, operativo antes del 2 de agosto de 2026. "
            "El sandbox permite desarrollar, entrenar, poner a prueba y validar sistemas de IA innovadores "
            "durante un tiempo limitado bajo supervisión regulatoria, sobre la base de un plan acordado "
            "con la autoridad competente."
        ),
    },
    "eu58_sandbox_pymes": {
        "source": "eu_ai_act",
        "text": (
            "Artículo 58 EU AI Act — Participación en los sandboxes regulatorios. "
            "Las autoridades garantizarán la participación prioritaria de PYME, empresas emergentes "
            "y personas físicas. El sandbox estará disponible de forma abierta y transparente. "
            "La participación no exime del cumplimiento del Reglamento, pero las autoridades "
            "podrán adaptar el ritmo y el modo de aplicación a las circunstancias del participante. "
            "La duración máxima del sandbox es de 24 meses, prorrogables por 12 meses adicionales."
        ),
    },

    # ---- EU AI ACT — Gobernanza ----
    "eu65_euai_board": {
        "source": "eu_ai_act",
        "text": (
            "Artículo 65 EU AI Act — Comité Europeo de Inteligencia Artificial (EUAI Board). "
            "Se crea el EUAI Board, compuesto por representantes de las autoridades nacionales de "
            "supervisión de IA de cada Estado miembro. El Comité asesorará y asistirá a la Comisión "
            "en la aplicación coherente del Reglamento, emitirá directrices y recomendaciones, "
            "coordinará actividades de supervisión y participará en la evaluación de modelos GPAI "
            "con riesgo sistémico."
        ),
    },

    # ---- AESIA ----
    "aesia_funciones": {
        "source": "aesia",
        "text": (
            "Real Decreto 729/2023 — Agencia Española de Supervisión de la Inteligencia Artificial (AESIA). "
            "La AESIA es el organismo público encargado de supervisar el cumplimiento de la normativa "
            "de IA en España y actuar como autoridad nacional de vigilancia del mercado en el marco "
            "del EU AI Act. Sus funciones incluyen: supervisión e inspección de sistemas de IA, "
            "imposición de sanciones, elaboración de guías y estándares, gestión del sandbox "
            "regulatorio nacional y coordinación con el EUAI Board y la Comisión Europea."
        ),
    },
    "aesia_competencias": {
        "source": "aesia",
        "text": (
            "AESIA — Competencias de supervisión e inspección. "
            "La AESIA tiene competencia para: a) exigir documentación técnica a proveedores y desplegadores; "
            "b) llevar a cabo inspecciones y auditorías técnicas; c) imponer medidas cautelares cuando "
            "un sistema presente riesgo grave e inminente; d) colaborar con la AEPD cuando los sistemas "
            "traten datos personales; e) actuar como punto único de contacto para el EUAI Board."
        ),
    },
    "aesia_poscomercializacion": {
        "source": "aesia",
        "text": (
            "AESIA — Guía de vigilancia poscomercialización. "
            "La AESIA ha publicado orientaciones para implementar el sistema de vigilancia "
            "poscomercialización exigido por el EU AI Act. Recomienda: establecer canales de reporte "
            "para usuarios, definir indicadores clave de rendimiento, realizar revisiones periódicas "
            "de los logs generados, y documentar las acciones correctoras adoptadas ante desviaciones. "
            "También orienta sobre cuándo debe notificarse un incidente a la AESIA."
        ),
    },
    "aesia_sandbox": {
        "source": "aesia",
        "text": (
            "AESIA — Sandbox Regulatorio de IA. "
            "La AESIA gestiona el sandbox regulatorio nacional previsto en el EU AI Act, "
            "que permite a empresas —con prioridad para startups y PYME— desarrollar y validar "
            "sistemas de IA innovadores bajo supervisión regulatoria durante un período limitado "
            "(hasta 24 meses + 12 de prórroga). "
            "Los participantes obtienen orientación personalizada sobre el cumplimiento del Reglamento. "
            "La participación en el sandbox no exime del cumplimiento normativo."
        ),
    },
    "aesia_incidentes": {
        "source": "aesia",
        "text": (
            "AESIA — Protocolo de notificación de incidentes graves. "
            "La AESIA actúa como autoridad receptora de las notificaciones de incidentes graves "
            "que deben presentar los proveedores de sistemas de IA de alto riesgo. "
            "Tras recibir la notificación, puede: solicitar información adicional, ordenar la "
            "suspensión cautelar del sistema, coordinar con la AEPD si hay datos personales implicados, "
            "y publicar alertas de seguridad si existe riesgo para otros usuarios del mercado."
        ),
    },

    # ---- RGPD / LOPDGDD ----
    "rgpd6_bases_legales": {
        "source": "lopd_rgpd",
        "text": (
            "Artículo 6 RGPD — Licitud del tratamiento. "
            "El tratamiento de datos personales solo será lícito si se cumple al menos una condición: "
            "a) el interesado dio su consentimiento; b) es necesario para ejecutar un contrato; "
            "c) es necesario para el cumplimiento de una obligación legal del responsable; "
            "d) es necesario para proteger intereses vitales del interesado; "
            "e) es necesario para el cumplimiento de una misión de interés público o ejercicio de poderes públicos."
        ),
    },
    "rgpd9_datos_sensibles": {
        "source": "lopd_rgpd",
        "text": (
            "Artículo 9 RGPD — Tratamiento de categorías especiales de datos personales. "
            "Quedan prohibidos el tratamiento de datos que revelen origen étnico o racial, "
            "opiniones políticas, convicciones religiosas, afiliación sindical, datos genéticos, "
            "datos biométricos para identificar unívocamente a una persona, datos de salud, "
            "vida sexual u orientación sexual. "
            "La prohibición no se aplica cuando el interesado da su consentimiento explícito "
            "o concurre alguna de las excepciones del apartado 2."
        ),
    },
    "rgpd22_decisiones_auto": {
        "source": "lopd_rgpd",
        "text": (
            "Artículo 22 RGPD — Decisiones individuales automatizadas, incluida la elaboración de perfiles. "
            "El interesado tendrá derecho a no ser objeto de decisiones basadas únicamente en tratamiento "
            "automatizado que produzcan efectos jurídicos o le afecten significativamente. "
            "El responsable deberá aplicar medidas adecuadas para salvaguardar los derechos del interesado, "
            "incluyendo el derecho a obtener intervención humana, expresar su punto de vista e impugnar la decisión."
        ),
    },
    "rgpd25_privacidad_diseno": {
        "source": "lopd_rgpd",
        "text": (
            "Artículo 25 RGPD — Protección de datos desde el diseño y por defecto. "
            "Teniendo en cuenta el estado de la técnica, el responsable aplicará medidas técnicas y "
            "organizativas apropiadas tanto en el momento de determinar los medios de tratamiento "
            "como en el momento del propio tratamiento, con el fin de aplicar de forma efectiva "
            "los principios de protección de datos e integrar las garantías necesarias."
        ),
    },
    "rgpd35_dpia": {
        "source": "lopd_rgpd",
        "text": (
            "Artículo 35 RGPD — Evaluación de impacto relativa a la protección de datos (DPIA). "
            "Cuando sea probable que un tipo de tratamiento entrañe un alto riesgo para los derechos "
            "y libertades de las personas, el responsable realizará una evaluación de impacto antes "
            "del tratamiento. Será obligatoria en especial para: a) evaluación sistemática de aspectos "
            "personales mediante tratamiento automatizado o elaboración de perfiles; b) tratamiento a gran "
            "escala de datos sensibles del artículo 9; c) vigilancia sistemática a gran escala."
        ),
    },
    "rgpd13_info": {
        "source": "lopd_rgpd",
        "text": (
            "Artículo 13 RGPD — Información que facilitará el responsable al recoger datos del interesado. "
            "El responsable facilitará: identidad y contacto del responsable y del DPO, finalidades y base "
            "jurídica del tratamiento, destinatarios, intención de transferencias internacionales, "
            "plazo de conservación, derechos de acceso, rectificación, supresión, limitación, portabilidad "
            "y oposición, y derecho a reclamación ante la autoridad de control (AEPD en España)."
        ),
    },
    "rgpd83_multas": {
        "source": "lopd_rgpd",
        "text": (
            "Artículo 83 RGPD — Condiciones generales para la imposición de multas administrativas. "
            "Las infracciones de los principios básicos del tratamiento y los derechos de los interesados "
            "se sancionarán con multas de hasta 20.000.000 EUR o el 4 % del volumen de negocio anual global. "
            "Otras infracciones (obligaciones del responsable, del encargado, organismos de certificación) "
            "se sancionarán con multas de hasta 10.000.000 EUR o el 2 % del volumen de negocio."
        ),
    },
    "lopdgdd_delegado": {
        "source": "lopd_rgpd",
        "text": (
            "Artículo 34 LOPDGDD — Designación del delegado de protección de datos. "
            "El delegado de protección de datos debe designarse cuando el tratamiento lo realice "
            "una autoridad u organismo público, cuando las actividades principales consistan en "
            "observación habitual y sistemática de interesados a gran escala, o cuando se traten "
            "a gran escala categorías especiales de datos del artículo 9 RGPD."
        ),
    },

    # ---- Documentos NO RELEVANTES (hard negatives del dominio legal) ----
    "rgpd_derechos_acceso": {
        "source": "lopd_rgpd",
        "text": (
            "Artículos 15–21 RGPD — Derechos de los interesados. "
            "El interesado tendrá derecho de acceso a sus datos, derecho de rectificación de datos inexactos, "
            "derecho de supresión ('derecho al olvido'), derecho a la limitación del tratamiento, "
            "derecho a la portabilidad y derecho de oposición al tratamiento. "
            "El responsable responderá a las solicitudes en el plazo de un mes, ampliable a tres en casos complejos."
        ),
    },

    # ---- Documentos fuera de dominio (easy negatives) ----
    "irpf_residencia": {
        "source": "other",
        "text": (
            "Artículo 9 Ley 35/2006 del IRPF — Residencia habitual en territorio español. "
            "Se entenderá que el contribuyente tiene su residencia habitual en territorio español cuando "
            "permanezca más de 183 días durante el año natural en territorio español, o radique en España "
            "el núcleo principal o la base de sus actividades o intereses económicos."
        ),
    },
    "et_despido": {
        "source": "other",
        "text": (
            "Artículo 52 Estatuto de los Trabajadores — Extinción del contrato por causas objetivas. "
            "El contrato podrá extinguirse por ineptitud del trabajador conocida o sobrevenida con "
            "posterioridad a su colocación efectiva en la empresa, por falta de adaptación del trabajador "
            "a las modificaciones técnicas razonables operadas en su puesto de trabajo, o por causas "
            "económicas, técnicas, organizativas o de producción."
        ),
    },
    "covid_alarma": {
        "source": "other",
        "text": (
            "Real Decreto 463/2020, de 14 de marzo — Estado de alarma por COVID-19. "
            "Se declara el estado de alarma para la gestión de la situación de crisis sanitaria. "
            "Durante su vigencia, las personas únicamente podrán circular por las vías de uso público "
            "para la realización de actividades esenciales como adquisición de alimentos, asistencia "
            "a centros sanitarios o acudir al lugar de trabajo."
        ),
    },
    "subvenciones_digitalizacion": {
        "source": "other",
        "text": (
            "Resolución de 12 de marzo de 2024, Secretaría de Estado de Digitalización. "
            "Convocatoria de subvenciones para proyectos de transformación digital en pymes del sector industrial. "
            "Se convocan subvenciones en régimen de concurrencia competitiva con un presupuesto total "
            "de 50 millones de euros para financiar proyectos de digitalización de procesos productivos."
        ),
    },
    "nis2_ciberseguridad": {
        "source": "other",
        "text": (
            "Directiva NIS2 (2022/2555) — Medidas de seguridad para entidades esenciales e importantes. "
            "Las entidades aplicarán medidas técnicas, operativas y organizativas apropiadas y proporcionadas "
            "para gestionar los riesgos para la seguridad de sus redes y sistemas de información. "
            "Incluirá: gestión de riesgos, continuidad del negocio, seguridad de la cadena de suministro "
            "y notificación de incidentes a la autoridad competente en un plazo de 24 horas."
        ),
    },
    "dora_resiliencia": {
        "source": "other",
        "text": (
            "Reglamento DORA (2022/2554) — Resiliencia operativa digital del sector financiero. "
            "Las entidades financieras establecerán un marco de gestión del riesgo de las TIC que les permita "
            "afrontar ese riesgo de forma rápida y eficiente. El marco incluirá: identificación de activos TIC, "
            "planes de respuesta ante incidentes, pruebas periódicas de resiliencia y notificación "
            "de incidentes TIC graves a las autoridades supervisoras."
        ),
    },
    "lssi_comercio": {
        "source": "other",
        "text": (
            "Ley 34/2002 de Servicios de la Sociedad de la Información y Comercio Electrónico (LSSI-CE). "
            "Los prestadores de servicios de la sociedad de la información deben cumplir con obligaciones "
            "de información general: denominación social, domicilio, datos de inscripción registral, "
            "NIF, datos de contacto para comunicaciones, incluyendo dirección de correo electrónico."
        ),
    },
    "codigo_civil_contratos": {
        "source": "other",
        "text": (
            "Artículo 1258 del Código Civil — Contratos. "
            "Los contratos se perfeccionan por el mero consentimiento, y desde entonces obligan "
            "no sólo al cumplimiento de lo expresamente pactado, sino también a todas las consecuencias "
            "que, según su naturaleza, sean conformes a la buena fe, al uso y a la ley."
        ),
    },
    "ley_competencia": {
        "source": "other",
        "text": (
            "Artículo 1 Ley 15/2007, de Defensa de la Competencia — Conductas colusorias. "
            "Se prohíbe todo acuerdo, decisión o recomendación colectiva, o práctica concertada, "
            "que tenga por objeto, produzca o pueda producir el efecto de impedir, restringir "
            "o falsear la competencia en todo o parte del mercado nacional."
        ),
    },
}

# ============================================================
# 2. DEFINICIÓN DE QUERIES Y SUS PARES DOCUMENTALES
# ============================================================
# Cada entrada: (query, [claves relevantes], [claves no relevantes])
# Regla de etiquetado: "relevante" = el documento CONTRIBUYE información
# útil para responder la query, aunque sea parcialmente.

QUERY_PAIRS: list[tuple[str, list[str], list[str]]] = [

    # ================================================================
    # BLOQUE 1: QUERIES ORIGINALES de rag_complex_queries_results.json
    # ================================================================

    (
        "Resume requisitos de un sistema de IA de alto riesgo y relaciónalos con "
        "obligaciones de documentación, supervisión humana y gestión de riesgos.",
        ["eu9_gestion_riesgos", "eu11_doc_tecnica", "eu14_supervision_humana", "eu16_obligaciones_prov"],
        ["rgpd83_multas", "irpf_residencia", "covid_alarma"],
    ),
    (
        "Si un sistema de IA procesa datos personales, ¿qué base legal y medidas pide "
        "RGPD/LOPDGDD y qué exige el Reglamento de IA sobre supervisión?",
        ["rgpd6_bases_legales", "rgpd25_privacidad_diseno", "eu14_supervision_humana", "rgpd35_dpia"],
        ["eu99_sanciones_prohibiciones", "irpf_residencia", "et_despido"],
    ),
    (
        "Ante un incidente grave en un sistema de IA de alto riesgo, ¿qué obligaciones "
        "de notificación y medidas correctoras aplican (Reglamento IA + marco español si existe)?",
        ["eu73_incidentes", "eu72_vigilancia", "aesia_incidentes", "eu17_sgc"],
        ["rgpd_derechos_acceso", "subvenciones_digitalizacion", "dora_resiliencia"],
    ),
    (
        "¿Qué es la evaluación de conformidad y el marcado CE en sistemas de IA de alto riesgo "
        "y qué evidencias/documentación deben guardarse?",
        ["eu43_conformidad", "eu47_declaracion", "eu11_doc_tecnica", "eu17_sgc"],
        ["rgpd6_bases_legales", "et_despido", "ley_competencia"],
    ),
    (
        "Diferencia obligaciones del proveedor y del desplegador (deployer) en IA de alto riesgo "
        "y cómo afecta si hay tratamiento de datos personales.",
        ["eu16_obligaciones_prov", "eu26_desplegadores", "eu25_cadena_valor", "rgpd6_bases_legales"],
        ["eu99_sanciones_prohibiciones", "covid_alarma", "irpf_residencia"],
    ),
    (
        "¿Qué dice el Reglamento de IA sobre registro/logs y trazabilidad y cómo encaja "
        "con principios de protección de datos?",
        ["eu12_logs", "eu13_transparencia_desplegador", "rgpd25_privacidad_diseno", "eu72_vigilancia"],
        ["eu99_sanciones_prohibiciones", "lssi_comercio", "subvenciones_digitalizacion"],
    ),
    (
        "¿Qué requisitos hay sobre gobernanza de datos y calidad del dataset para IA de alto riesgo "
        "y qué riesgos legales cubre esto?",
        ["eu10_datos", "eu9_gestion_riesgos", "rgpd25_privacidad_diseno", "rgpd9_datos_sensibles"],
        ["irpf_residencia", "et_despido", "covid_alarma"],
    ),
    (
        "¿Qué establece AESIA (o guía española) sobre evaluación, supervisión o vigilancia "
        "poscomercialización de sistemas de IA?",
        ["aesia_poscomercializacion", "aesia_competencias", "eu72_vigilancia", "aesia_funciones"],
        ["rgpd_derechos_acceso", "irpf_residencia", "ley_competencia"],
    ),
    (
        "Obligaciones de transparencia: qué informar al usuario final y qué pasa si "
        "el sistema usa datos personales.",
        ["eu13_transparencia_desplegador", "eu50_transparencia_limitado", "rgpd13_info", "rgpd22_decisiones_auto"],
        ["eu99_sanciones_prohibiciones", "et_despido", "codigo_civil_contratos"],
    ),
    (
        "Riesgos y sanciones: enumera qué podría pasar por incumplir Reglamento IA y RGPD "
        "en un caso de IA de alto riesgo.",
        ["eu99_sanciones_prohibiciones", "eu99_sanciones_requisitos", "rgpd83_multas", "eu99_criterios"],
        ["covid_alarma", "subvenciones_digitalizacion", "ley_competencia"],
    ),

    # ================================================================
    # BLOQUE 2: 100 QUERIES ADICIONALES
    # ================================================================

    # -- Prohibiciones (Art. 5) --
    (
        "¿Está prohibido un sistema de IA que detecta el estado emocional de trabajadores "
        "en su puesto de trabajo?",
        ["eu5_subliminal", "eu5_vulnerabilidades", "eu_anex3_rrhh"],
        ["rgpd6_bases_legales", "subvenciones_digitalizacion", "et_despido"],
    ),
    (
        "¿Puede un gobierno usar IA para asignar puntuaciones de confianza social a ciudadanos "
        "y restringirles el acceso a servicios públicos?",
        ["eu5_scoring_social", "eu5_subliminal"],
        ["rgpd22_decisiones_auto", "irpf_residencia", "covid_alarma"],
    ),
    (
        "¿Bajo qué condiciones puede la policía usar identificación biométrica facial en tiempo real "
        "en lugares públicos?",
        ["eu5_biomet_remota", "eu5_categorizacion_biomet"],
        ["eu43_conformidad", "irpf_residencia", "lssi_comercio"],
    ),
    (
        "¿Es legal un sistema de IA que dirige publicidad específica a personas con adicciones "
        "para explotar su vulnerabilidad?",
        ["eu5_vulnerabilidades", "eu5_subliminal"],
        ["rgpd6_bases_legales", "subvenciones_digitalizacion", "et_despido"],
    ),
    (
        "¿Puede un sistema de IA predecir si una persona va a cometer un delito y usarlo "
        "para priorizar vigilancia policial?",
        ["eu5_prediccion_riesgo", "eu5_scoring_social"],
        ["eu9_gestion_riesgos", "irpf_residencia", "lssi_comercio"],
    ),
    (
        "¿Están prohibidos los sistemas que categorizan a personas por su orientación sexual "
        "a partir de datos biométricos?",
        ["eu5_categorizacion_biomet", "rgpd9_datos_sensibles"],
        ["eu43_conformidad", "irpf_residencia", "ley_competencia"],
    ),

    # -- Clasificación de alto riesgo (Art. 6 + Anexo III) --
    (
        "¿Qué criterios usa el EU AI Act para clasificar un sistema de IA como de alto riesgo?",
        ["eu6_clasificacion", "eu_anex3_infraestructura"],
        ["eu99_sanciones_prohibiciones", "irpf_residencia", "covid_alarma"],
    ),
    (
        "¿Es de alto riesgo un sistema de IA que filtra automáticamente currículums en un proceso "
        "de selección de personal?",
        ["eu_anex3_rrhh", "eu6_clasificacion"],
        ["rgpd6_bases_legales", "et_despido", "lssi_comercio"],
    ),
    (
        "¿Qué sistemas de IA usados en el ámbito educativo son de alto riesgo según el EU AI Act?",
        ["eu_anex3_educacion", "eu6_clasificacion"],
        ["eu99_sanciones_prohibiciones", "irpf_residencia", "subvenciones_digitalizacion"],
    ),
    (
        "¿Un sistema de IA que concede o deniega préstamos bancarios es de alto riesgo?",
        ["eu_anex3_credito", "eu6_clasificacion"],
        ["rgpd6_bases_legales", "covid_alarma", "codigo_civil_contratos"],
    ),
    (
        "¿Qué sistemas de IA en infraestructuras críticas entran en la categoría de alto riesgo?",
        ["eu_anex3_infraestructura", "eu6_clasificacion"],
        ["eu99_sanciones_prohibiciones", "irpf_residencia", "ley_competencia"],
    ),
    (
        "¿Los sistemas de apoyo al diagnóstico médico por IA son de alto riesgo?",
        ["eu_anex3_sanidad", "eu6_clasificacion"],
        ["rgpd13_info", "irpf_residencia", "dora_resiliencia"],
    ),
    (
        "¿Es de alto riesgo un sistema de IA que asiste a jueces en la valoración de pruebas?",
        ["eu_anex3_judicial", "eu6_clasificacion"],
        ["eu9_gestion_riesgos", "irpf_residencia", "codigo_civil_contratos"],
    ),
    (
        "¿Los sistemas de IA para evaluación de solicitantes de asilo son de alto riesgo?",
        ["eu_anex3_migracion", "eu6_clasificacion"],
        ["rgpd6_bases_legales", "covid_alarma", "ley_competencia"],
    ),

    # -- Requisitos técnicos (Art. 9–15) --
    (
        "¿Qué debe incluir el sistema de gestión de riesgos de un sistema de IA de alto riesgo?",
        ["eu9_gestion_riesgos", "eu16_obligaciones_prov"],
        ["eu99_sanciones_prohibiciones", "irpf_residencia", "lssi_comercio"],
    ),
    (
        "¿Qué requisitos de calidad y gobernanza deben cumplir los datos de entrenamiento de IA?",
        ["eu10_datos", "eu9_gestion_riesgos"],
        ["rgpd_derechos_acceso", "subvenciones_digitalizacion", "et_despido"],
    ),
    (
        "¿Qué información mínima debe contener la documentación técnica de un sistema de IA de alto riesgo?",
        ["eu11_doc_tecnica", "eu16_obligaciones_prov"],
        ["rgpd13_info", "covid_alarma", "ley_competencia"],
    ),
    (
        "¿Cuánto tiempo deben conservarse los logs de un sistema de IA de alto riesgo?",
        ["eu12_logs", "eu16_obligaciones_prov"],
        ["rgpd6_bases_legales", "irpf_residencia", "lssi_comercio"],
    ),
    (
        "¿Qué información deben recibir los desplegadores de sistemas de IA de alto riesgo?",
        ["eu13_transparencia_desplegador", "eu26_desplegadores"],
        ["eu99_sanciones_prohibiciones", "et_despido", "subvenciones_digitalizacion"],
    ),
    (
        "¿Qué mecanismos de supervisión humana son obligatorios en sistemas de IA de alto riesgo?",
        ["eu14_supervision_humana", "eu13_transparencia_desplegador"],
        ["rgpd22_decisiones_auto", "irpf_residencia", "covid_alarma"],
    ),
    (
        "¿Qué nivel de exactitud y robustez debe garantizar un proveedor de IA de alto riesgo?",
        ["eu15_exactitud", "eu9_gestion_riesgos"],
        ["eu99_sanciones_prohibiciones", "lssi_comercio", "dora_resiliencia"],
    ),
    (
        "¿Cómo debe gestionarse el sesgo algorítmico en sistemas de IA de alto riesgo?",
        ["eu10_datos", "eu9_gestion_riesgos", "eu15_exactitud"],
        ["rgpd6_bases_legales", "subvenciones_digitalizacion", "et_despido"],
    ),
    (
        "¿El EU AI Act exige que los sistemas de IA sean resistentes a ataques adversariales?",
        ["eu15_exactitud", "eu9_gestion_riesgos"],
        ["nis2_ciberseguridad", "irpf_residencia", "lssi_comercio"],
    ),

    # -- Obligaciones proveedores y desplegadores --
    (
        "¿Qué obligaciones tiene un proveedor de IA de alto riesgo establecido fuera de la UE?",
        ["eu16_obligaciones_prov", "eu25_cadena_valor"],
        ["eu99_sanciones_prohibiciones", "irpf_residencia", "codigo_civil_contratos"],
    ),
    (
        "¿Puede un proveedor de IA delegar responsabilidades en un distribuidor o representante?",
        ["eu25_cadena_valor", "eu16_obligaciones_prov"],
        ["rgpd6_bases_legales", "et_despido", "lssi_comercio"],
    ),
    (
        "¿Qué obligaciones específicas tiene el desplegador de un sistema de IA de alto riesgo?",
        ["eu26_desplegadores", "eu13_transparencia_desplegador"],
        ["eu9_gestion_riesgos", "irpf_residencia", "subvenciones_digitalizacion"],
    ),
    (
        "¿Cuándo se convierte un distribuidor en proveedor según el EU AI Act?",
        ["eu25_cadena_valor", "eu16_obligaciones_prov"],
        ["eu99_sanciones_prohibiciones", "covid_alarma", "ley_competencia"],
    ),
    (
        "¿Qué sistema de gestión de la calidad debe implementar un proveedor de IA de alto riesgo?",
        ["eu17_sgc", "eu16_obligaciones_prov"],
        ["rgpd25_privacidad_diseno", "irpf_residencia", "dora_resiliencia"],
    ),
    (
        "¿Qué información debe incluir el 'README' o instrucciones de uso de un sistema de IA?",
        ["eu13_transparencia_desplegador", "eu16_obligaciones_prov"],
        ["rgpd13_info", "subvenciones_digitalizacion", "et_despido"],
    ),

    # -- Evaluación de conformidad --
    (
        "¿Cuándo es obligatorio recurrir a un organismo notificado para evaluar conformidad de IA?",
        ["eu43_conformidad", "eu6_clasificacion"],
        ["eu99_sanciones_prohibiciones", "irpf_residencia", "codigo_civil_contratos"],
    ),
    (
        "¿Qué debe incluir la declaración UE de conformidad de un sistema de IA de alto riesgo?",
        ["eu47_declaracion", "eu43_conformidad"],
        ["rgpd13_info", "covid_alarma", "ley_competencia"],
    ),
    (
        "¿Qué información debe registrarse en la base de datos de la UE para sistemas de IA?",
        ["eu49_registro", "eu47_declaracion"],
        ["eu9_gestion_riesgos", "irpf_residencia", "lssi_comercio"],
    ),
    (
        "¿Qué pasa con la conformidad de un sistema de IA cuando sufre una modificación sustancial?",
        ["eu43_conformidad", "eu25_cadena_valor"],
        ["rgpd25_privacidad_diseno", "subvenciones_digitalizacion", "et_despido"],
    ),
    (
        "¿Qué son las normas armonizadas en el contexto del EU AI Act y qué ventajas ofrecen?",
        ["eu43_conformidad", "eu47_declaracion"],
        ["rgpd83_multas", "covid_alarma", "ley_competencia"],
    ),

    # -- Transparencia chatbots / riesgo limitado --
    (
        "¿Qué obligaciones de transparencia tienen los chatbots y asistentes virtuales?",
        ["eu50_transparencia_limitado", "eu13_transparencia_desplegador"],
        ["eu99_sanciones_prohibiciones", "irpf_residencia", "dora_resiliencia"],
    ),
    (
        "¿Qué es el deepfake y qué obliga el EU AI Act sobre contenidos generados por IA?",
        ["eu50_transparencia_limitado"],
        ["eu5_subliminal", "irpf_residencia", "lssi_comercio"],
    ),
    (
        "¿Deben los usuarios ser informados cuando interactúan con un sistema de IA?",
        ["eu50_transparencia_limitado", "eu13_transparencia_desplegador", "rgpd13_info"],
        ["eu99_sanciones_prohibiciones", "covid_alarma", "subvenciones_digitalizacion"],
    ),

    # -- Modelos GPAI --
    (
        "¿Qué son los modelos de IA de uso general (GPAI) y qué regulación les aplica?",
        ["eu53_obligaciones_gpai", "eu51_gpai_riesgo_sistemico"],
        ["eu6_clasificacion", "irpf_residencia", "codigo_civil_contratos"],
    ),
    (
        "¿Qué obligaciones adicionales tienen los modelos GPAI con riesgo sistémico?",
        ["eu55_gpai_obligaciones_sistemico", "eu51_gpai_riesgo_sistemico"],
        ["eu99_sanciones_prohibiciones", "covid_alarma", "ley_competencia"],
    ),
    (
        "¿Cuándo se considera que un modelo GPAI tiene riesgo sistémico según el EU AI Act?",
        ["eu51_gpai_riesgo_sistemico", "eu55_gpai_obligaciones_sistemico"],
        ["eu6_clasificacion", "irpf_residencia", "lssi_comercio"],
    ),
    (
        "¿Qué transparencia sobre datos de entrenamiento deben publicar los proveedores de GPAI?",
        ["eu53_obligaciones_gpai", "eu10_datos"],
        ["rgpd6_bases_legales", "subvenciones_digitalizacion", "dora_resiliencia"],
    ),
    (
        "¿Qué multas se aplican a los proveedores de modelos de IA de uso general que incumplan?",
        ["eu101_multas_gpai", "eu99_sanciones_requisitos"],
        ["rgpd83_multas", "irpf_residencia", "et_despido"],
    ),

    # -- Sanciones --
    (
        "¿Cuál es la multa máxima por infringir una prohibición del artículo 5 del EU AI Act?",
        ["eu99_sanciones_prohibiciones", "eu99_criterios"],
        ["rgpd83_multas", "irpf_residencia", "codigo_civil_contratos"],
    ),
    (
        "¿Existen reducciones de multa para las PYME en el EU AI Act?",
        ["eu99_criterios", "eu99_sanciones_requisitos"],
        ["rgpd83_multas", "subvenciones_digitalizacion", "et_despido"],
    ),
    (
        "¿Qué factores tiene en cuenta la autoridad para calcular la sanción a un infractor del EU AI Act?",
        ["eu99_criterios", "eu99_sanciones_requisitos"],
        ["rgpd83_multas", "lssi_comercio", "ley_competencia"],
    ),
    (
        "¿Cuánto puede multar el RGPD por incumplimientos relacionados con el tratamiento de datos?",
        ["rgpd83_multas"],
        ["eu99_sanciones_prohibiciones", "irpf_residencia", "covid_alarma"],
    ),
    (
        "Si una empresa incumple a la vez el EU AI Act y el RGPD, ¿qué sanciones se aplican?",
        ["eu99_sanciones_requisitos", "rgpd83_multas", "eu99_criterios"],
        ["ley_competencia", "et_despido", "subvenciones_digitalizacion"],
    ),

    # -- Plazos de aplicación --
    (
        "¿Cuándo empiezan a aplicarse las prohibiciones del EU AI Act?",
        ["eu113_plazos", "eu5_subliminal"],
        ["eu99_sanciones_prohibiciones", "irpf_residencia", "dora_resiliencia"],
    ),
    (
        "¿Cuándo aplica el EU AI Act a los sistemas de IA de alto riesgo del Anexo III?",
        ["eu113_plazos", "eu6_clasificacion"],
        ["eu43_conformidad", "covid_alarma", "lssi_comercio"],
    ),
    (
        "¿En qué fecha entran en vigor las obligaciones sobre modelos GPAI del EU AI Act?",
        ["eu113_plazos", "eu53_obligaciones_gpai"],
        ["eu99_sanciones_prohibiciones", "irpf_residencia", "et_despido"],
    ),

    # -- Gobernanza institucional --
    (
        "¿Qué es el Comité Europeo de Inteligencia Artificial (EUAI Board) y qué funciones tiene?",
        ["eu65_euai_board", "aesia_funciones"],
        ["eu99_sanciones_prohibiciones", "irpf_residencia", "ley_competencia"],
    ),
    (
        "¿Qué son los sandboxes regulatorios de IA y quién puede acceder?",
        ["eu57_sandbox", "eu58_sandbox_pymes", "aesia_sandbox"],
        ["irpf_residencia", "covid_alarma", "codigo_civil_contratos"],
    ),
    (
        "¿Cuánto dura un sandbox regulatorio de IA y se puede prorrogar?",
        ["eu58_sandbox_pymes", "eu57_sandbox", "aesia_sandbox"],
        ["eu99_sanciones_prohibiciones", "subvenciones_digitalizacion", "lssi_comercio"],
    ),
    (
        "¿Las startups tienen acceso prioritario a los sandboxes regulatorios de IA?",
        ["eu58_sandbox_pymes", "aesia_sandbox"],
        ["irpf_residencia", "et_despido", "ley_competencia"],
    ),

    # -- AESIA --
    (
        "¿Qué funciones tiene la AESIA como autoridad de supervisión de IA en España?",
        ["aesia_funciones", "aesia_competencias"],
        ["eu99_sanciones_prohibiciones", "irpf_residencia", "dora_resiliencia"],
    ),
    (
        "¿Puede la AESIA suspender cautelarmente un sistema de IA que suponga un riesgo grave?",
        ["aesia_competencias", "aesia_incidentes"],
        ["rgpd6_bases_legales", "subvenciones_digitalizacion", "ley_competencia"],
    ),
    (
        "¿Qué guías ha publicado la AESIA sobre el cumplimiento del EU AI Act?",
        ["aesia_poscomercializacion", "aesia_funciones"],
        ["eu99_sanciones_prohibiciones", "irpf_residencia", "lssi_comercio"],
    ),
    (
        "¿Qué pasos sigue la AESIA cuando recibe la notificación de un incidente en un sistema de IA?",
        ["aesia_incidentes", "aesia_competencias", "eu73_incidentes"],
        ["rgpd_derechos_acceso", "covid_alarma", "et_despido"],
    ),

    # -- RGPD e IA --
    (
        "¿Qué dice el RGPD sobre el derecho a no ser objeto de decisiones tomadas exclusivamente "
        "por un algoritmo?",
        ["rgpd22_decisiones_auto"],
        ["eu99_sanciones_prohibiciones", "irpf_residencia", "lssi_comercio"],
    ),
    (
        "¿Cuándo es obligatorio realizar una Evaluación de Impacto (DPIA) antes de desplegar un sistema de IA?",
        ["rgpd35_dpia", "rgpd9_datos_sensibles"],
        ["eu9_gestion_riesgos", "covid_alarma", "ley_competencia"],
    ),
    (
        "¿Qué base legal habilita el tratamiento de datos personales para entrenar un modelo de IA?",
        ["rgpd6_bases_legales", "rgpd9_datos_sensibles"],
        ["eu10_datos", "irpf_residencia", "et_despido"],
    ),
    (
        "¿Pueden usarse datos biométricos para entrenar sistemas de IA sin consentimiento explícito?",
        ["rgpd9_datos_sensibles", "eu5_categorizacion_biomet"],
        ["eu6_clasificacion", "subvenciones_digitalizacion", "codigo_civil_contratos"],
    ),
    (
        "¿Qué derechos tiene una persona cuando una decisión automatizada de IA le afecta negativamente?",
        ["rgpd22_decisiones_auto", "rgpd_derechos_acceso"],
        ["eu99_sanciones_prohibiciones", "irpf_residencia", "dora_resiliencia"],
    ),
    (
        "¿Qué información deben recibir los ciudadanos cuando sus datos son usados por un sistema de IA?",
        ["rgpd13_info", "eu50_transparencia_limitado"],
        ["eu99_sanciones_prohibiciones", "et_despido", "lssi_comercio"],
    ),
    (
        "¿Debe un sistema de IA cumplir con el principio de privacidad desde el diseño del RGPD?",
        ["rgpd25_privacidad_diseno", "eu10_datos"],
        ["nis2_ciberseguridad", "irpf_residencia", "subvenciones_digitalizacion"],
    ),
    (
        "¿Cuándo es necesario designar un Delegado de Protección de Datos (DPO) en una empresa de IA?",
        ["lopdgdd_delegado", "rgpd35_dpia"],
        ["eu99_sanciones_prohibiciones", "covid_alarma", "ley_competencia"],
    ),

    # -- Intersección EU AI Act + RGPD --
    (
        "¿Cómo se coordinan el EU AI Act y el RGPD cuando un sistema de IA trata datos personales?",
        ["eu26_desplegadores", "rgpd6_bases_legales", "rgpd35_dpia"],
        ["nis2_ciberseguridad", "irpf_residencia", "et_despido"],
    ),
    (
        "¿Qué autoridad supervisa un sistema de IA que también vulnera el RGPD: la AESIA o la AEPD?",
        ["aesia_competencias", "aesia_funciones", "rgpd83_multas"],
        ["eu65_euai_board", "irpf_residencia", "lssi_comercio"],
    ),
    (
        "¿Es compatible el principio de minimización de datos del RGPD con el requisito de datos "
        "suficientes para entrenar IA de alto riesgo?",
        ["eu10_datos", "rgpd25_privacidad_diseno", "rgpd6_bases_legales"],
        ["eu99_sanciones_prohibiciones", "covid_alarma", "ley_competencia"],
    ),
    (
        "¿El EU AI Act tiene su propio régimen de sanciones o depende del RGPD?",
        ["eu99_sanciones_prohibiciones", "eu99_sanciones_requisitos", "rgpd83_multas"],
        ["irpf_residencia", "et_despido", "subvenciones_digitalizacion"],
    ),

    # -- Vigilancia poscomercialización e incidentes --
    (
        "¿Qué sistema de vigilancia poscomercialización debe establecer un proveedor de IA?",
        ["eu72_vigilancia", "eu17_sgc", "aesia_poscomercializacion"],
        ["rgpd_derechos_acceso", "irpf_residencia", "dora_resiliencia"],
    ),
    (
        "¿En qué plazo debe notificarse un incidente grave de un sistema de IA a las autoridades?",
        ["eu73_incidentes", "aesia_incidentes"],
        ["eu99_sanciones_prohibiciones", "covid_alarma", "lssi_comercio"],
    ),
    (
        "¿Qué medidas correctoras debe adoptar un proveedor tras detectar un fallo en su sistema de IA?",
        ["eu73_incidentes", "eu72_vigilancia", "eu17_sgc"],
        ["rgpd6_bases_legales", "irpf_residencia", "et_despido"],
    ),

    # -- Clasificaciones específicas avanzadas --
    (
        "¿Qué obligaciones de transparencia y supervisión humana aplican a los sistemas de IA usados "
        "en hospitales y clínicas?",
        ["eu_anex3_sanidad", "eu14_supervision_humana", "eu13_transparencia_desplegador"],
        ["rgpd22_decisiones_auto", "irpf_residencia", "ley_competencia"],
    ),
    (
        "¿Pueden los ayuntamientos usar sistemas de IA para priorizar el reparto de ayudas sociales?",
        ["eu_anex3_credito", "eu6_clasificacion", "eu26_desplegadores"],
        ["irpf_residencia", "covid_alarma", "lssi_comercio"],
    ),
    (
        "¿Cómo clasifica el EU AI Act a los sistemas de IA usados en procesos electorales?",
        ["eu_anex3_judicial", "eu5_scoring_social"],
        ["eu99_sanciones_prohibiciones", "irpf_residencia", "dora_resiliencia"],
    ),
    (
        "¿Qué dice el EU AI Act sobre los sistemas de IA que generan textos periodísticos o noticias?",
        ["eu50_transparencia_limitado", "eu53_obligaciones_gpai"],
        ["eu5_scoring_social", "subvenciones_digitalizacion", "et_despido"],
    ),
    (
        "¿Los sistemas de IA de segunda mano o modificados por el comprador mantienen su clasificación?",
        ["eu25_cadena_valor", "eu43_conformidad"],
        ["eu99_sanciones_prohibiciones", "irpf_residencia", "lssi_comercio"],
    ),

    # -- Protección de grupos vulnerables --
    (
        "¿Cómo protege el EU AI Act a los menores frente a sistemas de IA que les afectan?",
        ["eu5_vulnerabilidades", "eu14_supervision_humana", "eu_anex3_educacion"],
        ["rgpd6_bases_legales", "irpf_residencia", "codigo_civil_contratos"],
    ),
    (
        "¿Puede usarse IA para clasificar a personas según discapacidad en la concesión de seguros?",
        ["eu5_vulnerabilidades", "eu_anex3_credito", "rgpd9_datos_sensibles"],
        ["covid_alarma", "et_despido", "lssi_comercio"],
    ),

    # -- Sector financiero y seguros --
    (
        "¿Qué requisitos impone el EU AI Act a los sistemas de IA usados en la evaluación de riesgo crediticio?",
        ["eu_anex3_credito", "eu6_clasificacion", "eu9_gestion_riesgos"],
        ["dora_resiliencia", "irpf_residencia", "ley_competencia"],
    ),
    (
        "¿El Reglamento DORA y el EU AI Act se solapan en el sector financiero?",
        ["eu6_clasificacion", "eu9_gestion_riesgos"],
        ["dora_resiliencia", "irpf_residencia", "subvenciones_digitalizacion"],
    ),

    # -- Sector público --
    (
        "¿Qué obligaciones adicionales tienen los organismos públicos que despliegan IA de alto riesgo?",
        ["eu26_desplegadores", "eu49_registro", "aesia_competencias"],
        ["irpf_residencia", "covid_alarma", "lssi_comercio"],
    ),
    (
        "¿Puede la administración pública usar sistemas de IA para tomar decisiones administrativas "
        "que afecten a los ciudadanos?",
        ["eu26_desplegadores", "rgpd22_decisiones_auto", "eu6_clasificacion"],
        ["irpf_residencia", "et_despido", "codigo_civil_contratos"],
    ),

    # -- Derechos ciudadanos --
    (
        "¿Qué derecho tiene un ciudadano a saber que una decisión le fue tomada por un sistema de IA?",
        ["eu50_transparencia_limitado", "rgpd22_decisiones_auto", "rgpd13_info"],
        ["eu99_sanciones_prohibiciones", "irpf_residencia", "ley_competencia"],
    ),
    (
        "¿Puede una persona impugnar o revertir una decisión tomada por un sistema de IA?",
        ["rgpd22_decisiones_auto", "eu14_supervision_humana"],
        ["eu9_gestion_riesgos", "covid_alarma", "lssi_comercio"],
    ),
    (
        "¿Qué es el derecho a la explicación algorítmica y en qué normativa se recoge?",
        ["rgpd22_decisiones_auto", "eu13_transparencia_desplegador"],
        ["eu99_sanciones_prohibiciones", "irpf_residencia", "subvenciones_digitalizacion"],
    ),

    # -- NIS2 y ciberseguridad en IA (hard negatives específicos) --
    (
        "¿Qué dice el EU AI Act sobre la ciberseguridad de los sistemas de IA?",
        ["eu15_exactitud", "eu9_gestion_riesgos"],
        ["nis2_ciberseguridad", "irpf_residencia", "dora_resiliencia"],
    ),
    (
        "¿Cuáles son los requisitos de resiliencia frente a ataques que impone el EU AI Act?",
        ["eu15_exactitud", "eu55_gpai_obligaciones_sistemico"],
        ["nis2_ciberseguridad", "irpf_residencia", "codigo_civil_contratos"],
    ),

    # -- Explicabilidad e interpretabilidad --
    (
        "¿Exige el EU AI Act que los sistemas de IA de alto riesgo sean interpretables o explicables?",
        ["eu13_transparencia_desplegador", "eu14_supervision_humana", "eu15_exactitud"],
        ["eu99_sanciones_prohibiciones", "irpf_residencia", "et_despido"],
    ),
    (
        "¿Qué información sobre el funcionamiento del sistema de IA debe facilitarse al usuario final?",
        ["eu13_transparencia_desplegador", "eu50_transparencia_limitado"],
        ["rgpd13_info", "subvenciones_digitalizacion", "ley_competencia"],
    ),

    # -- Aplicación en recursos humanos --
    (
        "¿Pueden las empresas usar IA para evaluar el rendimiento de sus empleados en tiempo real?",
        ["eu_anex3_rrhh", "eu6_clasificacion", "eu14_supervision_humana"],
        ["rgpd22_decisiones_auto", "irpf_residencia", "et_despido"],
    ),
    (
        "¿Qué obligaciones tiene un departamento de RRHH que implementa IA para despedir empleados?",
        ["eu_anex3_rrhh", "eu26_desplegadores", "rgpd22_decisiones_auto"],
        ["et_despido", "irpf_residencia", "codigo_civil_contratos"],
    ),

    # -- Protección de datos específica de IA --
    (
        "¿Cuándo requiere el RGPD una evaluación de impacto (DPIA) para sistemas de IA con datos biométricos?",
        ["rgpd35_dpia", "rgpd9_datos_sensibles", "eu5_categorizacion_biomet"],
        ["eu99_sanciones_prohibiciones", "irpf_residencia", "lssi_comercio"],
    ),
    (
        "¿Qué restricciones impone el RGPD sobre el uso de datos de salud para entrenar IA?",
        ["rgpd9_datos_sensibles", "rgpd6_bases_legales", "eu10_datos"],
        ["eu99_sanciones_prohibiciones", "covid_alarma", "dora_resiliencia"],
    ),

    # -- Registro y trazabilidad --
    (
        "¿Dónde debe registrarse un sistema de IA de alto riesgo antes de ponerlo en el mercado europeo?",
        ["eu49_registro", "eu47_declaracion"],
        ["rgpd13_info", "irpf_residencia", "et_despido"],
    ),
    (
        "¿Qué contiene la base de datos pública de sistemas de IA de alto riesgo de la UE?",
        ["eu49_registro", "eu65_euai_board"],
        ["eu99_sanciones_prohibiciones", "subvenciones_digitalizacion", "lssi_comercio"],
    ),

    # -- Acreditación y organismos notificados --
    (
        "¿Qué son los organismos notificados en el EU AI Act y cuándo intervienen?",
        ["eu43_conformidad", "eu6_clasificacion"],
        ["aesia_funciones", "irpf_residencia", "codigo_civil_contratos"],
    ),

    # -- Aplicación extraterritorial --
    (
        "¿Aplica el EU AI Act a empresas de fuera de la UE cuyos sistemas de IA se usan en Europa?",
        ["eu16_obligaciones_prov", "eu25_cadena_valor"],
        ["eu99_sanciones_prohibiciones", "irpf_residencia", "lssi_comercio"],
    ),
    (
        "¿Qué es el representante autorizado de un proveedor de IA fuera de la UE?",
        ["eu16_obligaciones_prov", "eu25_cadena_valor"],
        ["rgpd6_bases_legales", "subvenciones_digitalizacion", "et_despido"],
    ),

    # -- Sistemas exentos --
    (
        "¿Existen categorías de sistemas de IA exentos del EU AI Act?",
        ["eu6_clasificacion", "eu5_biomet_remota"],
        ["eu99_sanciones_prohibiciones", "irpf_residencia", "nis2_ciberseguridad"],
    ),
    (
        "¿Aplica el EU AI Act a sistemas de IA militares o de seguridad nacional?",
        ["eu6_clasificacion", "eu5_subliminal"],
        ["eu99_sanciones_prohibiciones", "irpf_residencia", "dora_resiliencia"],
    ),

    # -- Consultas mixtas / complejas adicionales --
    (
        "Un hospital despliega un sistema de IA de apoyo al diagnóstico que trata datos de salud. "
        "¿Qué normativas aplican y qué autoridades supervisan?",
        ["eu_anex3_sanidad", "eu26_desplegadores", "rgpd9_datos_sensibles", "aesia_competencias"],
        ["irpf_residencia", "covid_alarma", "lssi_comercio"],
    ),
    (
        "Una startup desarrolla un modelo GPAI con más de 10^25 FLOPs de entrenamiento. "
        "¿Qué obligaciones adicionales tiene frente a una GPAI sin riesgo sistémico?",
        ["eu51_gpai_riesgo_sistemico", "eu55_gpai_obligaciones_sistemico", "eu53_obligaciones_gpai"],
        ["eu99_sanciones_prohibiciones", "irpf_residencia", "subvenciones_digitalizacion"],
    ),
    (
        "Una empresa usa IA para monitorizar las emociones de sus clientes en videollamadas. "
        "¿Es legal según el EU AI Act y el RGPD?",
        ["eu5_subliminal", "eu5_categorizacion_biomet", "rgpd9_datos_sensibles"],
        ["eu43_conformidad", "irpf_residencia", "codigo_civil_contratos"],
    ),
    (
        "¿Qué diferencia hay entre el marcado CE de un producto y la declaración de conformidad "
        "del EU AI Act para sistemas de IA de alto riesgo?",
        ["eu43_conformidad", "eu47_declaracion", "eu6_clasificacion"],
        ["rgpd83_multas", "irpf_residencia", "ley_competencia"],
    ),
    (
        "¿El EU AI Act permite usar IA para el seguimiento y puntuación del rendimiento académico "
        "de estudiantes en exámenes?",
        ["eu_anex3_educacion", "eu5_scoring_social", "eu6_clasificacion"],
        ["rgpd6_bases_legales", "covid_alarma", "subvenciones_digitalizacion"],
    ),
]

# ============================================================
# 3. GENERACIÓN DEL DATASET JSONL
# ============================================================

def expand_pairs(query_pairs: list) -> list[dict]:
    """Expande la lista de queries en ejemplos individuales (query, document, label)."""
    records = []
    for query, relevant_keys, non_relevant_keys in query_pairs:
        for key in relevant_keys:
            if key not in DOCS:
                raise ValueError(f"Clave no encontrada en DOCS: '{key}'")
            records.append({
                "query":    query,
                "document": DOCS[key]["text"],
                "label":    "relevante",
            })
        for key in non_relevant_keys:
            if key not in DOCS:
                raise ValueError(f"Clave no encontrada en DOCS: '{key}'")
            records.append({
                "query":    query,
                "document": DOCS[key]["text"],
                "label":    "no relevante",
            })
    return records


def main():
    records = expand_pairs(QUERY_PAIRS)
    random.shuffle(records)

    n_total     = len(records)
    n_relevante = sum(1 for r in records if r["label"] == "relevante")
    n_no_rel    = n_total - n_relevante
    n_queries   = len(QUERY_PAIRS)

    print(f"Dataset generado:")
    print(f"  Queries:       {n_queries}")
    print(f"  Ejemplos:      {n_total}")
    print(f"  Relevantes:    {n_relevante} ({n_relevante/n_total*100:.1f}%)")
    print(f"  No relevantes: {n_no_rel} ({n_no_rel/n_total*100:.1f}%)")

    # Detectar duplicados
    seen = set()
    dups = 0
    for r in records:
        key = (r["query"][:80], r["document"][:80])
        if key in seen:
            dups += 1
        seen.add(key)
    if dups:
        print(f"  ⚠️  Duplicados detectados: {dups}")

    # Guardar
    out_path = Path(__file__).parent / "processed" / "grading_dataset.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"\nDataset guardado en: {out_path}")
    print(f"  ({out_path.stat().st_size / 1024:.1f} KB)")

    # Mostrar muestra
    print("\nMuestra (primeros 3 ejemplos):")
    for r in records[:3]:
        print("-" * 70)
        print(f"  Query:    {r['query'][:90]}...")
        print(f"  Label:    {r['label']}")
        print(f"  Doc:      {r['document'][:100]}...")


if __name__ == "__main__":
    main()
