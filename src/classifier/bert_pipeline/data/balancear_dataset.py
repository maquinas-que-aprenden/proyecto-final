"""Script de balanceo del dataset EU AI Act.

Añade filas nuevas (redactadas manualmente) a las clases minoritarias
hasta alcanzar 208 ejemplos por clase (igual que la clase mayoritaria: inaceptable).

Clases a completar:
  alto_riesgo     : 136 → 208  (+72)
  riesgo_minimo   : 169 → 208  (+39)
  riesgo_limitado :  87 → 208  (+121)
"""

from pathlib import Path
import pandas as pd

CSV_PATH = Path(__file__).parent.parent.parent / "classifier_dataset_fusionado" / "datasets" / "eu_ai_act_flagged_es_limpio.csv"

# ---------------------------------------------------------------------------
# Nuevas descripciones — redactadas manualmente
# Formato: (descripcion, etiqueta_normalizada)
# ---------------------------------------------------------------------------

NUEVAS_FILAS = [

    # =========================================================
    # ALTO RIESGO (+72) — Anexo III EU AI Act
    # =========================================================
    ("Sistema de puntuación crediticia automatizado que evalúa la solvencia de solicitantes de préstamos hipotecarios para bancos minoristas utilizando historial financiero y datos demográficos.", "alto_riesgo"),
    ("Plataforma de selección de currículums que filtra y clasifica automáticamente candidatos a puestos de trabajo en función de sus competencias y experiencia.", "alto_riesgo"),
    ("Sistema de IA para el triaje de urgencias hospitalarias que asigna prioridad de atención a pacientes según la gravedad de los síntomas descritos.", "alto_riesgo"),
    ("Herramienta de apoyo a decisiones judiciales que analiza jurisprudencia y propone recomendaciones de sentencia en causas de derecho penal.", "alto_riesgo"),
    ("Sistema de evaluación automatizada de solicitudes de asilo que analiza la coherencia del relato del solicitante y lo contrasta con bases de datos de conflictos.", "alto_riesgo"),
    ("Plataforma de predicción de riesgo de reincidencia delictiva utilizada por el sistema penitenciario para informar decisiones sobre libertad condicional.", "alto_riesgo"),
    ("Sistema de admisión universitaria que clasifica y puntúa automáticamente a los candidatos a plazas de grado mediante un algoritmo de selección.", "alto_riesgo"),
    ("IA para la detección de fraude en seguros de salud que analiza reclamaciones y marca automáticamente expedientes para revisión de posible fraude.", "alto_riesgo"),
    ("Sistema de gestión de semáforos en infraestructuras críticas de tráfico urbano que optimiza flujos mediante IA con impacto directo en la seguridad vial.", "alto_riesgo"),
    ("Herramienta de evaluación del desempeño laboral que genera puntuaciones automáticas para empleados y alimenta decisiones de promoción y despido.", "alto_riesgo"),
    ("Sistema de IA para la gestión autónoma de redes eléctricas que redirige la distribución de energía ante fallos sin intervención humana inmediata.", "alto_riesgo"),
    ("Plataforma de análisis de riesgo para la concesión de microcréditos a autónomos que incluye variables de comportamiento en redes sociales.", "alto_riesgo"),
    ("Sistema de identificación biométrica por huella dactilar en controles fronterizos para verificar la identidad de viajeros procedentes de terceros países.", "alto_riesgo"),
    ("Herramienta de IA para la evaluación de solicitudes de subsidios de desempleo que clasifica solicitudes según probabilidad de elegibilidad.", "alto_riesgo"),
    ("Sistema de detección de anomalías en infraestructuras de abastecimiento de agua que identifica posibles ataques o fallos críticos en tiempo real.", "alto_riesgo"),
    ("IA para la evaluación de riesgo en operaciones quirúrgicas que analiza el historial del paciente y propone protocolos de intervención adaptados.", "alto_riesgo"),
    ("Sistema de gestión autónoma del tráfico aéreo que asiste a controladores en la asignación de rutas y altitudes para evitar colisiones.", "alto_riesgo"),
    ("Plataforma de scoring para el acceso a vivienda de protección oficial que puntúa automáticamente a solicitantes según criterios socioeconómicos.", "alto_riesgo"),
    ("Sistema de evaluación académica que califica automáticamente exámenes de acceso a funcionarial mediante análisis de respuestas abiertas.", "alto_riesgo"),
    ("Herramienta de apoyo a la inspección laboral que identifica empresas con alto riesgo de incumplimiento normativo para programar auditorías prioritarias.", "alto_riesgo"),
    ("Sistema de reconocimiento de voz para identificar a sospechosos en grabaciones utilizadas como prueba en procedimientos penales.", "alto_riesgo"),
    ("Plataforma de IA para la priorización de listas de espera quirúrgicas que reordena pacientes según criterios clínicos y de urgencia médica.", "alto_riesgo"),
    ("Sistema de detección de comportamiento sospechoso en infraestructuras de transporte ferroviario para alertar a las fuerzas de seguridad.", "alto_riesgo"),
    ("Herramienta de análisis de riesgo crediticio para la concesión de líneas de financiación a pymes basada en datos de facturación y mercado.", "alto_riesgo"),
    ("IA para la evaluación automatizada de la capacidad de conducción de personas mayores con el fin de renovar o revocar permisos de conducir.", "alto_riesgo"),
    ("Sistema de clasificación de estudiantes para programas educativos de refuerzo financiado con fondos públicos basado en rendimiento previo.", "alto_riesgo"),
    ("Plataforma de análisis de reclamaciones médicas que determina automáticamente la cobertura de seguros de salud y aprueba o deniega tratamientos.", "alto_riesgo"),
    ("Sistema de evaluación de riesgo de violencia de género que analiza llamadas de emergencia y determina el nivel de protección policial necesario.", "alto_riesgo"),
    ("Herramienta de IA para asignar recursos de servicios sociales municipales a familias en situación de vulnerabilidad según criterios de prioridad.", "alto_riesgo"),
    ("Sistema de detección de fraude fiscal que identifica contribuyentes con alto riesgo de evasión para priorizar inspecciones tributarias.", "alto_riesgo"),
    ("Plataforma de evaluación de aptitudes para la selección de personal de seguridad en instalaciones críticas mediante pruebas psicométricas automatizadas.", "alto_riesgo"),
    ("Sistema de IA para el diagnóstico asistido de enfermedades cardiovasculares mediante el análisis de electrocardiogramas en atención primaria.", "alto_riesgo"),
    ("Herramienta de monitorización del estado de presas hidráulicas que activa protocolos de emergencia de forma autónoma ante anomalías detectadas.", "alto_riesgo"),
    ("Sistema de clasificación de perfiles de riesgo para la asignación de fianzas en procedimientos penales utilizado por juzgados de instrucción.", "alto_riesgo"),
    ("Plataforma de evaluación de elegibilidad para ayudas a la dependencia que puntúa automáticamente el grado de autonomía de solicitantes.", "alto_riesgo"),
    ("IA para la toma de decisiones en préstamos estudiantiles con aval público que evalúa la probabilidad de devolución según perfil académico y socioeconómico.", "alto_riesgo"),
    ("Sistema de análisis de imágenes médicas que detecta nódulos pulmonares en radiografías de tórax para el cribado de cáncer de pulmón.", "alto_riesgo"),
    ("Herramienta de apoyo a decisiones de internamiento psiquiátrico involuntario basada en el análisis de historial clínico y evaluaciones previas.", "alto_riesgo"),
    ("Sistema de IA para la gestión autónoma de la velocidad y frenado en trenes de alta velocidad sin intervención del maquinista en situaciones críticas.", "alto_riesgo"),
    ("Plataforma de evaluación de riesgo de recaída en pacientes oncológicos que determina la frecuencia de seguimiento y las pruebas diagnósticas recomendadas.", "alto_riesgo"),
    ("Sistema de puntuación de solvencia para propietarios en solicitudes de alquiler de vivienda habitual utilizado por agencias inmobiliarias.", "alto_riesgo"),
    ("Herramienta de análisis de señales vitales en cuidados intensivos que alerta al personal médico sobre deterioro inminente del estado del paciente.", "alto_riesgo"),
    ("Sistema de evaluación de solicitudes de reagrupación familiar en procedimientos de inmigración que clasifica casos por probabilidad de resolución favorable.", "alto_riesgo"),
    ("IA para la asignación de plazas en escuelas infantiles municipales que pondera automáticamente criterios socioeconómicos y de proximidad.", "alto_riesgo"),
    ("Sistema de detección de incidencias en redes de telecomunicaciones críticas que activa medidas de contingencia de forma automática.", "alto_riesgo"),
    ("Plataforma de evaluación del riesgo de absentismo laboral utilizada por empresas para tomar decisiones sobre contratación de personal temporal.", "alto_riesgo"),
    ("Sistema de apoyo a la decisión sobre tratamientos de fertilidad financiados por el sistema público de salud basado en probabilidades de éxito.", "alto_riesgo"),
    ("Herramienta de análisis de solicitudes de indulto que evalúa el expediente penal y proporciona informes de riesgo a los órganos competentes.", "alto_riesgo"),
    ("Sistema de gestión de incidentes en infraestructuras de gas natural que activa válvulas de seguridad de forma autónoma ante fugas detectadas.", "alto_riesgo"),
    ("Plataforma de evaluación del riesgo de abandono escolar temprano que clasifica a estudiantes para la asignación de recursos de orientación educativa.", "alto_riesgo"),
    ("IA para el diagnóstico diferencial de enfermedades raras que analiza síntomas y pruebas complementarias y genera hipótesis diagnósticas priorizadas.", "alto_riesgo"),
    ("Sistema de evaluación de solicitudes de permiso de residencia permanente que analiza el historial del solicitante y emite recomendaciones de resolución.", "alto_riesgo"),
    ("Herramienta de clasificación de riesgo para operaciones de transplante de órganos que prioriza receptores en lista de espera según criterios clínicos.", "alto_riesgo"),
    ("Sistema de detección de ciberataques en infraestructuras de comunicaciones gubernamentales con capacidad de respuesta autónoma parcial.", "alto_riesgo"),
    ("Plataforma de análisis de productividad individual de trabajadores en centros de llamadas que informa decisiones de gestión de personal.", "alto_riesgo"),
    ("Sistema de evaluación del riesgo de impago en contratos de suministro energético para determinar el acceso al bono social de electricidad.", "alto_riesgo"),
    ("IA para la selección de candidatos a programas de formación profesional financiados con fondos europeos basada en perfiles de empleabilidad.", "alto_riesgo"),
    ("Herramienta de apoyo a la clasificación penitenciaria que asigna el régimen de internamiento a reclusos según el perfil criminológico calculado.", "alto_riesgo"),
    ("Sistema de monitorización de la seguridad estructural de puentes y viaductos que activa alertas de restricción de tráfico de forma autónoma.", "alto_riesgo"),
    ("Plataforma de análisis de reclamaciones laborales ante inspección de trabajo que determina la prioridad de investigación de denuncias.", "alto_riesgo"),
    ("Sistema de puntuación de crédito alternativo que utiliza datos de comportamiento de pago de servicios y telecomunicaciones para evaluar solvencia.", "alto_riesgo"),
    ("Herramienta de apoyo diagnóstico en dermatología que analiza fotografías de lesiones cutáneas y clasifica su malignidad potencial.", "alto_riesgo"),
    ("Sistema de evaluación de riesgo de reincidencia en maltratadores condenados utilizado para determinar medidas de alejamiento y control.", "alto_riesgo"),
    ("Plataforma de asignación de recursos en servicios de emergencias médicas que determina la prioridad de ambulancias según la gravedad del incidente.", "alto_riesgo"),
    ("IA para la evaluación de la aptitud psicológica de candidatos a fuerzas y cuerpos de seguridad del estado mediante análisis de respuestas.", "alto_riesgo"),
    ("Sistema de análisis de solicitudes de subvenciones agrícolas que clasifica expedientes según elegibilidad y prioridad de pago establecidos normativamente.", "alto_riesgo"),
    ("Herramienta de apoyo a decisiones de colocación de menores en acogida familiar que analiza el perfil familiar y del menor para la asignación.", "alto_riesgo"),
    ("Sistema de evaluación de riesgos laborales en obras de construcción que clasifica tareas y trabajadores según probabilidad de accidente.", "alto_riesgo"),
    ("Plataforma de identificación de deudores de alto riesgo para embargos preventivos en procedimientos judiciales de reclamación de deudas.", "alto_riesgo"),
    ("IA para la evaluación de la elegibilidad de pacientes a ensayos clínicos que filtra candidatos según criterios de inclusión y exclusión del protocolo.", "alto_riesgo"),
    ("Sistema de apoyo a la planificación de evacuaciones de emergencia que calcula rutas y capacidades de forma autónoma ante desastres naturales.", "alto_riesgo"),
    ("Plataforma de análisis del historial de conducción para la clasificación de conductores por tramos de riesgo en pólizas de seguro de automóvil.", "alto_riesgo"),

    # =========================================================
    # RIESGO_MINIMO (+39)
    # =========================================================
    ("Sistema de filtrado de spam que analiza correos electrónicos corporativos y los clasifica automáticamente como spam o legítimos para mantener la bandeja de entrada organizada.", "riesgo_minimo"),
    ("Motor de recomendación de películas y series que sugiere contenido en una plataforma de streaming basándose en el historial de visualización del usuario.", "riesgo_minimo"),
    ("Inteligencia artificial integrada en un videojuego de estrategia que controla a los personajes no jugadores y adapta su dificultad según el desempeño del jugador.", "riesgo_minimo"),
    ("Sistema de optimización logística que calcula rutas de entrega para flotas de transporte minimizando el consumo de combustible y los tiempos de tránsito.", "riesgo_minimo"),
    ("Herramienta de corrección ortográfica y gramatical que asiste a redactores en la revisión de textos mediante sugerencias de mejora estilística.", "riesgo_minimo"),
    ("Sistema de monitorización predictiva de maquinaria industrial que detecta anomalías en sensores para planificar el mantenimiento preventivo.", "riesgo_minimo"),
    ("Plataforma de gestión de inventario que utiliza aprendizaje automático para predecir la demanda de productos y optimizar el stock en almacenes.", "riesgo_minimo"),
    ("Asistente de IA para la planificación de cultivos agrícolas que analiza datos meteorológicos y del suelo para recomendar épocas de siembra y riego.", "riesgo_minimo"),
    ("Sistema de clasificación automática de documentos empresariales que organiza contratos, facturas y correspondencia en categorías predefinidas.", "riesgo_minimo"),
    ("Motor de búsqueda interno corporativo que utiliza IA para mejorar la relevancia de los resultados en repositorios de documentación técnica.", "riesgo_minimo"),
    ("Herramienta de generación de borradores de correos electrónicos que sugiere respuestas predefinidas basadas en el contenido del mensaje recibido.", "riesgo_minimo"),
    ("Sistema de optimización energética para edificios de oficinas que ajusta automáticamente la climatización según la ocupación y condiciones exteriores.", "riesgo_minimo"),
    ("IA para el control de calidad en líneas de producción de alimentos que detecta defectos visuales en productos mediante visión por computador.", "riesgo_minimo"),
    ("Asistente virtual para la organización de agendas y calendarios que sugiere franjas horarias para reuniones según disponibilidad y prioridades.", "riesgo_minimo"),
    ("Sistema de análisis de sentimientos en redes sociales para monitorizar la percepción de marca sin tomar decisiones automatizadas sobre personas.", "riesgo_minimo"),
    ("Herramienta de traducción automática para documentos corporativos internos que facilita la comunicación entre equipos de distintos países.", "riesgo_minimo"),
    ("Motor de recomendación de productos en una tienda de comercio electrónico de artículos deportivos basado en historial de navegación del usuario.", "riesgo_minimo"),
    ("Sistema de predicción meteorológica local que combina datos de satélites con modelos de aprendizaje automático para mejorar la precisión de las previsiones.", "riesgo_minimo"),
    ("IA de asistencia en el diseño gráfico que sugiere paletas de colores, tipografías y composiciones basándose en el estilo del proyecto.", "riesgo_minimo"),
    ("Sistema de detección de avería en vehículos de empresa que analiza datos del motor en tiempo real para recomendar revisiones al conductor.", "riesgo_minimo"),
    ("Plataforma de análisis de datos de ventas que identifica tendencias y patrones de consumo para apoyar decisiones comerciales de marketing.", "riesgo_minimo"),
    ("Sistema de clasificación automática de tickets de soporte técnico que asigna incidencias a los departamentos correspondientes según su contenido.", "riesgo_minimo"),
    ("Herramienta de IA para la generación de informes financieros rutinarios a partir de datos contables estructurados sin impacto en decisiones de inversión.", "riesgo_minimo"),
    ("Motor de optimización de precios dinámico para una cadena de supermercados que ajusta descuentos en productos de alta rotación próximos a caducar.", "riesgo_minimo"),
    ("Sistema de recomendación de música en una plataforma de streaming que crea listas de reproducción personalizadas según el estado de ánimo detectado.", "riesgo_minimo"),
    ("Asistente de IA para jardinería y plantas de interior que identifica especies mediante fotografía y recomienda cuidados y riegos específicos.", "riesgo_minimo"),
    ("Sistema de predicción de demanda eléctrica para una compañía distribuidora que optimiza la carga en la red durante horas valle y punta.", "riesgo_minimo"),
    ("Herramienta de generación automática de subtítulos para vídeos corporativos de formación interna con revisión humana obligatoria posterior.", "riesgo_minimo"),
    ("IA de reconocimiento de objetos para un almacén automatizado que identifica y clasifica paquetes según su forma, tamaño y etiquetado.", "riesgo_minimo"),
    ("Sistema de asistencia en la composición musical que sugiere acordes, melodías y arreglos basándose en el género y estilo elegido por el usuario.", "riesgo_minimo"),
    ("Motor de personalización de contenidos en un portal de noticias que ordena artículos según los intereses inferidos del historial de lectura.", "riesgo_minimo"),
    ("Sistema de optimización de rutas de reparto para un servicio de mensajería urbana que considera el tráfico en tiempo real y ventanas de entrega.", "riesgo_minimo"),
    ("Herramienta de análisis de código fuente que detecta errores de programación comunes y sugiere refactorizaciones para mejorar la calidad del software.", "riesgo_minimo"),
    ("IA integrada en una aplicación de cocina que genera recetas personalizadas según los ingredientes disponibles y las preferencias dietéticas del usuario.", "riesgo_minimo"),
    ("Sistema de monitorización ambiental que analiza datos de sensores de calidad del aire en una ciudad y genera alertas informativas para la ciudadanía.", "riesgo_minimo"),
    ("Plataforma de e-learning que adapta la dificultad de ejercicios al ritmo del estudiante sin emitir certificaciones ni evaluar competencias oficiales.", "riesgo_minimo"),
    ("Sistema de asistencia a conductores que analiza el comportamiento de conducción y ofrece consejos de ahorro de combustible y seguridad vial.", "riesgo_minimo"),
    ("Herramienta de clasificación de correo postal digitalizado en una empresa de logística que ordena envíos por código postal y tipo de servicio.", "riesgo_minimo"),
    ("Motor de IA para la detección de duplicados en bases de datos corporativas que identifica registros redundantes para su revisión y consolidación manual.", "riesgo_minimo"),

    # =========================================================
    # RIESGO_LIMITADO (+121)
    # =========================================================
    ("Chatbot de atención al cliente en una entidad bancaria que responde consultas frecuentes sobre saldos y movimientos sin tomar decisiones sobre créditos.", "riesgo_limitado"),
    ("Sistema de recomendación de contenidos en una plataforma de noticias digitales que personaliza el orden de artículos según los intereses del lector.", "riesgo_limitado"),
    ("Herramienta de generación de imágenes mediante inteligencia artificial para campañas publicitarias con etiqueta visible de contenido generado por IA.", "riesgo_limitado"),
    ("Asistente virtual de IA en una aplicación de salud mental que ofrece técnicas de mindfulness y relajación sin sustituir al profesional sanitario.", "riesgo_limitado"),
    ("Sistema de reconocimiento de emociones en llamadas de servicio al cliente que alerta al agente humano cuando detecta frustración en el interlocutor.", "riesgo_limitado"),
    ("Chatbot para la resolución de incidencias técnicas de telecomunicaciones que guía al usuario en pasos de diagnóstico básico con escalado a humano.", "riesgo_limitado"),
    ("Plataforma de traducción automática de documentos legales con advertencia explícita al usuario de que se trata de una traducción generada por IA.", "riesgo_limitado"),
    ("Sistema de moderación de contenidos en una red social que señala automáticamente publicaciones potencialmente infractoras para revisión humana.", "riesgo_limitado"),
    ("Herramienta de generación de textos de marketing personalizados para correos electrónicos comerciales con indicación de que el contenido es generado por IA.", "riesgo_limitado"),
    ("Asistente conversacional de IA en un portal de e-commerce que ayuda a los usuarios a encontrar productos según sus preferencias declaradas.", "riesgo_limitado"),
    ("Sistema de detección de sentimientos en reseñas de productos para clasificarlos automáticamente como positivos, neutros o negativos en la plataforma.", "riesgo_limitado"),
    ("Chatbot de información turística que responde preguntas sobre atracciones, horarios y transporte en destinos sin emitir recomendaciones de riesgo.", "riesgo_limitado"),
    ("Herramienta de síntesis de voz realista para doblaje de contenidos audiovisuales con obligación de etiquetar el contenido como generado artificialmente.", "riesgo_limitado"),
    ("Sistema de recomendación de cursos en una plataforma de formación online que sugiere itinerarios de aprendizaje según el perfil del estudiante.", "riesgo_limitado"),
    ("Asistente de IA integrado en un portal inmobiliario que responde consultas sobre características de inmuebles sin asesorar sobre inversión.", "riesgo_limitado"),
    ("Chatbot de asistencia en trámites administrativos municipales que informa sobre documentación necesaria y plazos sin validar solicitudes oficiales.", "riesgo_limitado"),
    ("Sistema de generación de deepfakes para producciones cinematográficas con consentimiento de los actores y etiquetado obligatorio del contenido.", "riesgo_limitado"),
    ("Herramienta de análisis de sentimientos en comentarios de clientes de un restaurante para identificar áreas de mejora en el servicio.", "riesgo_limitado"),
    ("Asistente virtual de IA para la planificación de viajes que sugiere itinerarios, alojamientos y actividades según preferencias del usuario.", "riesgo_limitado"),
    ("Sistema de chatbot jurídico que proporciona información general sobre derechos y procedimientos legales con aviso de que no constituye asesoramiento profesional.", "riesgo_limitado"),
    ("Plataforma de generación de contenido en redes sociales que crea publicaciones y hashtags para marcas con etiqueta de contenido generado por IA.", "riesgo_limitado"),
    ("Herramienta de reconocimiento de emociones en entornos de formación virtual para adaptar el ritmo de aprendizaje sin calificar al alumno.", "riesgo_limitado"),
    ("Sistema de chatbot para reservas en restaurantes que gestiona disponibilidad y confirmaciones sin acceder a datos personales sensibles.", "riesgo_limitado"),
    ("Asistente de IA en una aplicación de idiomas que corrige pronunciación y gramática en ejercicios orales sin emitir certificados de competencia.", "riesgo_limitado"),
    ("Sistema de generación de música original mediante inteligencia artificial para proyectos audiovisuales con atribución explícita de autoría artificial.", "riesgo_limitado"),
    ("Chatbot de soporte técnico para software empresarial que guía a los usuarios en la resolución de problemas comunes mediante árboles de decisión.", "riesgo_limitado"),
    ("Plataforma de análisis de conversaciones en redes sociales para detectar tendencias de opinión pública sobre una marca sin perfilar individualmente a usuarios.", "riesgo_limitado"),
    ("Herramienta de generación automática de subtítulos para accesibilidad en plataformas de vídeo con revisión disponible por el usuario.", "riesgo_limitado"),
    ("Sistema de recomendación de libros en una biblioteca digital que sugiere títulos según el historial de lectura y valoraciones del usuario.", "riesgo_limitado"),
    ("Asistente de IA en una aplicación de fitness que propone rutinas de ejercicio personalizadas sin sustituir el consejo de un profesional médico.", "riesgo_limitado"),
    ("Chatbot de información farmacéutica que describe efectos y posología de medicamentos de venta libre con advertencia de consultar al farmacéutico.", "riesgo_limitado"),
    ("Sistema de moderación automática de contenido en una plataforma de videojuegos que detecta insultos en el chat para advertir a los usuarios.", "riesgo_limitado"),
    ("Herramienta de generación de presentaciones corporativas mediante IA que crea diapositivas a partir de puntos clave introducidos por el usuario.", "riesgo_limitado"),
    ("Asistente virtual en una plataforma de telemedicina que triaga síntomas menores y agenda citas con médicos sin emitir diagnósticos.", "riesgo_limitado"),
    ("Sistema de personalización de la interfaz de usuario en una aplicación bancaria que adapta los accesos directos según los hábitos de uso del cliente.", "riesgo_limitado"),
    ("Chatbot de orientación vocacional para estudiantes de secundaria que informa sobre salidas profesionales sin recomendar decisiones académicas vinculantes.", "riesgo_limitado"),
    ("Plataforma de análisis de menciones en prensa digital que clasifica artículos sobre una empresa según el tono editorial para el equipo de comunicación.", "riesgo_limitado"),
    ("Herramienta de generación de avatares digitales realistas para comunicaciones corporativas con etiqueta visible de origen artificial.", "riesgo_limitado"),
    ("Sistema de recomendación de rutas de senderismo en una aplicación de actividades al aire libre basado en nivel de dificultad y preferencias.", "riesgo_limitado"),
    ("Asistente de IA para la redacción de correos profesionales que sugiere frases y mejora el tono y la claridad del texto sin acceder al buzón.", "riesgo_limitado"),
    ("Chatbot de consulta de normativa fiscal que informa sobre plazos y requisitos generales de declaraciones sin interpretar casos individuales.", "riesgo_limitado"),
    ("Sistema de detección de bots en redes sociales que identifica cuentas automatizadas para informar a los administradores de la plataforma.", "riesgo_limitado"),
    ("Herramienta de generación de descripciones de productos para catálogos de e-commerce basada en especificaciones técnicas introducidas por el vendedor.", "riesgo_limitado"),
    ("Asistente de IA en una aplicación de meditación que guía sesiones de relajación y hace seguimiento del estado de ánimo sin acceder a datos médicos.", "riesgo_limitado"),
    ("Sistema de análisis de contratos que identifica cláusulas relevantes y posibles ambigüedades para revisión por parte del equipo jurídico.", "riesgo_limitado"),
    ("Chatbot de atención en una empresa de seguros de hogar que informa sobre coberturas y recoge datos iniciales de siniestros para derivarlos a un agente.", "riesgo_limitado"),
    ("Plataforma de generación de contenido educativo adaptado que crea ejercicios y explicaciones según el nivel del alumno sin certificar resultados.", "riesgo_limitado"),
    ("Herramienta de transcripción automática de reuniones corporativas que genera actas en texto con indicación de posibles errores de reconocimiento.", "riesgo_limitado"),
    ("Sistema de recomendación de podcasts en una plataforma de audio que crea listas de episodios según los intereses y el tiempo disponible del usuario.", "riesgo_limitado"),
    ("Asistente de IA para la gestión de redes sociales corporativas que programa publicaciones y sugiere contenidos sin publicar de forma autónoma.", "riesgo_limitado"),
    ("Chatbot de soporte de recursos humanos que responde preguntas frecuentes de empleados sobre beneficios, vacaciones y políticas de empresa.", "riesgo_limitado"),
    ("Sistema de detección de plagio en trabajos académicos que compara textos con bases de datos online y señala coincidencias para revisión docente.", "riesgo_limitado"),
    ("Herramienta de personalización de correos electrónicos de marketing masivo que adapta el asunto y el saludo según el segmento del receptor.", "riesgo_limitado"),
    ("Asistente de IA en una aplicación de dietas y nutrición que sugiere menús semanales según preferencias sin prescribir tratamientos dietéticos clínicos.", "riesgo_limitado"),
    ("Sistema de chatbot para el seguimiento de pedidos en una empresa de paquetería que informa en tiempo real sobre el estado del envío.", "riesgo_limitado"),
    ("Plataforma de análisis de reseñas de viajeros en portales turísticos que resume automáticamente las valoraciones de alojamientos y restaurantes.", "riesgo_limitado"),
    ("Herramienta de generación de guiones para vídeos explicativos corporativos basada en un resumen del tema proporcionado por el usuario.", "riesgo_limitado"),
    ("Sistema de recomendación de fondos de inversión en una plataforma de ahorro con aviso de que no constituye asesoramiento financiero personalizado.", "riesgo_limitado"),
    ("Asistente de IA en una tienda online de moda que combina prendas y sugiere conjuntos según las preferencias estéticas y el presupuesto del usuario.", "riesgo_limitado"),
    ("Chatbot de información meteorológica que responde consultas sobre previsiones locales y ofrece recomendaciones de vestimenta.", "riesgo_limitado"),
    ("Sistema de detección de tono en correos electrónicos corporativos que alerta al remitente si el mensaje puede interpretarse como agresivo.", "riesgo_limitado"),
    ("Plataforma de generación de FAQ automáticas para sitios web empresariales a partir de la documentación existente del producto o servicio.", "riesgo_limitado"),
    ("Herramienta de análisis de engagement en publicaciones de redes sociales que identifica el mejor horario de publicación para maximizar el alcance.", "riesgo_limitado"),
    ("Asistente de IA en una plataforma de crowdfunding que ayuda a redactores de proyectos a mejorar la descripción y el titular de su campaña.", "riesgo_limitado"),
    ("Sistema de chatbot para la configuración de seguros de vida que guía al usuario en la selección de coberturas sin emitir la póliza de forma autónoma.", "riesgo_limitado"),
    ("Herramienta de reconocimiento facial para el acceso a un evento privado con consentimiento explícito de los participantes y alternativa no biométrica.", "riesgo_limitado"),
    ("Sistema de análisis de comentarios en reuniones de empresa mediante procesamiento de lenguaje natural para identificar temas recurrentes en actas.", "riesgo_limitado"),
    ("Plataforma de generación de informes de sostenibilidad a partir de datos de consumo energético y emisiones introducidos por la empresa.", "riesgo_limitado"),
    ("Asistente de IA para la selección de canciones en bodas y eventos que crea listas de reproducción según el género musical y la duración del evento.", "riesgo_limitado"),
    ("Chatbot de consulta de precios en una plataforma de subastas online que informa sobre el valor estimado de artículos sin participar en las pujas.", "riesgo_limitado"),
    ("Sistema de personalización de la experiencia en un museo virtual que adapta el recorrido y las explicaciones según el perfil cultural del visitante.", "riesgo_limitado"),
    ("Herramienta de análisis de logs de sistema para detectar patrones de uso inusuales en aplicaciones empresariales y generar informes para el equipo TI.", "riesgo_limitado"),
    ("Sistema de chatbot en una plataforma de aprendizaje de matemáticas que explica conceptos y resuelve dudas sin calificar ni evaluar al estudiante.", "riesgo_limitado"),
    ("Asistente de IA en una aplicación de gestión de presupuesto personal que categoriza gastos y propone objetivos de ahorro sin acceder a datos bancarios.", "riesgo_limitado"),
    ("Plataforma de generación de cuentos infantiles personalizados donde el adulto especifica personajes, escenario y moraleja con etiqueta de contenido IA.", "riesgo_limitado"),
    ("Sistema de análisis de postura mediante la cámara del dispositivo para ofrecer recomendaciones ergonómicas durante el trabajo remoto.", "riesgo_limitado"),
    ("Herramienta de chatbot para la gestión de citas en una peluquería que consulta disponibilidad y confirma reservas sin procesar pagos.", "riesgo_limitado"),
    ("Asistente de IA en una plataforma de bricolaje del hogar que sugiere materiales y pasos de instalación según la descripción del proyecto del usuario.", "riesgo_limitado"),
    ("Sistema de detección de duplicados en campañas publicitarias digitales que identifica anuncios con contenido similar para optimizar el presupuesto.", "riesgo_limitado"),
    ("Chatbot de asistencia en la declaración de impuestos que guía al contribuyente en la introducción de datos sin validar ni presentar la declaración.", "riesgo_limitado"),
    ("Plataforma de análisis de datos de wearables deportivos que genera informes de rendimiento para atletas amateur sin diagnóstico médico.", "riesgo_limitado"),
    ("Herramienta de generación de nombres y eslóganes para nuevas marcas mediante IA basada en el sector y los valores de la empresa.", "riesgo_limitado"),
    ("Sistema de recomendación de proveedores en una plataforma de compras corporativas que filtra opciones según criterios de precio, calidad y plazo.", "riesgo_limitado"),
    ("Asistente de IA para la revisión de contratos de alquiler que señala cláusulas inusuales con aviso de que no sustituye el asesoramiento legal profesional.", "riesgo_limitado"),
    ("Sistema de chatbot para el seguimiento de proyectos en una agencia creativa que informa al cliente sobre el estado de cada entregable.", "riesgo_limitado"),
    ("Plataforma de personalización de experiencias en un parque de atracciones que sugiere atracciones según la edad y las preferencias del visitante.", "riesgo_limitado"),
    ("Herramienta de análisis de la cadena de suministro que identifica cuellos de botella en el proceso productivo para el equipo de operaciones.", "riesgo_limitado"),
    ("Sistema de detección de emociones en la voz de locutores de radio para proporcionar retroalimentación sobre el impacto comunicativo del programa.", "riesgo_limitado"),
    ("Asistente de IA en una aplicación de jardinería urbana que identifica plagas en plantas mediante fotografía y recomienda tratamientos ecológicos.", "riesgo_limitado"),
    ("Chatbot de información sobre trámites notariales que explica los documentos necesarios y los pasos del proceso sin actuar como representante legal.", "riesgo_limitado"),
    ("Sistema de generación automática de resúmenes ejecutivos de informes corporativos extensos con indicación de que se trata de un resumen generado por IA.", "riesgo_limitado"),
    ("Plataforma de análisis de interacciones en sesiones de formación virtual que mide la participación y el tiempo de atención para el formador.", "riesgo_limitado"),
    ("Herramienta de personalización de experiencias de juego en una plataforma de casino online con etiqueta de IA y opciones de autoexclusión disponibles.", "riesgo_limitado"),
    ("Asistente de IA para la gestión del tiempo en startups que analiza las reuniones y propone bloques de trabajo concentrado según la agenda semanal.", "riesgo_limitado"),
    ("Sistema de análisis de imagen para clasificar automáticamente fotografías en una aplicación de álbum familiar según el contenido detectado.", "riesgo_limitado"),
    ("Chatbot de orientación en trámites de extranjería que informa sobre documentación y plazos sin tomar decisiones sobre visados ni permisos.", "riesgo_limitado"),
    ("Plataforma de análisis de conversaciones de ventas que identifica palabras clave y momentos de éxito para entrenar a nuevos comerciales.", "riesgo_limitado"),
    ("Herramienta de generación de propuestas comerciales personalizadas para consultoras que adapta el contenido según el sector y el tamaño del cliente.", "riesgo_limitado"),
    ("Sistema de recomendación de artículos en una plataforma de segunda mano que muestra objetos similares a los buscados por el usuario.", "riesgo_limitado"),
    ("Asistente de IA para la resolución de conflictos en equipos de trabajo que propone dinámicas de mediación y técnicas de comunicación no violenta.", "riesgo_limitado"),
    ("Sistema de chatbot para la atención a socios de una ONG que responde consultas sobre cuotas, actividades y campañas de voluntariado.", "riesgo_limitado"),
    ("Plataforma de análisis de patrones de uso en aplicaciones SaaS que detecta usuarios en riesgo de abandono para el equipo de customer success.", "riesgo_limitado"),
    ("Herramienta de generación de abstracts científicos a partir del contenido de artículos de investigación con indicación de que es texto generado por IA.", "riesgo_limitado"),
    ("Sistema de reconocimiento de objetos en aplicaciones de realidad aumentada para identificar productos en tienda y mostrar información adicional.", "riesgo_limitado"),
    ("Asistente de IA en una plataforma de idiomas para empresas que sugiere contenidos formativos según el nivel y los objetivos profesionales del empleado.", "riesgo_limitado"),
    ("Chatbot de atención en una clínica veterinaria que informa sobre síntomas comunes y recomienda consultar al veterinario sin emitir diagnósticos.", "riesgo_limitado"),
    ("Sistema de análisis de comportamiento del conductor en flotas de empresa para generar informes de seguridad vial sin penalizar automáticamente.", "riesgo_limitado"),
    ("Plataforma de generación de plantillas de documentos legales estándar como contratos de prestación de servicios con aviso de revisión profesional.", "riesgo_limitado"),
    ("Herramienta de análisis de accesibilidad web que detecta barreras para usuarios con discapacidad y propone correcciones al equipo de desarrollo.", "riesgo_limitado"),
    ("Sistema de recomendación de actividades culturales en una agenda digital de ciudad que personaliza la selección según los gustos registrados del usuario.", "riesgo_limitado"),
    ("Asistente de IA en una plataforma de crowdsourcing que clasifica tareas y las asigna a colaboradores según sus habilidades sin evaluar su rendimiento.", "riesgo_limitado"),
    ("Chatbot de soporte en una plataforma de gamificación empresarial que resuelve dudas sobre insignias, retos y recompensas de los empleados.", "riesgo_limitado"),
    ("Sistema de análisis de tendencias en el mercado de moda que identifica estilos emergentes en redes sociales para los diseñadores de la marca.", "riesgo_limitado"),
    ("Plataforma de generación de correos de bienvenida personalizados para nuevos clientes de un banco con el nombre y el producto contratado.", "riesgo_limitado"),
    ("Herramienta de análisis de grabaciones de formación para identificar momentos de mayor atención del grupo y optimizar los contenidos formativos.", "riesgo_limitado"),
    ("Asistente de IA para la compra de entradas de eventos que filtra opciones según disponibilidad, precio y asientos preferentes sin bloquear entradas.", "riesgo_limitado"),
    ("Sistema de detección de lenguaje tóxico en foros de debate online que etiqueta comentarios para revisión por parte del equipo de moderación humana.", "riesgo_limitado"),
    ("Chatbot de consulta sobre normativa de prevención de riesgos laborales que informa sobre obligaciones generales sin evaluar situaciones de empresa.", "riesgo_limitado"),
    ("Plataforma de análisis de la satisfacción del empleado mediante encuestas procesadas por IA que agrupa resultados anónimos por departamento.", "riesgo_limitado"),
    ("Herramienta de generación de newsletters corporativas que crea contenidos a partir de los comunicados internos de la semana con etiqueta de IA.", "riesgo_limitado"),
    ("Sistema de recomendación de noticias financieras en una aplicación de inversión que personaliza el feed informativo sin emitir recomendaciones de compraventa.", "riesgo_limitado"),
]


def main():
    print(f"Cargando CSV: {CSV_PATH}")
    df = pd.read_csv(CSV_PATH)

    print("Distribución ANTES del balanceo:")
    print(df["etiqueta_normalizada"].value_counts().to_string())

    # Verificar conteos esperados
    conteos_esperados = {"alto_riesgo": 72, "riesgo_minimo": 39, "riesgo_limitado": 121}
    conteos_nuevos = {}
    for _, etiqueta in NUEVAS_FILAS:
        conteos_nuevos[etiqueta] = conteos_nuevos.get(etiqueta, 0) + 1

    print("\nFilas nuevas por clase:")
    for k, v in conteos_nuevos.items():
        esperado = conteos_esperados.get(k, "?")
        estado = "OK" if v == esperado else f"AVISO: esperado {esperado}"
        print(f"  {k:<22} +{v}  {estado}")

    # Construir filas nuevas
    nuevas = []
    for i, (descripcion, etiqueta) in enumerate(NUEVAS_FILAS):
        import re
        tokens = re.findall(r'\b[a-záéíóúüñ]{3,}\b', descripcion.lower())
        stopwords = {
            'una', 'uno', 'los', 'las', 'del', 'que', 'par', 'con', 'sin', 'por',
            'para', 'como', 'más', 'sus', 'son', 'ser', 'han', 'etc', 'est',
        }
        limpia = " ".join(t for t in tokens if t not in stopwords)

        nuevas.append({
            "ambiguity": None,
            "articles": None,
            "category": None,
            "context": None,
            "descripcion": descripcion,
            "etiqueta": etiqueta,
            "explanation": None,
            "id": None,
            "notas": "añadido_balanceo",
            "sector": None,
            "severity": None,
            "split": "train",
            "tipo_datos": None,
            "violation": None,
            "etiqueta_normalizada": etiqueta,
            "longitud": len(descripcion),
            "descripcion_limpia": limpia,
        })

    df_nuevas = pd.DataFrame(nuevas)
    df_final = pd.concat([df, df_nuevas], ignore_index=True)

    print("\nDistribución DESPUÉS del balanceo:")
    print(df_final["etiqueta_normalizada"].value_counts().to_string())
    OUTPUT_PATH = CSV_PATH.parent / "eu_ai_act_flagged_es_balanceado.csv"
    df_final.to_csv(OUTPUT_PATH, index=False)
    print(f"\nTotal filas: {len(df)} -> {len(df_final)} (+{len(df_final) - len(df)})")
    print(f"\nCSV balanceado guardado en : {OUTPUT_PATH}")
    print(f"CSV original NO modificado : {CSV_PATH}")


if __name__ == "__main__":
    main()
