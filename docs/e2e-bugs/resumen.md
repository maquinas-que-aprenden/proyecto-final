### Bugs detectados en E2E test — 28 febrero 2026

Prueba realizada con 4 queries sobre la imagen develop desplegada. Pipeline E2E
completo funciona en los 3 flujos (RAG, clasificador, informes). Estos son los bugs
encontrados:

###### Bug 1 — Inversión del mapa de riesgo en el generador de

###### informes

Gravedad: CRÍTICA

El report.generate recibe el nivel de riesgo como número (0, 1, 2, 3) pero no recibe la
etiqueta textual. El LLM lo interpreta ordinalmente: 0 = sin riesgo, 3 = máximo riesgo. La
codificación real del proyecto es la inversa: 0 = inaceptable, 3 = mínimo. Resultado: un
sistema de predicción de recidiva para libertad condicional (nivel 0 = inaceptable) recibe un
informe que dice "obligaciones mínimas, sin restricciones significativas".

Fix: Pasar la etiqueta string ("inaceptable", "alto", "limitado", "mínimo") junto al número al
generador de informes. Responsable: Maru.

###### Bug 2 — Query de retrieval para informes usa el número del

###### nivel en vez de la descripción

Gravedad: CRÍTICA

Cuando se genera un informe, el retriever busca artículos relevantes con la query
"obligaciones {número} EU AI Act" (literalmente "obligaciones 0 EU AI Act" o "obligaciones 3
EU AI Act"). Esa query no tiene sentido semántico y recupera documentos casi irrelevantes
(distancias >12 vs ~6 cuando el RAG funciona bien). El LLM entonces alucina
interpretaciones de esos artículos porque el contexto recuperado no corresponde al caso de
uso.

Fix: Construir la query de retrieval con la descripción del sistema y el nivel en texto, por
ejemplo: "obligaciones sistema inaceptable administración de justicia EU AI Act".
Responsable: Maru (orchestrator) o Dani (retriever).

Bug 3 — Clasificador mal calibrado para casos canónicos del EU AI Act

Gravedad: ALTA

El clasificador falla en casos de uso explícitamente listados en el Anexo III del EU AI Act:

CV screening → predice inaceptable (67% confianza) cuando la clasificación correcta es
alto (Anexo III, cat. 4.a)


Scoring crediticio → predice mínimo (70% confianza) cuando la clasificación correcta es alto
(Anexo III, cat. 5.b)
Evaluación de recidiva → predice inaceptable (96% confianza), que es debatible pero el
informe resultante es catastrófico por el Bug 1
El dataset de entrenamiento probablemente no incluye suficientes ejemplos de estos casos
o están mal etiquetados.

Fix: Revisar y aumentar el dataset con ejemplos de los casos del Anexo III. Responsable:
Rubén.

###### Bug 4 — El LLM alucina interpretaciones legales de los

###### artículos recuperados

Gravedad: ALTA (consecuencia parcial del Bug 2)

En los informes, el LLM cita artículos reales pero les atribuye contenido inventado.
Ejemplos:

Art. 8 (cumplimiento de requisitos para sistemas de alto riesgo) → el informe dice "establece
que sistemas sin impacto significativo no están sujetos a regulaciones estrictas"
Art. 54 (representantes autorizados de proveedores de GPAI) → el informe dice "requiere
minimizar sesgos y garantizar precisión"
Art. 89 (medidas de seguimiento de la Oficina de IA) → el informe dice "establece
transparencia y responsabilidad para sistemas de bajo riesgo"
La causa raíz es el Bug 2: como los documentos recuperados no son relevantes, el LLM
rellena con su conocimiento previo y los atribuye a los artículos equivocados. Si el retrieval
mejora (Bug 2 resuelto), este bug debería reducirse significativamente.

Fix: Depende de Bug 2. Adicionalmente, el prompt del generador de informes debería
instruir explícitamente al LLM a no atribuir contenido que no aparezca en el contexto
recuperado. Responsable: Maru (prompt engineering del report).

###### Bug 5 — Error en el cálculo de explicabilidad del clasificador

Gravedad: MEDIA (en progreso)

En todas las queries con clasificación aparece en los logs:

No se pudo calcular explicabilidad: could not convert string to
float: '[-2.3841858E-7,-8.34465E-7,2.3841858E-7,8.34465E-7]'

El pred_contribs de XGBoost devuelve los valores en formato string en lugar de float, o hay
un problema de parseo al procesarlos. El sistema continúa sin explicabilidad pero no corta
el flujo. Este bug está siendo trabajado en el branch fix/cambio-shap.

Fix: En progreso. Responsable: Rubén.


https://github.com/maquinas-que-aprenden/proyecto-final/pull/

###### Prioridad sugerida

Bug 1 → Bug 2 → Bug 4 (mejora sola con Bug 2) → Bug 3 → Bug 5 (ya en curso en
fix/cambio-shap)


### Bugs detectados en E2E test — 1 marzo 2026

Prueba realizada con 5 queries sobre la imagen develop desplegada. Pipeline E2E
completo funciona en los 3 flujos (RAG, clasificador, informes). Estos son los bugs
encontrados:

Bug 1 — El razonamiento interno del orchestrator aparece en el chat
Gravedad: CRÍTICA

El output que ve el usuario contiene literalmente los tags <thinking>...</thinking> con el
razonamiento de Bedrock Nova Lite. Ejemplo real de Q5:

<thinking> La herramienta de búsqueda no ha encontrado documentos relevantes, lo que
sugiere que puede ser necesario proporcionar una descripción más detallada... </thinking>

Además del leak en sí, el texto dentro del <thinking> era factualmente incorrecto (decía que
no encontró documentos cuando el retriever sí recuperó 5). El razonamiento visible nunca
debería llegar al usuario.

Fix: Filtrar el contenido entre <thinking>...</thinking> antes de renderizar la respuesta. 1-
líneas en app.py o en el orchestrator. Responsable: Maru.

Bug 2 — La cita legal del clasificador es incorrecta
Gravedad: CRÍTICA

El clasificador genera correctamente annex3_ref: "Anexo III cat. X" en el output interno, pero
la respuesta al usuario cita EU AI Act, Artículo 52 — un artículo que regula obligaciones de
transparencia para chatbots y deepfakes, sin ninguna relación con la clasificación de riesgo.
La referencia correcta es siempre Art. 6 + la categoría del Anexo III correspondiente.

Este bug es grave para un sistema legal: el producto está citando el artículo equivocado
como fundamento de su clasificación. El dato correcto existe internamente (annex3_ref)
pero se pierde y se reemplaza por una cita incorrecta en algún punto entre el output del
clasificador y la respuesta final.

Fix: Rastrear dónde se pierde annex3_ref y se genera la cita incorrecta — probablemente
en el prompt del orchestrator o del tool de informe. Pasar annex3_ref explícitamente al
generador de respuesta. Responsable: Rubén + Maru.

Bug 3 — Grading inusable en producción: latencias de 8 a 30 minutos
Gravedad: CRÍTICA

Ollama Qwen 2.5 3B corre en CPU (CPU model buffer size = 1834.82 MiB) y evalúa
documentos secuencialmente. Tiempos reales observados:

Query Latencia total Docs gradeados


Q1 (RAG) ~8 min 5
Q4 (RAG + informe) ~30 min 5
Q5 (RAG solo) ~29 min 5
Hay dos causas independientes:

a) n_ctx configurado a 4.096 tokens cuando el modelo soporta 32.768. En Q4 un documento
AESIA llegó a 20.837 tokens, se truncó con keep=4 tokens del prompt original, y Ollama
tardó 17 minutos procesando contexto roto. El modelo no produce resultados fiables con un
contexto así de truncado.

b) Grading secuencial. Cada documento se envía a Ollama en serie. Sin GPU, las opciones
son: procesar en paralelo con asyncio, reducir k de retrieval de 5 a 3, o filtrar por threshold
de distancia semántica antes de enviar a gradear (si el documento está muy lejos
semánticamente, descartarlo sin llamar a Ollama).

Fix: Aumentar n_ctx en la config de Ollama a 8192 mínimo (o limitar tamaño de chunk al
indexar para que ningún doc supere el límite). Paralelizar las llamadas de grading.
Responsable: Nati (config Ollama/Docker) + Dani (tamaño de chunks).

Bug 4 — La explicación SHAP contradice la clasificación final
Gravedad: ALTA

Cuando el clasificador hace override (inaceptable → alto_riesgo), la clasificación final es
correcta pero el texto de explicación que ve el usuario dice:

"Los factores principales para 'inaceptable': num_palabras, svd_24, svd_30"

El usuario recibe dos mensajes contradictorios: "tu sistema es de alto riesgo" + "los factores
de inaceptable son...". La explicación SHAP describe la predicción ML que fue descartada
por el override, no la clasificación final.

Fix: Cuando se aplica un override de Anexo III, actualizar el texto de explicación para que
referencie la clasificación final y el artículo del Anexo III que la justifica, en lugar de los
factores SHAP de la predicción descartada. Responsable: Rubén.

Bug 5 — El orchestrator genera queries de retrieval en inglés
Gravedad: ALTA

En Q5, Bedrock Nova Lite construyó la query de búsqueda en inglés:

"EU AI Act articles applicable to AI systems that evaluate recidivism risk for parole
recommendation"

El corpus está en español. Las distancias semánticas resultantes fueron 14+ en lugar del
rango habitual de 7-9 cuando la query es en español. El grading posterior filtró los 5
documentos recuperados como no relevantes (0/5 pasaron), y el sistema respondió
pidiendo más información al usuario — después de 29 minutos de espera.


Fix: Añadir instrucción explícita en el prompt del orchestrator para generar queries de
retrieval en español. Responsable: Maru.

Bug 6 — El orchestrator invoca el clasificador dos veces
Gravedad: MEDIA

En Q3, Langfuse registra dos spans classifier.predict_risk con el mismo input, separados
1.15 segundos, con IDs distintos — dos llamadas reales. El orchestrator hace dos turnos
ReAct: en el primero llama al tool clasificador directamente; en el segundo llama al tool
informe, que internamente vuelve a ejecutar el clasificador. La primera llamada es
redundante.

Fix: El orchestrator debería pasar el resultado de clasificación del turno 1 al tool de informe
como parámetro, o el tool de informe debería aceptar una clasificación precomputada en
lugar de repetirla. Responsable: Maru.

Bug 7 — Features SHAP técnicas expuestas al usuario como justificación
Gravedad: MEDIA

La explicación de clasificación muestra al usuario los nombres internos de las features del
modelo: num_palabras, svd_24, svd_30. Estos son componentes SVD de TF-IDF sin ningún
significado semántico para un usuario final — y por construcción, los svd_N no tienen
interpretación individual posible. Además, que num_palabras sea la feature con mayor
contribución SHAP (~1.0) en múltiples queries sugiere que el modelo está capturando
longitud del texto, no características relevantes al dominio legal.

Fix: Reemplazar la explicación SHAP técnica por la referencia al Anexo III y la categoría
legal que activó la clasificación, que es la justificación real y comprensible para el usuario.
Responsable: Rubén.

Prioridad sugerida

Bug 1 → Bug 2 → Bug 3 → Bug 4 → Bug 5 → Bug 6 → Bug 7


##### Bugs E2E — Lista priorizada (2026-03-02)

🔴 **P0 — Corregir antes de la demo**

**BUG-01 — Clasificador: annex3_override devuelve campos contradictorios**

```
● Síntoma : risk_level: "alto_riesgo" pero probabilities: {inaceptable: 0.99} y
shap_explanation: "Factores principales para 'inaceptable'". Los campos
auxiliares no se actualizan cuando el override cambia la clase final.
● Impacto : Aparece en Q2, Q3 y Q4. Si un evaluador mira los logs de Langfuse o pregunta "¿por
qué alto_riesgo si la probabilidad de inaceptable es 99%?", no hay respuesta coherente.
● Responsable : Rubén
● Fichero : src/classifier/main.py — lógica de annex3_override
● Fix : Cuando annex3_override=True, recalibrar probabilities a la clase final y actualizar
shap_explanation para referenciar risk_level en lugar de ml_prediction.risk_level.
```
**BUG-02 — Latencia RAG: grading Ollama bloquea 4-6 minutos por query**

```
● Síntoma : Cada doc tarda 33-120s en ser evaluado por Qwen 2.5 3B en CPU. Con k=5, el total
es 4-6 minutos. En Q1 fueron 228s, en Q4 (del run anterior) ~5:58min.
● Impacto : Cualquier query que active search_legal_docs bloquea la UI más de 4 minutos.
Inaceptable en demo en vivo.
● Responsable : Dani
● Fichero : src/rag/main.py — grade()
● Fix opciones (de menor a mayor esfuerzo):
○ Opción A (15 min): reducir k de 5 a 2 en search_legal_docs. Ahorra ~2-3 min.
○ Opción B (1h): usar solo score threshold como fallback (ya existe el código),
deshabilitar grading LLM en producción con un flag de env.
○ Opción C (2h): pre-calentar Ollama antes de la demo y reducir k a 2.
```
🟡 **P1 — Corregir esta semana**

**BUG-03 — generate_report recupera solo Art. 47, informe incompleto**

```
● Síntoma : La query "obligaciones sistemas de riesgo alto_riesgo EU AI Act" con
k=3 devuelve siempre Art. 47 + 2 guías AESIA. Los informes de Q3 y Q4 cubren solo una
obligación cuando deberían cubrir 6-7 artículos.
● Impacto : El informe de cumplimiento parece superficial. Un evaluador que conozca el EU AI
Act notará que faltan Art. 9, 13, 14, 15.
● Responsable : Maru
● Fichero : src/orchestrator/main.py — tool generate_report
● Fix : Aumentar k a 5 y hacer la query más específica, por ejemplo "requisitos
obligaciones proveedor sistema IA alto riesgo artículos EU AI Act".
```
**BUG-04 — Double-call al clasificador (PR #90 no deployado o incompleto)**


```
● Síntoma : En queries con generate_report, el clasificador se invoca dos veces con el mismo
input (una desde classify_risk y otra internamente desde generate_report). Confirmado
en Q3.
● Impacto : Procesamiento duplicado. Bajo impacto en latencia (~30ms extra) pero indica que
el fix del PR #90 no llegó a la imagen develop.
● Responsable : Maru + Nati
● Fix : Verificar si el PR #90 está mergeado en develop y si la imagen se rebuildeó después. Si
no, forzar rebuild.
```
**BUG-05 — grade() filtra docs relevantes (demasiado restrictivo)**

```
● Síntoma : En Q1, de 5 docs recuperados solo pasó 1 (Art. 25). El Art. 26 — "Obligaciones de
los responsables del despliegue" — fue rechazado pese a ser directamente relevante. El
contexto de generate() quedó empobrecido.
● Impacto : Respuestas incompletas en queries RAG. La respuesta de Q1 ignoró Art. 26.
● Responsable : Dani
● Fichero : src/rag/main.py — grade()
● Fix : Revisar el prompt de grading — puede estar siendo demasiado literal. Alternativamente,
bajar el threshold de score fallback.
```
🔵 **P2 — Si queda tiempo**

**BUG-06 — Sin logging de aplicación en docker (queries sin Ollama silenciosas)**

```
● Síntoma : En Q2 y Q3 (sin Ollama), docker logs está vacío. Solo aparece el output verbose de
Ollama. Si Bedrock o el clasificador fallan en producción, no hay evidencia en logs.
● Impacto : Dificulta diagnóstico en vivo durante la demo si algo falla.
● Responsable : Nati
● Fix : Añadir logging.basicConfig con nivel INFO en app.py o en el punto de entrada,
asegurando que los logs van a stdout.
```
**BUG-07 — Langfuse trazas llegan con delay visible**

```
● Síntoma : Las trazas en Langfuse no aparecen en tiempo real — hay un delay perceptible
respecto a la respuesta en la UI.
● Impacto : Si se muestra Langfuse durante la demo en vivo, el evaluador puede ver trazas
vacías o incompletas.
● Responsable : Nati
● Mitigación demo (sin código): Mostrar Langfuse siempre referenciando la query anterior, no
la actual. Presentarlo como "aquí vemos la traza de la query que acabamos de hacer"
después de que llegue.
```
**Resumen por persona**

```
Responsable Bugs Prioridad
Rubén BUG-01 (annex3_override) P
```

**Dani** BUG-02 (latencia Ollama), BUG-05 (grade restrictivo) P0, P

**Maru** BUG-03 (k=3 informe incompleto), BUG-04 (double-call) P1, P

**Nati** BUG-04 (verificar deploy), BUG-06 (logging), BUG-07 (Langfuse demo) P1, P2,
P


### Query 1

###### Input en chat UI

¿Qué obligaciones tiene un sistema de IA de alto riesgo según el EU AI Act?

###### Salida en chat UI

Obligaciones para sistemas de IA de alto riesgo según el EU AI Act

Según el EU AI Act, las obligaciones para los sistemas de IA de alto riesgo se establecen en
el Artículo 25. Los proveedores de sistemas de IA de alto riesgo, incluyendo distribuidores,
importadores, responsables del despliegue o terceros como proveedores, tienen las
siguientes obligaciones específicas:

1. Marca o Nombre en Sistemas de IA de Alto Riesgo:
    ○ Cuando colocan su nombre o marca en un sistema de IA de alto riesgo
       que ya ha sido introducido en el mercado o puesto en servicio, serán
       considerados proveedores y estarán sujetos a las obligaciones del
       proveedor (Artículo 25(1)(a)).
2. Modificación Sustancial de Sistemas de IA de Alto Riesgo:
    ○ Cuando modifican sustancialmente un sistema de IA de alto riesgo que
       ya ha sido introducido en el mercado o puesto en servicio, de tal
       manera que siga siendo un sistema de IA de alto riesgo de conformidad
       con el artículo 6, también serán considerados proveedores y deberán
       cumplir con las obligaciones del proveedor (Artículo 25(1)(b)).
3. Modificación de Finalidad de Sistemas de IA:
    ○ Cuando modifican la finalidad prevista de un sistema de IA, incluso un
       sistema de IA de uso general que no haya sido considerado de alto
       riesgo y ya haya sido introducido en el mercado o puesto en servicio, de
       tal manera que el sistema se convierte en un sistema de IA de alto
       riesgo de conformidad con el artículo 6, también serán considerados
       proveedores y deberán cumplir con las obligaciones del proveedor
       (Artículo 25(1)(c)).

Las obligaciones mencionadas implican que los proveedores deben cumplir con las
exigencias establecidas en el artículo 16 del EU AI Act, que incluyen:

```
● Evaluación de la conformidad.
● Documentación.
● Supervisión del mercado.
● Garantía de que los sistemas de IA de alto riesgo cumplen con los requisitos de
seguridad y robustez establecidos en la normativa.
```
Fuentes:


```
● EU AI Act, Artículo 25.
```
_Informe preliminar generado por IA. Consulte profesional jurídico._

###### Salida en docker logs

time=2026-03-02T09:35:39.374Z level=WARN source=cpu_linux.go:130 msg="failed to
parse CPU allowed micro secs" error="strconv.ParseInt: parsing \"max\": invalid syntax"
llama_model_loader: loaded meta data with 35 key-value pairs and 434 tensors from
/home/appuser/.ollama/models/blobs/sha256-5ee4f07cdb9beadbbb293e85803c569b01bd
ed059d2715faa7bb405f31caa6 (version GGUF V3 (latest))
llama_model_loader: Dumping metadata keys/values. Note: KV overrides do not apply in
this output.
llama_model_loader: - kv 0: general.architecture str = qwen
llama_model_loader: - kv 1: general.type str = model
llama_model_loader: - kv 2: general.name str = Qwen2.5 3B
Instruct
llama_model_loader: - kv 3: general.finetune str = Instruct
llama_model_loader: - kv 4: general.basename str = Qwen2.
llama_model_loader: - kv 5: general.size_label str = 3B
llama_model_loader: - kv 6: general.license str = other
llama_model_loader: - kv 7: general.license.name str =
qwen-research
llama_model_loader: - kv 8: general.license.link str =
https://huggingface.co/Qwen/Qwen2.5-3...
llama_model_loader: - kv 9: general.base_model.count u32 = 1
llama_model_loader: - kv 10: general.base_model.0.name str = Qwen2.
3B
llama_model_loader: - kv 11: general.base_model.0.organization str = Qwen
llama_model_loader: - kv 12: general.base_model.0.repo_url str =
https://huggingface.co/Qwen/Qwen2.5-3B
llama_model_loader: - kv 13: general.tags arr[str,2] = ["chat",
"text-generation"]
llama_model_loader: - kv 14: general.languages arr[str,1] = ["en"]
llama_model_loader: - kv 15: qwen2.block_count u32 = 36
llama_model_loader: - kv 16: qwen2.context_length u32 = 32768
llama_model_loader: - kv 17: qwen2.embedding_length u32 = 2048
llama_model_loader: - kv 18: qwen2.feed_forward_length u32 = 11008
llama_model_loader: - kv 19: qwen2.attention.head_count u32 = 16
llama_model_loader: - kv 20: qwen2.attention.head_count_kv u32 = 2
llama_model_loader: - kv 21: qwen2.rope.freq_base f32 =
1000000.
llama_model_loader: - kv 22: qwen2.attention.layer_norm_rms_epsilon f32 =
0.
llama_model_loader: - kv 23: general.file_type u32 = 15
llama_model_loader: - kv 24: tokenizer.ggml.model str = gpt
llama_model_loader: - kv 25: tokenizer.ggml.pre str = qwen


llama_model_loader: - kv 26: tokenizer.ggml.tokens arr[str,151936] = ["!", "\"",
"#", "$", "%", "&", "'", ...
llama_model_loader: - kv 27: tokenizer.ggml.token_type arr[i32,151936] = [1, 1,
1, 1, 1, 1, 1, 1, 1, 1, 1, 1, ...
llama_model_loader: - kv 28: tokenizer.ggml.merges arr[str,151387] = ["Ġ Ġ",
"ĠĠ ĠĠ", "i n", "Ġ t",...
llama_model_loader: - kv 29: tokenizer.ggml.eos_token_id u32 = 151645
llama_model_loader: - kv 30: tokenizer.ggml.padding_token_id u32 =
151643
llama_model_loader: - kv 31: tokenizer.ggml.bos_token_id u32 = 151643
llama_model_loader: - kv 32: tokenizer.ggml.add_bos_token bool = false
llama_model_loader: - kv 33: tokenizer.chat_template str = {%- if tools
%}\n {{- '<|im_start|>...
llama_model_loader: - kv 34: general.quantization_version u32 = 2
llama_model_loader: - type f32: 181 tensors
llama_model_loader: - type q4_K: 216 tensors
llama_model_loader: - type q6_K: 37 tensors
print_info: file format = GGUF V3 (latest)
print_info: file type = Q4_K - Medium
print_info: file size = 1.79 GiB (4.99 BPW)
load: printing all EOG tokens:
load: - 151643 ('<|endoftext|>')
load: - 151645 ('<|im_end|>')
load: - 151662 ('<|fim_pad|>')
load: - 151663 ('<|repo_name|>')
load: - 151664 ('<|file_sep|>')
load: special tokens cache size = 22
load: token to piece cache size = 0.9310 MB
print_info: arch = qwen
print_info: vocab_only = 1
print_info: no_alloc = 0
print_info: model type = ?B
print_info: model params = 3.09 B
print_info: general.name = Qwen2.5 3B Instruct
print_info: vocab type = BPE
print_info: n_vocab = 151936
print_info: n_merges = 151387
print_info: BOS token = 151643 '<|endoftext|>'
print_info: EOS token = 151645 '<|im_end|>'
print_info: EOT token = 151645 '<|im_end|>'
print_info: PAD token = 151643 '<|endoftext|>'
print_info: LF token = 198 'Ċ'
print_info: FIM PRE token = 151659 '<|fim_prefix|>'
print_info: FIM SUF token = 151661 '<|fim_suffix|>'
print_info: FIM MID token = 151660 '<|fim_middle|>'
print_info: FIM PAD token = 151662 '<|fim_pad|>'
print_info: FIM REP token = 151663 '<|repo_name|>'
print_info: FIM SEP token = 151664 '<|file_sep|>'


print_info: EOG token = 151643 '<|endoftext|>'
print_info: EOG token = 151645 '<|im_end|>'
print_info: EOG token = 151662 '<|fim_pad|>'
print_info: EOG token = 151663 '<|repo_name|>'
print_info: EOG token = 151664 '<|file_sep|>'
print_info: max token length = 256
llama_model_load: vocab only - skipping tensors
time=2026-03-02T09:35:39.829Z level=INFO source=server.go:431 msg="starting runner"
cmd="/usr/local/bin/ollama runner --model
/home/appuser/.ollama/models/blobs/sha256-5ee4f07cdb9beadbbb293e85803c569b01bd
ed059d2715faa7bb405f31caa6 --port 46079"
time=2026-03-02T09:35:39.831Z level=INFO source=sched.go:491 msg="system memory"
total="7.6 GiB" free="4.4 GiB" free_swap="0 B"
time=2026-03-02T09:35:39.831Z level=INFO source=server.go:498 msg="loading model"
"model layers"=37 requested=-
time=2026-03-02T09:35:39.832Z level=INFO source=device.go:245 msg="model weights"
device=CPU size="1.8 GiB"
time=2026-03-02T09:35:39.832Z level=INFO source=device.go:256 msg="kv cache"
device=CPU size="144.0 MiB"
time=2026-03-02T09:35:39.832Z level=INFO source=device.go:272 msg="total memory"
size="1.9 GiB"
time=2026-03-02T09:35:39.850Z level=INFO source=runner.go:965 msg="starting go
runner"
load_backend: loaded CPU backend from /usr/local/lib/ollama/libggml-cpu-skylakex.so
time=2026-03-02T09:35:39.863Z level=INFO source=ggml.go:104 msg=system
CPU.0.SSE3=1 CPU.0.SSSE3=1 CPU.0.AVX=1 CPU.0.AVX2=1 CPU.0.F16C=
CPU.0.FMA=1 CPU.0.BMI2=1 CPU.0.AVX512=1 CPU.0.LLAMAFILE=
CPU.1.LLAMAFILE=1 compiler=cgo(gcc)
time=2026-03-02T09:35:39.864Z level=INFO source=runner.go:1001 msg="Server listening
on 127.0.0.1:46079"
time=2026-03-02T09:35:39.866Z level=INFO source=runner.go:895 msg=load
request="{Operation:commit LoraPath:[] Parallel:1 BatchSize:512 FlashAttention:Auto
KvSize:4096 KvCacheType: NumThreads:1 GPULayers:[] MultiUserCache:false
ProjectorPath: MainGPU:0 UseMmap:false}"
time=2026-03-02T09:35:39.868Z level=INFO source=server.go:1350 msg="waiting for llama
runner to start responding"
time=2026-03-02T09:35:39.868Z level=INFO source=server.go:1384 msg="waiting for
server to become available" status="llm server loading model"
llama_model_loader: loaded meta data with 35 key-value pairs and 434 tensors from
/home/appuser/.ollama/models/blobs/sha256-5ee4f07cdb9beadbbb293e85803c569b01bd
ed059d2715faa7bb405f31caa6 (version GGUF V3 (latest))
llama_model_loader: Dumping metadata keys/values. Note: KV overrides do not apply in
this output.
llama_model_loader: - kv 0: general.architecture str = qwen
llama_model_loader: - kv 1: general.type str = model
llama_model_loader: - kv 2: general.name str = Qwen2.5 3B
Instruct
llama_model_loader: - kv 3: general.finetune str = Instruct


llama_model_loader: - kv 4: general.basename str = Qwen2.
llama_model_loader: - kv 5: general.size_label str = 3B
llama_model_loader: - kv 6: general.license str = other
llama_model_loader: - kv 7: general.license.name str =
qwen-research
llama_model_loader: - kv 8: general.license.link str =
https://huggingface.co/Qwen/Qwen2.5-3...
llama_model_loader: - kv 9: general.base_model.count u32 = 1
llama_model_loader: - kv 10: general.base_model.0.name str = Qwen2.
3B
llama_model_loader: - kv 11: general.base_model.0.organization str = Qwen
llama_model_loader: - kv 12: general.base_model.0.repo_url str =
https://huggingface.co/Qwen/Qwen2.5-3B
llama_model_loader: - kv 13: general.tags arr[str,2] = ["chat",
"text-generation"]
llama_model_loader: - kv 14: general.languages arr[str,1] = ["en"]
llama_model_loader: - kv 15: qwen2.block_count u32 = 36
llama_model_loader: - kv 16: qwen2.context_length u32 = 32768
llama_model_loader: - kv 17: qwen2.embedding_length u32 = 2048
llama_model_loader: - kv 18: qwen2.feed_forward_length u32 = 11008
llama_model_loader: - kv 19: qwen2.attention.head_count u32 = 16
llama_model_loader: - kv 20: qwen2.attention.head_count_kv u32 = 2
llama_model_loader: - kv 21: qwen2.rope.freq_base f32 =
1000000.
llama_model_loader: - kv 22: qwen2.attention.layer_norm_rms_epsilon f32 =
0.
llama_model_loader: - kv 23: general.file_type u32 = 15
llama_model_loader: - kv 24: tokenizer.ggml.model str = gpt
llama_model_loader: - kv 25: tokenizer.ggml.pre str = qwen
llama_model_loader: - kv 26: tokenizer.ggml.tokens arr[str,151936] = ["!", "\"",
"#", "$", "%", "&", "'", ...
llama_model_loader: - kv 27: tokenizer.ggml.token_type arr[i32,151936] = [1, 1,
1, 1, 1, 1, 1, 1, 1, 1, 1, 1, ...
llama_model_loader: - kv 28: tokenizer.ggml.merges arr[str,151387] = ["Ġ Ġ",
"ĠĠ ĠĠ", "i n", "Ġ t",...
llama_model_loader: - kv 29: tokenizer.ggml.eos_token_id u32 = 151645
llama_model_loader: - kv 30: tokenizer.ggml.padding_token_id u32 =
151643
llama_model_loader: - kv 31: tokenizer.ggml.bos_token_id u32 = 151643
llama_model_loader: - kv 32: tokenizer.ggml.add_bos_token bool = false
llama_model_loader: - kv 33: tokenizer.chat_template str = {%- if tools
%}\n {{- '<|im_start|>...
llama_model_loader: - kv 34: general.quantization_version u32 = 2
llama_model_loader: - type f32: 181 tensors
llama_model_loader: - type q4_K: 216 tensors
llama_model_loader: - type q6_K: 37 tensors
print_info: file format = GGUF V3 (latest)
print_info: file type = Q4_K - Medium


print_info: file size = 1.79 GiB (4.99 BPW)
load: printing all EOG tokens:
load: - 151643 ('<|endoftext|>')
load: - 151645 ('<|im_end|>')
load: - 151662 ('<|fim_pad|>')
load: - 151663 ('<|repo_name|>')
load: - 151664 ('<|file_sep|>')
load: special tokens cache size = 22
load: token to piece cache size = 0.9310 MB
print_info: arch = qwen
print_info: vocab_only = 0
print_info: no_alloc = 0
print_info: n_ctx_train = 32768
print_info: n_embd = 2048
print_info: n_embd_inp = 2048
print_info: n_layer = 36
print_info: n_head = 16
print_info: n_head_kv = 2
print_info: n_rot = 128
print_info: n_swa = 0
print_info: is_swa_any = 0
print_info: n_embd_head_k = 128
print_info: n_embd_head_v = 128
print_info: n_gqa = 8
print_info: n_embd_k_gqa = 256
print_info: n_embd_v_gqa = 256
print_info: f_norm_eps = 0.0e+
print_info: f_norm_rms_eps = 1.0e-
print_info: f_clamp_kqv = 0.0e+
print_info: f_max_alibi_bias = 0.0e+
print_info: f_logit_scale = 0.0e+
print_info: f_attn_scale = 0.0e+
print_info: n_ff = 11008
print_info: n_expert = 0
print_info: n_expert_used = 0
print_info: n_expert_groups = 0
print_info: n_group_used = 0
print_info: causal attn = 1
print_info: pooling type = -
print_info: rope type = 2
print_info: rope scaling = linear
print_info: freq_base_train = 1000000.
print_info: freq_scale_train = 1
print_info: n_ctx_orig_yarn = 32768
print_info: rope_yarn_log_mul= 0.
print_info: rope_finetuned = unknown
print_info: model type = 3B
print_info: model params = 3.09 B


print_info: general.name = Qwen2.5 3B Instruct
print_info: vocab type = BPE
print_info: n_vocab = 151936
print_info: n_merges = 151387
print_info: BOS token = 151643 '<|endoftext|>'
print_info: EOS token = 151645 '<|im_end|>'
print_info: EOT token = 151645 '<|im_end|>'
print_info: PAD token = 151643 '<|endoftext|>'
print_info: LF token = 198 'Ċ'
print_info: FIM PRE token = 151659 '<|fim_prefix|>'
print_info: FIM SUF token = 151661 '<|fim_suffix|>'
print_info: FIM MID token = 151660 '<|fim_middle|>'
print_info: FIM PAD token = 151662 '<|fim_pad|>'
print_info: FIM REP token = 151663 '<|repo_name|>'
print_info: FIM SEP token = 151664 '<|file_sep|>'
print_info: EOG token = 151643 '<|endoftext|>'
print_info: EOG token = 151645 '<|im_end|>'
print_info: EOG token = 151662 '<|fim_pad|>'
print_info: EOG token = 151663 '<|repo_name|>'
print_info: EOG token = 151664 '<|file_sep|>'
print_info: max token length = 256
load_tensors: loading model tensors, this can take a while... (mmap = false)
load_tensors: CPU model buffer size = 1834.82 MiB
llama_context: constructing llama_context
llama_context: n_seq_max = 1
llama_context: n_ctx = 4096
llama_context: n_ctx_seq = 4096
llama_context: n_batch = 512
llama_context: n_ubatch = 512
llama_context: causal_attn = 1
llama_context: flash_attn = auto
llama_context: kv_unified = false
llama_context: freq_base = 1000000.
llama_context: freq_scale = 1
llama_context: n_ctx_seq (4096) < n_ctx_train (32768) -- the full capacity of the model will
not be utilized
llama_context: CPU output buffer size = 0.59 MiB
llama_kv_cache: CPU KV buffer size = 144.00 MiB
llama_kv_cache: size = 144.00 MiB ( 4096 cells, 36 layers, 1/1 seqs), K (f16): 72.00 MiB,
V (f16): 72.00 MiB
llama_context: Flash Attention was auto, set to enabled
llama_context: CPU compute buffer size = 304.75 MiB
llama_context: graph nodes = 1231
llama_context: graph splits = 1
time=2026-03-02T09:35:52.921Z level=INFO source=server.go:1388 msg="llama runner
started in 13.09 seconds"
time=2026-03-02T09:35:52.922Z level=INFO source=sched.go:566 msg="loaded runners"
count=


time=2026-03-02T09:35:52.922Z level=INFO source=server.go:1350 msg="waiting for llama
runner to start responding"
time=2026-03-02T09:35:52.922Z level=INFO source=server.go:1388 msg="llama runner
started in 13.09 seconds"
[GIN] 2026/03/02 - 09:36:12 | 200 | 33.286959904s | 127.0.0.1 | POST "/api/chat"
[GIN] 2026/03/02 - 09:37:12 | 200 | 59.965590376s | 127.0.0.1 | POST
"/api/chat"
[GIN] 2026/03/02 - 09:38:14 | 200 | 1m2s | 127.0.0.1 | POST "/api/chat"
[GIN] 2026/03/02 - 09:38:25 | 200 | 10.572157108s | 127.0.0.1 | POST "/api/chat"
[GIN] 2026/03/02 - 09:39:29 | 200 | 1m3s | 127.0.0.1 | POST "/api/chat"

###### Logs de langfuse en JSON

[
{
"id": "df87a50d-15e7-4b17-971b-3aee00645bd9",
"type": "SPAN",
"name": "rag.retrieve (df87a50d)",
"startTime": "2026-03-02T09:35:22.923Z",
"endTime": "2026-03-02T09:35:39.188Z",
"depth": 0,
"input": "{\"args\":[\"Obligaciones para sistemas de IA de alto riesgo según el EU AI
Act\"],\"kwargs\":{}}",
"output": "[{\"doc\":\"Obligaciones de los proveedores y responsables del despliegue de
sistemas de IA de alto riesgo y de otras
partes\",\"metadata\":{\"unit_id\":\"3\",\"doc_date\":\"13 junio 2024\",\"unit_title\":\"SECCIÓN
3\",\"source\":\"eu_ai_act\",\"id\":\"1927ec2cec85c21d989d73a8d932b5c0\",\"unit_type\":\"se
ction\",\"file\":\"EU_AI_Act_2024_1689_ES.html\",\"sub_index\":0,\"unit_index\":20,\"doc_title\
":\"L_202401689ES.000101.fmx.xml\"},\"score\":0.7854188084602356},{\"doc\":\"Obligacione
s de los responsables del despliegue de sistemas de IA de alto riesgo\\n1. Los
responsables del despliegue de sistemas de IA de alto riesgo adoptarán medidas técnicas y
organizativas adecuadas para garantizar que utilizan dichos sistemas con arreglo a las
instrucciones de uso que los acompañen, de acuerdo con los apartados 3 y 6.\\n2. Los
responsables del despliegue encomendarán la supervisión humana a personas físicas que
tengan la competencia, la formación y la autoridad necesarias.\\n3. Las obligaciones
previstas en los apartados 1 y 2 no afectan a otras obligaciones que el Derecho nacional o
de la Unión imponga a los responsables del despliegue ni a su libertad para organizar sus
propios recursos y actividades con el fin de poner en práctica las medidas de supervisión
humana que indique el proveedor.\\n4. Sin perjuicio de lo dispuesto en los apartados 1 y 2,
el responsable del despliegue se asegurará de que los datos de entrada sean pertinentes y
suficientemente representativos en vista de la finalidad prevista del sistema de IA de alto
riesgo, en la medida en que ejerza el control sobre dichos
datos.\",\"metadata\":{\"unit_index\":31,\"unit_id\":\"26\",\"file\":\"EU_AI_Act_2024_1689_ES.h
tml\",\"unit_type\":\"article\",\"doc_date\":\"13 junio
2024\",\"sub_index\":0,\"doc_title\":\"L_202401689ES.000101.fmx.xml\",\"source\":\"eu_ai_ac
t\",\"unit_title\":\"Artículo
26\",\"id\":\"6894451b30952f00cc47f204c382d6eb\"},\"score\":0.785405695438385},{\"doc\":\
"Responsabilidades a lo largo de la cadena de valor de la IA\\n1. Cualquier distribuidor,


importador, responsable del despliegue o tercero será considerado proveedor de un sistema
de IA de alto riesgo a los efectos del presente Reglamento y estará sujeto a las obligaciones
del proveedor previstas en el artículo 16 en cualquiera de las siguientes
circunstancias:\\na)\\ncuando ponga su nombre o marca en un sistema de IA de alto riesgo
previamente introducido en el mercado o puesto en servicio, sin perjuicio de los acuerdos
contractuales que estipulen que las obligaciones se asignan de otro modo;\\nb)\\ncuando
modifique sustancialmente un sistema de IA de alto riesgo que ya haya sido introducido en
el mercado o puesto en servicio de tal manera que siga siendo un sistema de IA de alto
riesgo con arreglo al artículo 6;\\nc)\\ncuando modifique la finalidad prevista de un sistema
de IA, incluido un sistema de IA de uso general, que no haya sido considerado de alto
riesgo y ya haya sido introducido en el mercado o puesto en servicio, de tal manera que el
sistema de IA de que se trate se convierta en un sistema de IA de alto riesgo de
conformidad con el artículo
6.\",\"metadata\":{\"unit_type\":\"article\",\"source\":\"eu_ai_act\",\"sub_index\":0,\"file\":\"EU_A
I_Act_2024_1689_ES.html\",\"doc_title\":\"L_202401689ES.000101.fmx.xml\",\"doc_date\":\"
13 junio 2024\",\"unit_title\":\"Artículo
25\",\"unit_id\":\"25\",\"unit_index\":30,\"id\":\"8d84e19594df27c6cca8e9961aac43a6\"},\"scor
e\":0.7748615741729736},{\"doc\":\"Obligaciones de los proveedores de modelos de IA de
uso general con riesgo sistémico\",\"metadata\":{\"doc_date\":\"13 junio
2024\",\"unit_title\":\"SECCIÓN
3\",\"unit_id\":\"3\",\"unit_type\":\"section\",\"sub_index\":0,\"file\":\"EU_AI_Act_2024_1689_E
S.html\",\"source\":\"eu_ai_act\",\"doc_title\":\"L_202401689ES.000101.fmx.xml\",\"unit_index
\":66,\"id\":\"b99e0d02811935240ce38d51196bdd7f\"},\"score\":0.7721918225288391},{\"doc\
":\"por parte del proveedor, si este proporciona al responsable del despliegue el\\nsistema
de IA como un MLSaaS ( Machine Learning as a Service ) u otras formas
de\\ncomercialización y puesta en marcha que impliquen una instalación automática por\\nel
responsable del despliegue donde no haya configuración del sistema.\\n● Si el sistema de
IA va a ser entregado al responsable del despliegue en un formato\\non-premise o in-cloud,
gestionado por el responsable del despliegue, el proveedor\\ndebe proporcionar unas
instrucciones adecuadas para realizar la protección del\\nsistema especialmente durante el
tiempo de inferencia del sistema de IA en\\nproducción. El proceso de instalación del
sistema de IA debe contar con\\nmecanismos que garanticen que la instalación tenga en
cuenta las instrucciones de\\nmanera obligatoria, bien a través de pr ocedimientos de script
automáticos o semi\\nautomáticos, la obligación de disponer de las instrucciones abiertas
para el proceso\\nantes de continuar, la solicitud explicita de la lectura de estas o la
referencia a la\\nlectura especifica a conocer para cada paso del proceso.\\n● Las
actualizaciones del sistema de inteligencia artificial de alto riesgo deben de ser\\ntratadas
con todas las medidas aplicables descritas en esta guía.\\nComo complemento a estas
medidas organizativas, el proveedor deberá alinear las\\nsiguientes medidas
técnicas:\",\"metadata\":{\"unit_title\":\"4.1.1 Medidas
aplicables\",\"file\":\"11-guia-ciberseguridad.pdf\",\"unit_id\":\"4.1.1\",\"doc_date\":\"
diciembre
2025\",\"sub_index\":2,\"id\":\"62018f0d02a5fb86c271b25dc9bc6365\",\"source\":\"aesia\",\"d
oc_title\":\"Empresas desarrollando cumplimiento de
requisitos\",\"unit_index\":43,\"unit_type\":\"subsection\"},\"score\":0.780783161520958}]",
"metadata": "{\"k\":5,\"n_docs_retrieved\":5}"
},
{


"id": "b2e78408-26e8-40c2-82fd-319166b6b714",
"type": "SPAN",
"name": "retriever.search (b2e78408)",
"startTime": "2026-03-02T09:35:22.924Z",
"endTime": "2026-03-02T09:35:39.187Z",
"depth": 1,
"input": "{\"args\":[\"Obligaciones para sistemas de IA de alto riesgo según el EU AI
Act\"],\"kwargs\":{\"k\":5,\"mode\":\"soft\"}}",
"output": "[{\"id\":\"1927ec2cec85c21d989d73a8d932b5c0\",\"text\":\"Obligaciones de los
proveedores y responsables del despliegue de sistemas de IA de alto riesgo y de otras
partes\",\"metadata\":{\"unit_id\":\"3\",\"doc_date\":\"13 junio 2024\",\"unit_title\":\"SECCIÓN
3\",\"source\":\"eu_ai_act\",\"id\":\"1927ec2cec85c21d989d73a8d932b5c0\",\"unit_type\":\"se
ction\",\"file\":\"EU_AI_Act_2024_1689_ES.html\",\"sub_index\":0,\"unit_index\":20,\"doc_title\
":\"L_202401689ES.000101.fmx.xml\"},\"distance\":0.2145811915397644},{\"id\":\"6894451b
30952f00cc47f204c382d6eb\",\"text\":\"Obligaciones de los responsables del despliegue de
sistemas de IA de alto riesgo\\n1. Los responsables del despliegue de sistemas de IA de
alto riesgo adoptarán medidas técnicas y organizativas adecuadas para garantizar que
utilizan dichos sistemas con arreglo a las instrucciones de uso que los acompañen, de
acuerdo con los apartados 3 y 6.\\n2. Los responsables del despliegue encomendarán la
supervisión humana a personas físicas que tengan la competencia, la formación y la
autoridad necesarias.\\n3. Las obligaciones previstas en los apartados 1 y 2 no afectan a
otras obligaciones que el Derecho nacional o de la Unión imponga a los responsables del
despliegue ni a su libertad para organizar sus propios recursos y actividades con el fin de
poner en práctica las medidas de supervisión humana que indique el proveedor.\\n4. Sin
perjuicio de lo dispuesto en los apartados 1 y 2, el responsable del despliegue se asegurará
de que los datos de entrada sean pertinentes y suficientemente representativos en vista de
la finalidad prevista del sistema de IA de alto riesgo, en la medida en que ejerza el control
sobre dichos
datos.\",\"metadata\":{\"unit_index\":31,\"unit_id\":\"26\",\"file\":\"EU_AI_Act_2024_1689_ES.h
tml\",\"unit_type\":\"article\",\"doc_date\":\"13 junio
2024\",\"sub_index\":0,\"doc_title\":\"L_202401689ES.000101.fmx.xml\",\"source\":\"eu_ai_ac
t\",\"unit_title\":\"Artículo
26\",\"id\":\"6894451b30952f00cc47f204c382d6eb\"},\"distance\":0.214594304561615},{\"id\":
\"8d84e19594df27c6cca8e9961aac43a6\",\"text\":\"Responsabilidades a lo largo de la
cadena de valor de la IA\\n1. Cualquier distribuidor, importador, responsable del despliegue
o tercero será considerado proveedor de un sistema de IA de alto riesgo a los efectos del
presente Reglamento y estará sujeto a las obligaciones del proveedor previstas en el
artículo 16 en cualquiera de las siguientes circunstancias:\\na)\\ncuando ponga su nombre o
marca en un sistema de IA de alto riesgo previamente introducido en el mercado o puesto
en servicio, sin perjuicio de los acuerdos contractuales que estipulen que las obligaciones
se asignan de otro modo;\\nb)\\ncuando modifique sustancialmente un sistema de IA de alto
riesgo que ya haya sido introducido en el mercado o puesto en servicio de tal manera que
siga siendo un sistema de IA de alto riesgo con arreglo al artículo 6;\\nc)\\ncuando modifique
la finalidad prevista de un sistema de IA, incluido un sistema de IA de uso general, que no
haya sido considerado de alto riesgo y ya haya sido introducido en el mercado o puesto en
servicio, de tal manera que el sistema de IA de que se trate se convierta en un sistema de
IA de alto riesgo de conformidad con el artículo
6.\",\"metadata\":{\"unit_type\":\"article\",\"source\":\"eu_ai_act\",\"sub_index\":0,\"file\":\"EU_A


I_Act_2024_1689_ES.html\",\"doc_title\":\"L_202401689ES.000101.fmx.xml\",\"doc_date\":\"
13 junio 2024\",\"unit_title\":\"Artículo
25\",\"unit_id\":\"25\",\"unit_index\":30,\"id\":\"8d84e19594df27c6cca8e9961aac43a6\"},\"dista
nce\":0.22513842582702637},{\"id\":\"b99e0d02811935240ce38d51196bdd7f\",\"text\":\"Obli
gaciones de los proveedores de modelos de IA de uso general con riesgo
sistémico\",\"metadata\":{\"doc_date\":\"13 junio 2024\",\"unit_title\":\"SECCIÓN
3\",\"unit_id\":\"3\",\"unit_type\":\"section\",\"sub_index\":0,\"file\":\"EU_AI_Act_2024_1689_E
S.html\",\"source\":\"eu_ai_act\",\"doc_title\":\"L_202401689ES.000101.fmx.xml\",\"unit_index
\":66,\"id\":\"b99e0d02811935240ce38d51196bdd7f\"},\"distance\":0.2278081774711609},{\"i
d\":\"62018f0d02a5fb86c271b25dc9bc6365\",\"text\":\"por parte del proveedor, si este
proporciona al responsable del despliegue el\\nsistema de IA como un MLSaaS ( Machine
Learning as a Service ) u otras formas de\\ncomercialización y puesta en marcha que
impliquen una instalación automática por\\nel responsable del despliegue donde no haya
configuración del sistema.\\n● Si el sistema de IA va a ser entregado al responsable del
despliegue en un formato\\non-premise o in-cloud, gestionado por el responsable del
despliegue, el proveedor\\ndebe proporcionar unas instrucciones adecuadas para realizar la
protección del\\nsistema especialmente durante el tiempo de inferencia del sistema de IA
en\\nproducción. El proceso de instalación del sistema de IA debe contar con\\nmecanismos
que garanticen que la instalación tenga en cuenta las instrucciones de\\nmanera obligatoria,
bien a través de pr ocedimientos de script automáticos o semi\\nautomáticos, la obligación
de disponer de las instrucciones abiertas para el proceso\\nantes de continuar, la solicitud
explicita de la lectura de estas o la referencia a la\\nlectura especifica a conocer para cada
paso del proceso.\\n● Las actualizaciones del sistema de inteligencia artificial de alto riesgo
deben de ser\\ntratadas con todas las medidas aplicables descritas en esta guía.\\nComo
complemento a estas medidas organizativas, el proveedor deberá alinear las\\nsiguientes
medidas técnicas:\",\"metadata\":{\"unit_title\":\"4.1.1 Medidas
aplicables\",\"file\":\"11-guia-ciberseguridad.pdf\",\"unit_id\":\"4.1.1\",\"doc_date\":\"
diciembre
2025\",\"sub_index\":2,\"id\":\"62018f0d02a5fb86c271b25dc9bc6365\",\"source\":\"aesia\",\"d
oc_title\":\"Empresas desarrollando cumplimiento de
requisitos\",\"unit_index\":43,\"unit_type\":\"subsection\"},\"distance\":0.21921683847904205}
]",
"metadata":
"{\"mode\":\"soft\",\"k\":5,\"n_results\":5,\"min_distance\":0.2146,\"max_distance\":0.2278}"
},
{
"id": "a2d485ce-750e-4588-b843-03a14965683f",
"type": "SPAN",
"name": "rag.grade (a2d485ce)",
"startTime": "2026-03-02T09:35:39.189Z",
"endTime": "2026-03-02T09:39:29.089Z",
"depth": 0,
"input": "{\"args\":[\"Obligaciones para sistemas de IA de alto riesgo según el EU AI
Act\",[{\"doc\":\"Obligaciones de los proveedores y responsables del despliegue de sistemas
de IA de alto riesgo y de otras partes\",\"metadata\":{\"unit_id\":\"3\",\"doc_date\":\"13 junio
2024\",\"unit_title\":\"SECCIÓN
3\",\"source\":\"eu_ai_act\",\"id\":\"1927ec2cec85c21d989d73a8d932b5c0\",\"unit_type\":\"se
ction\",\"file\":\"EU_AI_Act_2024_1689_ES.html\",\"sub_index\":0,\"unit_index\":20,\"doc_title\


":\"L_202401689ES.000101.fmx.xml\"},\"score\":0.7854188084602356},{\"doc\":\"Obligacione
s de los responsables del despliegue de sistemas de IA de alto riesgo\\n1. Los
responsables del despliegue de sistemas de IA de alto riesgo adoptarán medidas técnicas y
organizativas adecuadas para garantizar que utilizan dichos sistemas con arreglo a las
instrucciones de uso que los acompañen, de acuerdo con los apartados 3 y 6.\\n2. Los
responsables del despliegue encomendarán la supervisión humana a personas físicas que
tengan la competencia, la formación y la autoridad necesarias.\\n3. Las obligaciones
previstas en los apartados 1 y 2 no afectan a otras obligaciones que el Derecho nacional o
de la Unión imponga a los responsables del despliegue ni a su libertad para organizar sus
propios recursos y actividades con el fin de poner en práctica las medidas de supervisión
humana que indique el proveedor.\\n4. Sin perjuicio de lo dispuesto en los apartados 1 y 2,
el responsable del despliegue se asegurará de que los datos de entrada sean pertinentes y
suficientemente representativos en vista de la finalidad prevista del sistema de IA de alto
riesgo, en la medida en que ejerza el control sobre dichos
datos.\",\"metadata\":{\"unit_index\":31,\"unit_id\":\"26\",\"file\":\"EU_AI_Act_2024_1689_ES.h
tml\",\"unit_type\":\"article\",\"doc_date\":\"13 junio
2024\",\"sub_index\":0,\"doc_title\":\"L_202401689ES.000101.fmx.xml\",\"source\":\"eu_ai_ac
t\",\"unit_title\":\"Artículo
26\",\"id\":\"6894451b30952f00cc47f204c382d6eb\"},\"score\":0.785405695438385},{\"doc\":\
"Responsabilidades a lo largo de la cadena de valor de la IA\\n1. Cualquier distribuidor,
importador, responsable del despliegue o tercero será considerado proveedor de un sistema
de IA de alto riesgo a los efectos del presente Reglamento y estará sujeto a las obligaciones
del proveedor previstas en el artículo 16 en cualquiera de las siguientes
circunstancias:\\na)\\ncuando ponga su nombre o marca en un sistema de IA de alto riesgo
previamente introducido en el mercado o puesto en servicio, sin perjuicio de los acuerdos
contractuales que estipulen que las obligaciones se asignan de otro modo;\\nb)\\ncuando
modifique sustancialmente un sistema de IA de alto riesgo que ya haya sido introducido en
el mercado o puesto en servicio de tal manera que siga siendo un sistema de IA de alto
riesgo con arreglo al artículo 6;\\nc)\\ncuando modifique la finalidad prevista de un sistema
de IA, incluido un sistema de IA de uso general, que no haya sido considerado de alto
riesgo y ya haya sido introducido en el mercado o puesto en servicio, de tal manera que el
sistema de IA de que se trate se convierta en un sistema de IA de alto riesgo de
conformidad con el artículo
6.\",\"metadata\":{\"unit_type\":\"article\",\"source\":\"eu_ai_act\",\"sub_index\":0,\"file\":\"EU_A
I_Act_2024_1689_ES.html\",\"doc_title\":\"L_202401689ES.000101.fmx.xml\",\"doc_date\":\"
13 junio 2024\",\"unit_title\":\"Artículo
25\",\"unit_id\":\"25\",\"unit_index\":30,\"id\":\"8d84e19594df27c6cca8e9961aac43a6\"},\"scor
e\":0.7748615741729736},{\"doc\":\"Obligaciones de los proveedores de modelos de IA de
uso general con riesgo sistémico\",\"metadata\":{\"doc_date\":\"13 junio
2024\",\"unit_title\":\"SECCIÓN
3\",\"unit_id\":\"3\",\"unit_type\":\"section\",\"sub_index\":0,\"file\":\"EU_AI_Act_2024_1689_E
S.html\",\"source\":\"eu_ai_act\",\"doc_title\":\"L_202401689ES.000101.fmx.xml\",\"unit_index
\":66,\"id\":\"b99e0d02811935240ce38d51196bdd7f\"},\"score\":0.7721918225288391},{\"doc\
":\"por parte del proveedor, si este proporciona al responsable del despliegue el\\nsistema
de IA como un MLSaaS ( Machine Learning as a Service ) u otras formas
de\\ncomercialización y puesta en marcha que impliquen una instalación automática por\\nel
responsable del despliegue donde no haya configuración del sistema.\\n● Si el sistema de
IA va a ser entregado al responsable del despliegue en un formato\\non-premise o in-cloud,


gestionado por el responsable del despliegue, el proveedor\\ndebe proporcionar unas
instrucciones adecuadas para realizar la protección del\\nsistema especialmente durante el
tiempo de inferencia del sistema de IA en\\nproducción. El proceso de instalación del
sistema de IA debe contar con\\nmecanismos que garanticen que la instalación tenga en
cuenta las instrucciones de\\nmanera obligatoria, bien a través de pr ocedimientos de script
automáticos o semi\\nautomáticos, la obligación de disponer de las instrucciones abiertas
para el proceso\\nantes de continuar, la solicitud explicita de la lectura de estas o la
referencia a la\\nlectura especifica a conocer para cada paso del proceso.\\n● Las
actualizaciones del sistema de inteligencia artificial de alto riesgo deben de ser\\ntratadas
con todas las medidas aplicables descritas en esta guía.\\nComo complemento a estas
medidas organizativas, el proveedor deberá alinear las\\nsiguientes medidas
técnicas:\",\"metadata\":{\"unit_title\":\"4.1.1 Medidas
aplicables\",\"file\":\"11-guia-ciberseguridad.pdf\",\"unit_id\":\"4.1.1\",\"doc_date\":\"10
diciembre
2025\",\"sub_index\":2,\"id\":\"62018f0d02a5fb86c271b25dc9bc6365\",\"source\":\"aesia\",\"d
oc_title\":\"Empresas desarrollando cumplimiento de
requisitos\",\"unit_index\":43,\"unit_type\":\"subsection\"},\"score\":0.780783161520958}]],\"k
wargs\":{}}",
"metadata": "{}"
},
{
"id": "0673bd5e-0d1d-4225-9ad3-eb2ad011ca92",
"type": "SPAN",
"name": "rag.generate (0673bd5e)",
"startTime": "2026-03-02T09:39:29.090Z",
"endTime": "2026-03-02T09:39:31.493Z",
"depth": 0,
"input": "{\"args\":[\"Obligaciones para sistemas de IA de alto riesgo según el EU AI
Act\",[{\"doc\":\"Responsabilidades a lo largo de la cadena de valor de la IA\\n1. Cualquier
distribuidor, importador, responsable del despliegue o tercero será considerado proveedor
de un sistema de IA de alto riesgo a los efectos del presente Reglamento y estará sujeto a
las obligaciones del proveedor previstas en el artículo 16 en cualquiera de las siguientes
circunstancias:\\na)\\ncuando ponga su nombre o marca en un sistema de IA de alto riesgo
previamente introducido en el mercado o puesto en servicio, sin perjuicio de los acuerdos
contractuales que estipulen que las obligaciones se asignan de otro modo;\\nb)\\ncuando
modifique sustancialmente un sistema de IA de alto riesgo que ya haya sido introducido en
el mercado o puesto en servicio de tal manera que siga siendo un sistema de IA de alto
riesgo con arreglo al artículo 6;\\nc)\\ncuando modifique la finalidad prevista de un sistema
de IA, incluido un sistema de IA de uso general, que no haya sido considerado de alto
riesgo y ya haya sido introducido en el mercado o puesto en servicio, de tal manera que el
sistema de IA de que se trate se convierta en un sistema de IA de alto riesgo de
conformidad con el artículo
6.\",\"metadata\":{\"unit_type\":\"article\",\"source\":\"eu_ai_act\",\"sub_index\":0,\"file\":\"EU_A
I_Act_2024_1689_ES.html\",\"doc_title\":\"L_202401689ES.000101.fmx.xml\",\"doc_date\":\"
13 junio 2024\",\"unit_title\":\"Artículo
25\",\"unit_id\":\"25\",\"unit_index\":30,\"id\":\"8d84e19594df27c6cca8e9961aac43a6\"},\"scor
e\":0.7748615741729736}]],\"kwargs\":{}}",


"output": "{\"answer\":\"**Obligaciones para sistemas de IA de alto riesgo según el EU AI
Act**\\n\\nSegún el EU AI Act, las obligaciones para los sistemas de IA de alto riesgo se
establecen en el Artículo 25, que detalla las responsabilidades a lo largo de la cadena de
valor de la IA. Aquí se resumen las obligaciones específicas para los proveedores de
sistemas de IA de alto riesgo:\\n\\n1. **Distribuidores, Importadores, Responsables del
Despliegue o Terceros como Proveedores de Sistemas de IA de Alto Riesgo:**\\n - Serán
considerados proveedores de un sistema de IA de alto riesgo y estarán sujetos a las
obligaciones del proveedor previstas en el artículo 16 en las siguientes circunstancias:\\n
a) **Cuando pongan su nombre o marca en un sistema de IA de alto riesgo previamente
introducido en el mercado o puesto en servicio**, sin perjuicio de los acuerdos contractuales
que estipulen que las obligaciones se asignan de otro modo (Artículo 25(1)(a)).\\n b)
**Cuando modifiquen sustancialmente un sistema de IA de alto riesgo que ya haya sido
introducido en el mercado o puesto en servicio**, de tal manera que siga siendo un sistema
de IA de alto riesgo de conformidad con el artículo 6 (Artículo 25(1)(b)).\\n c) **Cuando
modifiquen la finalidad prevista de un sistema de IA, incluido un sistema de IA de uso
general, que no haya sido considerado de alto riesgo y ya haya sido introducido en el
mercado o puesto en servicio**, de tal manera que el sistema de IA de que se trate se
convierta en un sistema de IA de alto riesgo de conformidad con el artículo 6 (Artículo
25(1)(c)).\\n\\nEstas obligaciones implican que los proveedores deben cumplir con las
exigencias establecidas en el artículo 16 del EU AI Act, que incluyen aspectos como la
evaluación de la conformidad, la documentación, la supervisión del mercado, y la garantía
de que los sistemas de IA de alto riesgo cumplen con los requisitos de seguridad y robustez
establecidos en la normativa.\\n\\n**Fuentes:**\\n- EU AI Act, Artículo 25.\\n\\n_Informe
preliminar generado por IA. Consulte profesional
jurídico._\",\"sources\":[{\"unit_type\":\"article\",\"source\":\"eu_ai_act\",\"sub_index\":0,\"file\":\
"EU_AI_Act_2024_1689_ES.html\",\"doc_title\":\"L_202401689ES.000101.fmx.xml\",\"doc_d
ate\":\"13 junio 2024\",\"unit_title\":\"Artículo
25\",\"unit_id\":\"25\",\"unit_index\":30,\"id\":\"8d84e19594df27c6cca8e9961aac43a6\"}],\"gro
unded\":true}",
"metadata": "{\"n_context_docs\":1,\"grounded\":true}"
}
]

###### Análisis de Code Claude

**Pipeline completo: FUNCIONAL** ✓

El flujo completo funcionó correctamente. Desglose por etapa:

**retrieve() —** ✓ **OK (16s)**

```
● 5 docs recuperados con scores 0.77-0.79 — buena precisión semántica
● Docs correctos: Art. 25 (cadena de valor), Art. 26 (responsables despliegue), guía AESIA,
cabeceras Sección 3
● ChromaDB respondió en 16s (frío, primer acceso)
```

**grade() —** ✓ **FUNCIONAL, pero** ⚠ **dos problemas**

**Problema 1 — Latencia crítica: 3:50 minutos**
Cada llamada Ollama tarda ~45-60s en CPU:
doc 1: 33s
doc 2: 60s
doc 3: 62s
doc 4: 10s ← único rápido
doc 5: 63s
─────────────
Total: ~228s = 3:48

5 llamadas secuenciales × Qwen 2.5 3B en CPU = **cuello de botella claro**.
**Problema 2 — Filtrado demasiado agresivo**
Solo pasó **1 de 5 docs** (Art. 25). Fue filtrado el **Art. 26** — que es literalmente "Obligaciones de los
responsables del despliegue de sistemas de IA de alto riesgo" — directamente relevante a la query. El
Qwen 3B está siendo muy restrictivo en la grading task.

**generate() —** ✓ **OK (2s)**

```
● Bedrock Nova Lite respondió en 2 segundos
● grounded: true — respuesta anclada en corpus real
● Cita correcta: Art. 25, EU AI Act, 13 junio 2024
● Disclaimer presente ✓
```
**Calidad de la respuesta —** ⚠ **Correcta pero incompleta**

La respuesta es **factualmente correcta** pero la pregunta era "qué obligaciones tiene un sistema de
alto riesgo" y la respuesta solo cubre Art. 25 (quién se convierte en proveedor). Le falta:

```
● Art. 16 — obligaciones principales del proveedor (documentación técnica, evaluación de
conformidad)
● Art. 26 — obligaciones del responsable del despliegue (supervisión humana, datos
representativos)
● Art. 9-15 — gestión de riesgos, datos, transparencia, exactitud, robustez
```
Causa raíz: el grading eliminó Art. 26 y el contexto de generate quedó con solo 1 doc.

**Resumen Query 1**

```
Métrica Valor Estado
Latencia total ~4 min ⚠ PROBLEMA
Latencia Ollama/doc 33-63s ⚠ CPU lento
Docs retrieved 5 ✓
Docs tras grading 1/5 ⚠ Muy restrictivo
```

```
Respuesta grounded sí ✓
Citas correctas Art. 25 ✓
Disclaimer presente ✓
Langfuse trazando sí ✓
```
**Riesgo para la demo**

**La latencia de 4 minutos es el mayor riesgo**. En presentación en vivo, el evaluador verá 4 minutos de
espera. Hay dos mitigaciones rápidas posibles:

1. **Reducir k de 5 a 3** — ahorra ~90s, implementación: 1 línea
2. **Pre-calentar Ollama** antes de la demo (el modelo ya estaba cargado tras la primera llamada
    — el doc 4 tardó solo 10s)

### Query 2

###### Input en chat UI

Tengo un sistema que analiza currículums automáticamente para filtrar candidatos en procesos de
selección. ¿En qué nivel de riesgo lo clasificarías?

###### Salida en chat UI

Tu sistema que analiza currículums automáticamente para filtrar candidatos en
procesos de selección ha sido clasificado como de riesgo alto. Según la herramienta
de clasificación, la confianza en esta clasificación es del 85%, y la referencia legal
es el Anexo III, categoría 4.a del EU AI Act.

Este nivel de riesgo implica que el sistema tiene el potencial de causar daños
significativos a la salud, la seguridad o los derechos legales de las personas,
especialmente en relación con la privacidad y la no discriminación en procesos de
selección.

_Informe preliminar generado por IA. Consulte profesional jurídico._

###### Salida en docker logs

No hay.

###### Logs de langfuse en JSON

[
{
"id": "2490140c-9476-49c2-8605-145fbf68b17d",
"type": "SPAN",


"name": "classifier.predict_risk (2490140c)",
"startTime": "2026-03-02T09:45:58.579Z",
"endTime": "2026-03-02T09:45:59.145Z",
"depth": 0,
"input": "{\"args\":[\"Un sistema que analiza currículums automáticamente para filtrar
candidatos en procesos de selección.\"],\"kwargs\":{}}",
"output":
"{\"risk_level\":\"alto_riesgo\",\"confidence\":0.85,\"probabilities\":{\"inaceptable\":0.9939,\"alto
\":0.0019,\"limitado\":0.0002,\"mínimo\":0.004},\"shap_top_features\":[{\"feature\":\"num_pala
bras\",\"contribution\":0.8221570253372192},{\"feature\":\"svd_24\",\"contribution\":0.624691
6651725769},{\"feature\":\"svd_30\",\"contribution\":0.5895200967788696},{\"feature\":\"svd_
2\",\"contribution\":0.5856242775917053},{\"feature\":\"svd_12\",\"contribution\":0.485838472
84317017}],\"shap_explanation\":\"Factores principales para 'inaceptable': num_palabras,
svd_24, svd_30.\",\"annex3_override\":true,\"annex3_ref\":\"Anexo III cat.
4.a\",\"ml_prediction\":{\"risk_level\":\"inaceptable\",\"confidence\":0.9939029812812805}}",
"metadata":
"{\"risk_level\":\"alto_riesgo\",\"confidence\":0.85,\"probabilities\":{\"inaceptable\":0.9939,\"alto
\":0.0019,\"limitado\":0.0002,\"mínimo\":0.004}}"
}
]

###### Análisis de Code Claude

**Pipeline: classify_risk solamente (sin RAG) — correcto** ✓

El orquestador eligió la tool adecuada: no hay RAG, solo clasificador. Latencia: **0.57 segundos** —
excelente.

**Clasificación legal —** ✓ **Correcta**

"Alto riesgo" es la clasificación correcta según EU AI Act **Anexo III, categoría 4.a** (sistemas de IA en
empleo, gestión de candidatos). La UI lo presenta bien, con referencia legal y disclaimer.

**BUG CRÍTICO encontrado — Contradicción de campos**

Mirando el output de Langfuse:
{
"risk_level": "alto_riesgo", ← resultado final
"confidence": 0.85,

"probabilities": {
"inaceptable": 0.9939, ← ⚠ contradice risk_level
"alto": 0.0019,
"limitado": 0.0002,
"mínimo": 0.004
},

"shap_explanation": "Factores principales para 'inaceptable'...", ← ⚠ clase incorrecta


"annex3_override": true, ← override activo
"ml_prediction": {
"risk_level": "inaceptable", ← predicción ML bruta
"confidence": 0.9939
}
}

Lo que está pasando:

1. El modelo ML predice **inaceptable** con 99.39% de confianza
2. El sistema lo **sobreescribe** a alto_riesgo via annex3_override (correcto legalmente)
3. Pero **las probabilidades no se actualizan** — siguen mostrando la distribución de la predicción
    ML original
4. La **SHAP explanation también queda desincronizada** — explica inaceptable cuando el
    output es alto_riesgo

**El override es legalmente correcto, pero los campos auxiliares son inconsistentes.**

**BUG MEDIO — SHAP explica la clase equivocada**

"shap_explanation": "Factores principales para 'inaceptable': num_palabras, svd_24, svd_30."

El usuario recibe alto_riesgo como clasificación, pero la explicabilidad está describiendo por qué el
modelo interno dijo inaceptable. En una demo, si el evaluador pregunta "¿por qué es alto riesgo?", la
respuesta interna será sobre la clase equivocada.

**PREOCUPACIÓN — Features SHAP opacas para la demo**

Las top features son:
num_palabras, svd_24, svd_30, svd_2, svd_12

No aparecen keywords interpretables ("selección", "candidatos", "empleo"). Esto es esperable (SVD
transforma el espacio de features) pero dificulta la narrativa en presentación si alguien pregunta
"¿qué hizo que el sistema lo clasificara así?"

**Resumen Query 2**

```
Métrica Valor Estado
Latencia 0.57s ✓ Excelente
Tool elegida classify_risk ✓ Correcto
Clasificación final alto_riesgo ✓ Legalmente correcta
Referencia legal Anexo III cat. 4.a ✓
Disclaimer presente ✓
```

```
probabilities vs risk_level contradictorios ⚠ Bug
SHAP explanation clase incorrecta ⚠ Bug
Features SHAP SVD opacas ⚠ Demo risk
```
**Prioridad de fix**

El bug de probabilities contradictorias y shap_explanation con clase equivocada está en
src/classifier/main.py — en la lógica de annex3_override. Cuando se activa el override, habría que
actualizar los campos derivados (probabilities calibradas a la clase final, shap_explanation con la
clase correcta). Es un fix de Rubén, y el impacto en la demo es alto si el evaluador mira los logs o
pregunta por la explicabilidad.
Siguiente query cuando quieras.

### Query 3

###### Input en chat UI

Genera un informe de cumplimiento para un sistema de scoring crediticio automático.

###### Output en chat UI

## Informe de Cumplimiento del Sistema

## de Scoring Crediticio Automático

#### 1. Resumen Ejecutivo

El sistema de scoring crediticio automático evalúa la solvencia de un individuo
basándose en varios factores como historia crediticia, ingresos, deudas y otros
indicadores financieros. Este sistema ha sido clasificado como de alto riesgo debido
a las implicaciones significativas que su uso puede tener en la vida de las personas.

#### 2. Clasificación de Riesgo

El sistema ha sido asignado al nivel de riesgo "alto riesgo" según el Anexo III cat.
5.b del Reglamento Europeo de IA (EU AI Act). Este nivel se reserva para sistemas
cuyo uso está permitido, pero que conllevan un alto riesgo debido a su impacto
potencial en la seguridad, la vida o los derechos fundamentales de las personas.

#### 3. Obligaciones Aplicables

**Declaración UE de Conformidad**


Según el artículo 47 del EU AI Act, el proveedor del sistema de scoring crediticio
automático debe redactar una declaración UE de conformidad para cada sistema de
IA de alto riesgo. Esta declaración debe cumplir los siguientes requisitos:

1. Formato y Disponibilidad: La declaración debe estar en un formato legible
    por máquina, firmada electrónica o manuscritamente, y mantenerse
    disponible para las autoridades nacionales competentes durante un
    período de diez años.
2. Contenido: La declaración debe especificar el sistema de IA de alto riesgo
    y contener la información indicada en el anexo V. Además, debe traducirse
    a una lengua que puedan entender fácilmente las autoridades
    competentes.
3. Responsabilidad: Al elaborar la declaración, el proveedor asume la
    responsabilidad del cumplimiento de los requisitos establecidos en la
    sección 2 del EU AI Act.

#### 4. Citas Legales

```
● EU AI Act — Artículo 47: Declaración UE de conformidad.
● EU AI Act — Anexo III cat. 5.b: Clasificación de sistemas de alto riesgo.
```
#### 5. Recomendaciones

1. Redactar Declaración UE de Conformidad: El proveedor debe redactar una
    declaración UE de conformidad para el sistema de scoring crediticio
    automático, asegurando que cumpla con todos los requisitos establecidos
    en el artículo 47 del EU AI Act.
2. Mantenimiento y Actualización: La declaración debe mantenerse
    actualizada y disponible para las autoridades competentes según lo
    establecido en la normativa.
3. Traducción y Disponibilidad: La declaración debe traducirse a una lengua
    comprensible para las autoridades nacionales competentes y mantenerse
    disponible durante el período requerido.

_Informe preliminar generado por IA. Consulte profesional jurídico._

###### Salida en docker logs

No hay.

###### Logs de langfuse en JSON

[
{
"id": "812fff9d-8522-47f6-b21f-ec8dc7f15bcc",


"type": "SPAN",
"name": "classifier.predict_risk (812fff9d)",
"startTime": "2026-03-02T09:49:26.138Z",
"endTime": "2026-03-02T09:49:26.153Z",
"depth": 0,
"input": "{\"args\":[\"Sistema de IA que evalúa el riesgo de recidiva de presos para
recomendar libertad condicional\"],\"kwargs\":{}}",
"output":
"{\"risk_level\":\"alto_riesgo\",\"confidence\":0.85,\"probabilities\":{\"inaceptable\":0.9922,\"alto
\":0.0073,\"limitado\":0.0002,\"mínimo\":0.0003},\"shap_top_features\":[{\"feature\":\"num_pal
abras\",\"contribution\":1.0230586528778076},{\"feature\":\"svd_24\",\"contribution\":0.93559
78965759277},{\"feature\":\"svd_30\",\"contribution\":0.6751113533973694},{\"feature\":\"svd
_32\",\"contribution\":0.5668127536773682},{\"feature\":\"svd_2\",\"contribution\":0.52756577
73017883}],\"shap_explanation\":\"Factores principales para 'inaceptable': num_palabras,
svd_24, svd_30.\",\"annex3_override\":true,\"annex3_ref\":\"Anexo III cat.
6\",\"ml_prediction\":{\"risk_level\":\"inaceptable\",\"confidence\":0.992236316204071}}",
"metadata":
"{\"risk_level\":\"alto_riesgo\",\"confidence\":0.85,\"probabilities\":{\"inaceptable\":0.9922,\"alto
\":0.0073,\"limitado\":0.0002,\"mínimo\":0.0003}}"
}
]
[
{
"id": "7d9fa5fa-ae1c-45cf-8815-d12cb0e699d3",
"type": "SPAN",
"name": "rag.retrieve (7d9fa5fa)",
"startTime": "2026-03-02T09:49:26.908Z",
"endTime": "2026-03-02T09:49:27.032Z",
"depth": 0,
"input": "{\"args\":[\"EU AI Act Artículos aplicables a sistemas de IA de alto
riesgo\"],\"kwargs\":{}}",
"output": "[{\"doc\":\"Ámbito de aplicación\\n1. El presente Reglamento se aplicará
a:\\na)\\nlos proveedores que introduzcan en el mercado o pongan en servicio sistemas de
IA o que introduzcan en el mercado modelos de IA de uso general en la Unión, con
independencia de si dichos proveedores están establecidos o ubicados en la Unión o en un
tercer país;\\nb)\\nlos responsables del despliegue de sistemas de IA que estén
establecidos o ubicados en la Unión;\\nc)\\nlos proveedores y responsables del despliegue
de sistemas de IA que estén establecidos o ubicados en un tercer país, cuando los
resultados de salida generados por el sistema de IA se utilicen en la Unión;\\nd)\\nlos
importadores y distribuidores de sistemas de IA;\\ne)\\nlos fabricantes de productos que
introduzcan en el mercado o pongan en servicio un sistema de IA junto con su producto y
con su propio nombre o marca;\\nf)\\nlos representantes autorizados de los proveedores
que no estén establecidos en la Unión;\\ng)\\nlas personas afectadas que estén ubicadas en
la Unión.\\n2. A los sistemas de IA clasificados como sistemas de IA de alto riesgo de
conformidad con el artículo 6, apartado 1, y relativos a productos regulados por los actos
legislativos de armonización de la Unión enumerados en la sección B del anexo I,
únicamente se les aplicará el artículo 6, apartado 1, y los artículos 102 a 109 y el artículo

112. El artículo 57 se aplicará únicamente en la medida en que los requisitos para los


sistemas de IA de alto riesgo en virtud del presente Reglamento se hayan integrado en
dichos actos legislativos de armonización de la Unión.\\n3. El presente Reglamento no se
aplicará a los ámbitos que queden fuera del ámbito de aplicación del Derecho de la Unión y,
en cualquier caso, no afectará a las competencias de los Estados miembros en materia de
seguridad nacional, independientemente del tipo de entidad a la que los Estados miembros
hayan encomendado el desempeño de tareas en relación con dichas
competencias.\",\"metadata\":{\"unit_type\":\"article\",\"unit_index\":2,\"id\":\"737a455bf8c4b4
bd15ad3027bef40dbd\",\"unit_id\":\"2\",\"sub_index\":0,\"unit_title\":\"Artículo
2\",\"source\":\"eu_ai_act\",\"doc_title\":\"L_202401689ES.000101.fmx.xml\",\"doc_date\":\"13
junio
2024\",\"file\":\"EU_AI_Act_2024_1689_ES.html\"},\"score\":0.7600609362125397},{\"doc\":\"
9\\nA) Sistemas prohibidos: los usos de IA que se encuentren en este nivel de la jerarquía
están\\nprohibidos debido al alto riego que entrañan: sistemas IA que suponen una
amenaza para la\\nseguridad, la vida o los derechos fundamentales. En este nivel se
encuentran, por ejemplo, los\\nsistemas con alguna de las siguientes funciones:\\n•
Manipulación subliminal del comportamiento de una persona de manera que\\npueda
causarle daños físicos o psicológicos a él o a otros.\\n• Explotación de vulnerabilidades de
grupos sociales para manipular su\\ncomportamiento de forma que pueda causarles daño a
ellos o a otros.\\n• Evaluación o clasificación de personas o grupos por su comportamiento
social que\\npueda perjudicarlos desproporcionadamente en el ámbito del
comportamiento\\nobservado, o perjudicarlos en ámbitos distintos a donde se observó.\\n•
Identificación biométrica en tiempo real en espacios de acceso público para\\nautoridades
policiales, salvo casos tasados y mediando autorización.\\nLa Comisión Europea ha
preparado unas directrices con el fin de aclarar la interpretación de\\nciertos casos
concretos (Guidelines on prohibited artificial intelligence practices established
by\\nRegulation (EU) 20241689 (AI Act)) 1.\\nB) Sistemas de Alto Riesgo: el segundo nivel
se reserva a los sistemas de alto riesgo, pero\\ncuyo uso está permitido, a los que el
Reglamento dedica la mayoría de los requisitos y\\nobligaciones que deben cumplir los
distintos roles que participan en la cadena de valor de la\\npuesta en uso de un sistema IA
(operadores). Se dividen en dos tipos de sistemas:\\nB1) Productos o componentes de
seguridad de alto riesgo contemplados en\\nlegislación de armonización:\\no Sistemas de IA
que sea un componente de seguridad de alguno de los productos\\ncontemplados en la
legislación de armonización de la Unión recogidos en el Anexo\\nI del Reglamento o,\\no
Que el propio sistema de IA como producto, deba someterse a una evaluación de
la\",\"metadata\":{\"file\":\"guia_01_intro_reglamento_ia.pdf\",\"sub_index\":1,\"id\":\"f0173017
05f02276959c1fcba419dfc2\",\"unit_index\":18,\"doc_title\":\"1\",\"source\":\"aesia\",\"unit_typ
e\":\"section\",\"doc_date\":\"10 diciembre 2025\",\"unit_id\":\"2.3\",\"unit_title\":\"2.3 Niveles
de riesgo del Reglamento Europeo de
IA\"},\"score\":0.7696539908647537},{\"doc\":\"continuo planificado y ejecutado durante todo
el ciclo de vida de un sistema\\nAI Act\\n\\n12\\nde IA de alto riesgo, que requerirá
revisiones y actualizaciones sistemáticas\\nperiódicas. Constará de las siguientes
etapas:\\na) la determinación y el análisis de los riesgos conocidos y previsibles\\nque el
sistema de IA de alto riesgo pueda plantear para la salud, la\\nseguridad o los derechos
fundamentales cuando el sistema de IA de\\nalto riesgo se utilice de conformidad con su
finalidad prevista;\\nb) la estimación y la evaluación de los riesgos que podrían
surgir\\ncuando el sistema de IA de alto riesgo se utilice de conformidad con\\nsu finalidad
prevista y cuando se le dé un uso indebido\\nrazonablemente previsible;\\nc) la evaluación
de otros riesgos que podrían surgir, a partir del análisis\\nde los datos recogidos con el


sistema de vigilancia\\nposcomercialización a que se refiere el artículo 72;\\nd) la adopción
de medidas adecuadas y específicas de gestión de\\nriesgos diseñadas para hacer frente a
los riesgos detectados con\\narreglo a la letra
a).\",\"metadata\":{\"unit_type\":\"chapter\",\"file\":\"05-guia-de-gestion-de-riesgos.pdf\",\"id\":\"
193af7ed5209e3ee4aad244c14546876\",\"source\":\"aesia\",\"unit_title\":\"2. El sistema de
gestión de riesgos se entenderá como un proceso
iterativo\",\"sub_index\":0,\"unit_index\":42,\"doc_date\":\"10 diciembre
2025\",\"unit_id\":\"2\",\"doc_title\":\"0\"},\"score\":0.7664396464824677},{\"doc\":\"Artificial\\nL
a puesta en servicio o la utilización de sistemas de IA de alto riesgo debe supeditarse\\nal
cumplimiento de determinados requisitos obligatorios, entre los cuales está el de\\nla
gestión de riesgos. Estos requisitos tienen como objetivo garantizar que los sistemas\\nde
IA de alto riesgo disponibles en la Unión o cuyos resultados de salida se utilicen en
la\\nUnión no representen riesgos inaceptables para intereses públicos
importantes\\nreconocidos y protegidos por el Derecho de la Unión.\\nEn este apartado se
incluye los artículos referentes a la generación de la gestión de riesgos\\ndel Reglamento
2024/1689 del Parlamento Europeo y del Consejo, de 13 de junio de 2024\\n(Reglamento
Europeo de Inteligencia Artificial) y se detalla en que secciones de esta guía\\nse abordan
los diferentes elementos de dichos
artículos.\",\"metadata\":{\"source\":\"aesia\",\"sub_index\":0,\"unit_type\":\"chapter\",\"doc_da
te\":\"10 diciembre 2025\",\"unit_title\":\"3. Reglamento de
Inteligencia\",\"unit_id\":\"3\",\"doc_title\":\"0\",\"id\":\"8856439c4e28777c2b9485525355c3e7\
",\"unit_index\":39,\"file\":\"05-guia-de-gestion-de-riesgos.pdf\"},\"score\":0.766067564487457
3},{\"doc\":\"Artificial\\nLa puesta en servicio o la utilización de sistemas de IA de alto riesgo
debe supeditarse\\nal cumplimiento de determinados requisitos obligatorios, entre los cuales
está el de\\nnotificación de incidentes graves. Estos requisitos tienen como objetivo
garantizar que\\nlos sistemas de IA de alto riesgo disponibles en la Unión o cuyos
resultados de salida se\\nutilicen en la Unión no representen riesgos inaceptables para
intereses públicos\\nimportantes reconocidos y protegidos por el Derecho de la Unión.\\nEn
este apartado se incluye los artículos referentes a la g estión de incidentes graves
del\\nReglamento 2024/1689 del Parlamento Europeo y del Consejo, de 13 de junio de
2024\\n(Reglamento Europeo de Inteligencia Artificial) y se detalla en que secciones de esta
guía\\nse abordan los diferentes elementos de dichos
artículos.\",\"metadata\":{\"unit_id\":\"3\",\"sub_index\":0,\"doc_title\":\"0\",\"source\":\"aesia\",\"
id\":\"add8a04b2b13e2fefa2b0ce2beaee88f\",\"doc_date\":\"10 diciembre
2025\",\"unit_type\":\"chapter\",\"unit_title\":\"3. Reglamento de
Inteligencia\",\"file\":\"14-guia-gestion-de-incidentes.pdf\",\"unit_index\":19},\"score\":0.76488
81375789642}]",
"metadata": "{\"k\":5,\"n_docs_retrieved\":5}"
},
{
"id": "3db73a1c-50d3-4f0a-9c50-60dbdec33fc1",
"type": "SPAN",
"name": "retriever.search (3db73a1c)",
"startTime": "2026-03-02T09:49:26.908Z",
"endTime": "2026-03-02T09:49:27.031Z",
"depth": 1,
"input": "{\"args\":[\"EU AI Act Artículos aplicables a sistemas de IA de alto
riesgo\"],\"kwargs\":{\"k\":5,\"mode\":\"soft\"}}",


"output": "[{\"id\":\"737a455bf8c4b4bd15ad3027bef40dbd\",\"text\":\"Ámbito de
aplicación\\n1. El presente Reglamento se aplicará a:\\na)\\nlos proveedores que
introduzcan en el mercado o pongan en servicio sistemas de IA o que introduzcan en el
mercado modelos de IA de uso general en la Unión, con independencia de si dichos
proveedores están establecidos o ubicados en la Unión o en un tercer país;\\nb)\\nlos
responsables del despliegue de sistemas de IA que estén establecidos o ubicados en la
Unión;\\nc)\\nlos proveedores y responsables del despliegue de sistemas de IA que estén
establecidos o ubicados en un tercer país, cuando los resultados de salida generados por el
sistema de IA se utilicen en la Unión;\\nd)\\nlos importadores y distribuidores de sistemas de
IA;\\ne)\\nlos fabricantes de productos que introduzcan en el mercado o pongan en servicio
un sistema de IA junto con su producto y con su propio nombre o marca;\\nf)\\nlos
representantes autorizados de los proveedores que no estén establecidos en la
Unión;\\ng)\\nlas personas afectadas que estén ubicadas en la Unión.\\n2. A los sistemas
de IA clasificados como sistemas de IA de alto riesgo de conformidad con el artículo 6,
apartado 1, y relativos a productos regulados por los actos legislativos de armonización de
la Unión enumerados en la sección B del anexo I, únicamente se les aplicará el artículo 6,
apartado 1, y los artículos 102 a 109 y el artículo 112. El artículo 57 se aplicará únicamente
en la medida en que los requisitos para los sistemas de IA de alto riesgo en virtud del
presente Reglamento se hayan integrado en dichos actos legislativos de armonización de la
Unión.\\n3. El presente Reglamento no se aplicará a los ámbitos que queden fuera del
ámbito de aplicación del Derecho de la Unión y, en cualquier caso, no afectará a las
competencias de los Estados miembros en materia de seguridad nacional,
independientemente del tipo de entidad a la que los Estados miembros hayan
encomendado el desempeño de tareas en relación con dichas
competencias.\",\"metadata\":{\"unit_type\":\"article\",\"unit_index\":2,\"id\":\"737a455bf8c4b4
bd15ad3027bef40dbd\",\"unit_id\":\"2\",\"sub_index\":0,\"unit_title\":\"Artículo
2\",\"source\":\"eu_ai_act\",\"doc_title\":\"L_202401689ES.000101.fmx.xml\",\"doc_date\":\"13
junio
2024\",\"file\":\"EU_AI_Act_2024_1689_ES.html\"},\"distance\":0.23993906378746033},{\"id\"
:\"f017301705f02276959c1fcba419dfc2\",\"text\":\"9\\nA) Sistemas prohibidos: los usos de IA
que se encuentren en este nivel de la jerarquía están\\nprohibidos debido al alto riego que
entrañan: sistemas IA que suponen una amenaza para la\\nseguridad, la vida o los
derechos fundamentales. En este nivel se encuentran, por ejemplo, los\\nsistemas con
alguna de las siguientes funciones:\\n• Manipulación subliminal del comportamiento de una
persona de manera que\\npueda causarle daños físicos o psicológicos a él o a otros.\\n•
Explotación de vulnerabilidades de grupos sociales para manipular su\\ncomportamiento de
forma que pueda causarles daño a ellos o a otros.\\n• Evaluación o clasificación de
personas o grupos por su comportamiento social que\\npueda perjudicarlos
desproporcionadamente en el ámbito del comportamiento\\nobservado, o perjudicarlos en
ámbitos distintos a donde se observó.\\n• Identificación biométrica en tiempo real en
espacios de acceso público para\\nautoridades policiales, salvo casos tasados y mediando
autorización.\\nLa Comisión Europea ha preparado unas directrices con el fin de aclarar la
interpretación de\\nciertos casos concretos (Guidelines on prohibited artificial intelligence
practices established by\\nRegulation (EU) 20241689 (AI Act)) 1.\\nB) Sistemas de Alto
Riesgo: el segundo nivel se reserva a los sistemas de alto riesgo, pero\\ncuyo uso está
permitido, a los que el Reglamento dedica la mayoría de los requisitos y\\nobligaciones que
deben cumplir los distintos roles que participan en la cadena de valor de la\\npuesta en uso
de un sistema IA (operadores). Se dividen en dos tipos de sistemas:\\nB1) Productos o


componentes de seguridad de alto riesgo contemplados en\\nlegislación de
armonización:\\no Sistemas de IA que sea un componente de seguridad de alguno de los
productos\\ncontemplados en la legislación de armonización de la Unión recogidos en el
Anexo\\nI del Reglamento o,\\no Que el propio sistema de IA como producto, deba
someterse a una evaluación de
la\",\"metadata\":{\"file\":\"guia_01_intro_reglamento_ia.pdf\",\"sub_index\":1,\"id\":\"f0173017
05f02276959c1fcba419dfc2\",\"unit_index\":18,\"doc_title\":\"1\",\"source\":\"aesia\",\"unit_typ
e\":\"section\",\"doc_date\":\"10 diciembre 2025\",\"unit_id\":\"2.3\",\"unit_title\":\"2.3 Niveles
de riesgo del Reglamento Europeo de
IA\"},\"distance\":0.23034600913524628},{\"id\":\"193af7ed5209e3ee4aad244c14546876\",\"t
ext\":\"continuo planificado y ejecutado durante todo el ciclo de vida de un sistema\\nAI
Act\\n\\n12\\nde IA de alto riesgo, que requerirá revisiones y actualizaciones
sistemáticas\\nperiódicas. Constará de las siguientes etapas:\\na) la determinación y el
análisis de los riesgos conocidos y previsibles\\nque el sistema de IA de alto riesgo pueda
plantear para la salud, la\\nseguridad o los derechos fundamentales cuando el sistema de IA
de\\nalto riesgo se utilice de conformidad con su finalidad prevista;\\nb) la estimación y la
evaluación de los riesgos que podrían surgir\\ncuando el sistema de IA de alto riesgo se
utilice de conformidad con\\nsu finalidad prevista y cuando se le dé un uso
indebido\\nrazonablemente previsible;\\nc) la evaluación de otros riesgos que podrían surgir,
a partir del análisis\\nde los datos recogidos con el sistema de
vigilancia\\nposcomercialización a que se refiere el artículo 72;\\nd) la adopción de medidas
adecuadas y específicas de gestión de\\nriesgos diseñadas para hacer frente a los riesgos
detectados con\\narreglo a la letra
a).\",\"metadata\":{\"unit_type\":\"chapter\",\"file\":\"05-guia-de-gestion-de-riesgos.pdf\",\"id\":\"
193af7ed5209e3ee4aad244c14546876\",\"source\":\"aesia\",\"unit_title\":\"2. El sistema de
gestión de riesgos se entenderá como un proceso
iterativo\",\"sub_index\":0,\"unit_index\":42,\"doc_date\":\"10 diciembre
2025\",\"unit_id\":\"2\",\"doc_title\":\"0\"},\"distance\":0.23356035351753235},{\"id\":\"8856439
c4e28777c2b9485525355c3e7\",\"text\":\"Artificial\\nLa puesta en servicio o la utilización de
sistemas de IA de alto riesgo debe supeditarse\\nal cumplimiento de determinados
requisitos obligatorios, entre los cuales está el de\\nla gestión de riesgos. Estos requisitos
tienen como objetivo garantizar que los sistemas\\nde IA de alto riesgo disponibles en la
Unión o cuyos resultados de salida se utilicen en la\\nUnión no representen riesgos
inaceptables para intereses públicos importantes\\nreconocidos y protegidos por el Derecho
de la Unión.\\nEn este apartado se incluye los artículos referentes a la generación de la
gestión de riesgos\\ndel Reglamento 2024/1689 del Parlamento Europeo y del Consejo, de
13 de junio de 2024\\n(Reglamento Europeo de Inteligencia Artificial) y se detalla en que
secciones de esta guía\\nse abordan los diferentes elementos de dichos
artículos.\",\"metadata\":{\"source\":\"aesia\",\"sub_index\":0,\"unit_type\":\"chapter\",\"doc_da
te\":\"10 diciembre 2025\",\"unit_title\":\"3. Reglamento de
Inteligencia\",\"unit_id\":\"3\",\"doc_title\":\"0\",\"id\":\"8856439c4e28777c2b9485525355c3e7\
",\"unit_index\":39,\"file\":\"05-guia-de-gestion-de-riesgos.pdf\"},\"distance\":0.233932435512
54272},{\"id\":\"add8a04b2b13e2fefa2b0ce2beaee88f\",\"text\":\"Artificial\\nLa puesta en
servicio o la utilización de sistemas de IA de alto riesgo debe supeditarse\\nal cumplimiento
de determinados requisitos obligatorios, entre los cuales está el de\\nnotificación de
incidentes graves. Estos requisitos tienen como objetivo garantizar que\\nlos sistemas de IA
de alto riesgo disponibles en la Unión o cuyos resultados de salida se\\nutilicen en la Unión
no representen riesgos inaceptables para intereses públicos\\nimportantes reconocidos y


protegidos por el Derecho de la Unión.\\nEn este apartado se incluye los artículos referentes
a la g estión de incidentes graves del\\nReglamento 2024/1689 del Parlamento Europeo y
del Consejo, de 13 de junio de 2024\\n(Reglamento Europeo de Inteligencia Artificial) y se
detalla en que secciones de esta guía\\nse abordan los diferentes elementos de dichos
artículos.\",\"metadata\":{\"unit_id\":\"3\",\"sub_index\":0,\"doc_title\":\"0\",\"source\":\"aesia\",\"
id\":\"add8a04b2b13e2fefa2b0ce2beaee88f\",\"doc_date\":\"10 diciembre
2025\",\"unit_type\":\"chapter\",\"unit_title\":\"3. Reglamento de
Inteligencia\",\"file\":\"14-guia-gestion-de-incidentes.pdf\",\"unit_index\":19},\"distance\":0.235
11186242103577}]",
"metadata":
"{\"mode\":\"soft\",\"k\":5,\"n_results\":5,\"min_distance\":0.2303,\"max_distance\":0.2399}"
},
{
"id": "039c184c-6a85-4056-9ca1-cf113a43348e",
"type": "SPAN",
"name": "rag.grade (039c184c)",
"startTime": "2026-03-02T09:49:27.033Z",
"endTime": "2026-03-02T09:55:25.556Z",
"depth": 0,
"input": "{\"args\":[\"EU AI Act Artículos aplicables a sistemas de IA de alto
riesgo\",[{\"doc\":\"Ámbito de aplicación\\n1. El presente Reglamento se aplicará
a:\\na)\\nlos proveedores que introduzcan en el mercado o pongan en servicio sistemas de
IA o que introduzcan en el mercado modelos de IA de uso general en la Unión, con
independencia de si dichos proveedores están establecidos o ubicados en la Unión o en un
tercer país;\\nb)\\nlos responsables del despliegue de sistemas de IA que estén
establecidos o ubicados en la Unión;\\nc)\\nlos proveedores y responsables del despliegue
de sistemas de IA que estén establecidos o ubicados en un tercer país, cuando los
resultados de salida generados por el sistema de IA se utilicen en la Unión;\\nd)\\nlos
importadores y distribuidores de sistemas de IA;\\ne)\\nlos fabricantes de productos que
introduzcan en el mercado o pongan en servicio un sistema de IA junto con su producto y
con su propio nombre o marca;\\nf)\\nlos representantes autorizados de los proveedores
que no estén establecidos en la Unión;\\ng)\\nlas personas afectadas que estén ubicadas en
la Unión.\\n2. A los sistemas de IA clasificados como sistemas de IA de alto riesgo de
conformidad con el artículo 6, apartado 1, y relativos a productos regulados por los actos
legislativos de armonización de la Unión enumerados en la sección B del anexo I,
únicamente se les aplicará el artículo 6, apartado 1, y los artículos 102 a 109 y el artículo

112. El artículo 57 se aplicará únicamente en la medida en que los requisitos para los
sistemas de IA de alto riesgo en virtud del presente Reglamento se hayan integrado en
dichos actos legislativos de armonización de la Unión.\\n3. El presente Reglamento no se
aplicará a los ámbitos que queden fuera del ámbito de aplicación del Derecho de la Unión y,
en cualquier caso, no afectará a las competencias de los Estados miembros en materia de
seguridad nacional, independientemente del tipo de entidad a la que los Estados miembros
hayan encomendado el desempeño de tareas en relación con dichas
competencias.\",\"metadata\":{\"unit_type\":\"article\",\"unit_index\":2,\"id\":\"737a455bf8c4b4
bd15ad3027bef40dbd\",\"unit_id\":\"2\",\"sub_index\":0,\"unit_title\":\"Artículo
2\",\"source\":\"eu_ai_act\",\"doc_title\":\"L_202401689ES.000101.fmx.xml\",\"doc_date\":\"13
junio
2024\",\"file\":\"EU_AI_Act_2024_1689_ES.html\"},\"score\":0.7600609362125397},{\"doc\":\"


9\\nA) Sistemas prohibidos: los usos de IA que se encuentren en este nivel de la jerarquía
están\\nprohibidos debido al alto riego que entrañan: sistemas IA que suponen una
amenaza para la\\nseguridad, la vida o los derechos fundamentales. En este nivel se
encuentran, por ejemplo, los\\nsistemas con alguna de las siguientes funciones:\\n•
Manipulación subliminal del comportamiento de una persona de manera que\\npueda
causarle daños físicos o psicológicos a él o a otros.\\n• Explotación de vulnerabilidades de
grupos sociales para manipular su\\ncomportamiento de forma que pueda causarles daño a
ellos o a otros.\\n• Evaluación o clasificación de personas o grupos por su comportamiento
social que\\npueda perjudicarlos desproporcionadamente en el ámbito del
comportamiento\\nobservado, o perjudicarlos en ámbitos distintos a donde se observó.\\n•
Identificación biométrica en tiempo real en espacios de acceso público para\\nautoridades
policiales, salvo casos tasados y mediando autorización.\\nLa Comisión Europea ha
preparado unas directrices con el fin de aclarar la interpretación de\\nciertos casos
concretos (Guidelines on prohibited artificial intelligence practices established
by\\nRegulation (EU) 20241689 (AI Act)) 1.\\nB) Sistemas de Alto Riesgo: el segundo nivel
se reserva a los sistemas de alto riesgo, pero\\ncuyo uso está permitido, a los que el
Reglamento dedica la mayoría de los requisitos y\\nobligaciones que deben cumplir los
distintos roles que participan en la cadena de valor de la\\npuesta en uso de un sistema IA
(operadores). Se dividen en dos tipos de sistemas:\\nB1) Productos o componentes de
seguridad de alto riesgo contemplados en\\nlegislación de armonización:\\no Sistemas de IA
que sea un componente de seguridad de alguno de los productos\\ncontemplados en la
legislación de armonización de la Unión recogidos en el Anexo\\nI del Reglamento o,\\no
Que el propio sistema de IA como producto, deba someterse a una evaluación de
la\",\"metadata\":{\"file\":\"guia_01_intro_reglamento_ia.pdf\",\"sub_index\":1,\"id\":\"f0173017
05f02276959c1fcba419dfc2\",\"unit_index\":18,\"doc_title\":\"1\",\"source\":\"aesia\",\"unit_typ
e\":\"section\",\"doc_date\":\"10 diciembre 2025\",\"unit_id\":\"2.3\",\"unit_title\":\"2.3 Niveles
de riesgo del Reglamento Europeo de
IA\"},\"score\":0.7696539908647537},{\"doc\":\"continuo planificado y ejecutado durante todo
el ciclo de vida de un sistema\\nAI Act\\n\\n12\\nde IA de alto riesgo, que requerirá
revisiones y actualizaciones sistemáticas\\nperiódicas. Constará de las siguientes
etapas:\\na) la determinación y el análisis de los riesgos conocidos y previsibles\\nque el
sistema de IA de alto riesgo pueda plantear para la salud, la\\nseguridad o los derechos
fundamentales cuando el sistema de IA de\\nalto riesgo se utilice de conformidad con su
finalidad prevista;\\nb) la estimación y la evaluación de los riesgos que podrían
surgir\\ncuando el sistema de IA de alto riesgo se utilice de conformidad con\\nsu finalidad
prevista y cuando se le dé un uso indebido\\nrazonablemente previsible;\\nc) la evaluación
de otros riesgos que podrían surgir, a partir del análisis\\nde los datos recogidos con el
sistema de vigilancia\\nposcomercialización a que se refiere el artículo 72;\\nd) la adopción
de medidas adecuadas y específicas de gestión de\\nriesgos diseñadas para hacer frente a
los riesgos detectados con\\narreglo a la letra
a).\",\"metadata\":{\"unit_type\":\"chapter\",\"file\":\"05-guia-de-gestion-de-riesgos.pdf\",\"id\":\"
193af7ed5209e3ee4aad244c14546876\",\"source\":\"aesia\",\"unit_title\":\"2. El sistema de
gestión de riesgos se entenderá como un proceso
iterativo\",\"sub_index\":0,\"unit_index\":42,\"doc_date\":\"10 diciembre
2025\",\"unit_id\":\"2\",\"doc_title\":\"0\"},\"score\":0.7664396464824677},{\"doc\":\"Artificial\\nL
a puesta en servicio o la utilización de sistemas de IA de alto riesgo debe supeditarse\\nal
cumplimiento de determinados requisitos obligatorios, entre los cuales está el de\\nla
gestión de riesgos. Estos requisitos tienen como objetivo garantizar que los sistemas\\nde


IA de alto riesgo disponibles en la Unión o cuyos resultados de salida se utilicen en
la\\nUnión no representen riesgos inaceptables para intereses públicos
importantes\\nreconocidos y protegidos por el Derecho de la Unión.\\nEn este apartado se
incluye los artículos referentes a la generación de la gestión de riesgos\\ndel Reglamento
2024/1689 del Parlamento Europeo y del Consejo, de 13 de junio de 2024\\n(Reglamento
Europeo de Inteligencia Artificial) y se detalla en que secciones de esta guía\\nse abordan
los diferentes elementos de dichos
artículos.\",\"metadata\":{\"source\":\"aesia\",\"sub_index\":0,\"unit_type\":\"chapter\",\"doc_da
te\":\"10 diciembre 2025\",\"unit_title\":\"3. Reglamento de
Inteligencia\",\"unit_id\":\"3\",\"doc_title\":\"0\",\"id\":\"8856439c4e28777c2b9485525355c3e7\
",\"unit_index\":39,\"file\":\"05-guia-de-gestion-de-riesgos.pdf\"},\"score\":0.766067564487457
3},{\"doc\":\"Artificial\\nLa puesta en servicio o la utilización de sistemas de IA de alto riesgo
debe supeditarse\\nal cumplimiento de determinados requisitos obligatorios, entre los cuales
está el de\\nnotificación de incidentes graves. Estos requisitos tienen como objetivo
garantizar que\\nlos sistemas de IA de alto riesgo disponibles en la Unión o cuyos
resultados de salida se\\nutilicen en la Unión no representen riesgos inaceptables para
intereses públicos\\nimportantes reconocidos y protegidos por el Derecho de la Unión.\\nEn
este apartado se incluye los artículos referentes a la g estión de incidentes graves
del\\nReglamento 2024/1689 del Parlamento Europeo y del Consejo, de 13 de junio de
2024\\n(Reglamento Europeo de Inteligencia Artificial) y se detalla en que secciones de esta
guía\\nse abordan los diferentes elementos de dichos
artículos.\",\"metadata\":{\"unit_id\":\"3\",\"sub_index\":0,\"doc_title\":\"0\",\"source\":\"aesia\",\"
id\":\"add8a04b2b13e2fefa2b0ce2beaee88f\",\"doc_date\":\"10 diciembre
2025\",\"unit_type\":\"chapter\",\"unit_title\":\"3. Reglamento de
Inteligencia\",\"file\":\"14-guia-gestion-de-incidentes.pdf\",\"unit_index\":19},\"score\":0.76488
81375789642}]],\"kwargs\":{}}",
"output": "[{\"doc\":\"Artificial\\nLa puesta en servicio o la utilización de sistemas de IA de
alto riesgo debe supeditarse\\nal cumplimiento de determinados requisitos obligatorios,
entre los cuales está el de\\nla gestión de riesgos. Estos requisitos tienen como objetivo
garantizar que los sistemas\\nde IA de alto riesgo disponibles en la Unión o cuyos
resultados de salida se utilicen en la\\nUnión no representen riesgos inaceptables para
intereses públicos importantes\\nreconocidos y protegidos por el Derecho de la Unión.\\nEn
este apartado se incluye los artículos referentes a la generación de la gestión de
riesgos\\ndel Reglamento 2024/1689 del Parlamento Europeo y del Consejo, de 13 de junio
de 2024\\n(Reglamento Europeo de Inteligencia Artificial) y se detalla en que secciones de
esta guía\\nse abordan los diferentes elementos de dichos
artículos.\",\"metadata\":{\"source\":\"aesia\",\"sub_index\":0,\"unit_type\":\"chapter\",\"doc_da
te\":\"10 diciembre 2025\",\"unit_title\":\"3. Reglamento de
Inteligencia\",\"unit_id\":\"3\",\"doc_title\":\"0\",\"id\":\"8856439c4e28777c2b9485525355c3e7\
",\"unit_index\":39,\"file\":\"05-guia-de-gestion-de-riesgos.pdf\"},\"score\":0.766067564487457
3}]",
"metadata": "{\"n_docs_in\":5,\"n_relevant\":1,\"method\":\"llm\"}"
},
{
"id": "60fc024f-0891-4d2c-8f27-dcafac1611ee",
"type": "SPAN",
"name": "rag.generate (60fc024f)",
"startTime": "2026-03-02T09:55:25.557Z",


"endTime": "2026-03-02T09:55:27.398Z",
"depth": 0,
"input": "{\"args\":[\"EU AI Act Artículos aplicables a sistemas de IA de alto
riesgo\",[{\"doc\":\"Artificial\\nLa puesta en servicio o la utilización de sistemas de IA de alto
riesgo debe supeditarse\\nal cumplimiento de determinados requisitos obligatorios, entre los
cuales está el de\\nla gestión de riesgos. Estos requisitos tienen como objetivo garantizar
que los sistemas\\nde IA de alto riesgo disponibles en la Unión o cuyos resultados de salida
se utilicen en la\\nUnión no representen riesgos inaceptables para intereses públicos
importantes\\nreconocidos y protegidos por el Derecho de la Unión.\\nEn este apartado se
incluye los artículos referentes a la generación de la gestión de riesgos\\ndel Reglamento
2024/1689 del Parlamento Europeo y del Consejo, de 13 de junio de 2024\\n(Reglamento
Europeo de Inteligencia Artificial) y se detalla en que secciones de esta guía\\nse abordan
los diferentes elementos de dichos
artículos.\",\"metadata\":{\"source\":\"aesia\",\"sub_index\":0,\"unit_type\":\"chapter\",\"doc_da
te\":\"10 diciembre 2025\",\"unit_title\":\"3. Reglamento de
Inteligencia\",\"unit_id\":\"3\",\"doc_title\":\"0\",\"id\":\"8856439c4e28777c2b9485525355c3e7\
",\"unit_index\":39,\"file\":\"05-guia-de-gestion-de-riesgos.pdf\"},\"score\":0.766067564487457
3}]],\"kwargs\":{}}",
"output": "{\"answer\":\"**Respuesta:**\\n\\nLos artículos aplicables a sistemas de IA de
alto riesgo según el EU AI Act (Reglamento Europeo de Inteligencia Artificial) se encuentran
en el Reglamento 2024/1689 del Parlamento Europeo y del Consejo, de 13 de junio de

2024. A continuación, se detallan los artículos específicos que abordan los requisitos
obligatorios para la puesta en servicio o la utilización de sistemas de IA de alto
riesgo:\\n\\n1. **Artículo 6: Sistemas de IA de alto riesgo**\\n - Este artículo define qué
sistemas de IA se consideran de alto riesgo y establece que su puesta en servicio o
utilización debe supeditarse a determinados requisitos obligatorios.\\n\\n2. **Artículo 7:
Requisitos de los sistemas de IA de alto riesgo**\\n - Este artículo detalla los requisitos
obligatorios que deben cumplir los sistemas de IA de alto riesgo, incluyendo la gestión de
riesgos.\\n\\n3. **Artículo 8: Gestión de riesgos**\\n - Este artículo se centra en los
requisitos específicos para la gestión de riesgos de los sistemas de IA de alto riesgo, con el
objetivo de garantizar que no representen riesgos inaceptables para intereses públicos
importantes reconocidos y protegidos por el Derecho de la Unión.\\n\\nEstos artículos tienen
como objetivo garantizar que los sistemas de IA de alto riesgo disponibles en la Unión o
cuyos resultados de salida se utilicen en la Unión no representen riesgos inaceptables para
intereses públicos importantes reconocidos y protegidos por el Derecho de la
Unión.\\n\\n**Fuentes:**\\n- Reglamento 2024/1689 del Parlamento Europeo y del Consejo,
de 13 de junio de 2024 (Reglamento Europeo de Inteligencia Artificial), Artículos 6, 7 y
8.\\n\\n_Informe preliminar generado por IA. Consulte profesional
jurídico._\",\"sources\":[{\"source\":\"aesia\",\"sub_index\":0,\"unit_type\":\"chapter\",\"doc_dat
e\":\"10 diciembre 2025\",\"unit_title\":\"3. Reglamento de
Inteligencia\",\"unit_id\":\"3\",\"doc_title\":\"0\",\"id\":\"8856439c4e28777c2b9485525355c3e7\
",\"unit_index\":39,\"file\":\"05-guia-de-gestion-de-riesgos.pdf\"}],\"grounded\":true}",
"metadata": "{\"n_context_docs\":1,\"grounded\":true}"
}
]


###### Análisis de Code Claude

**Pipeline: generate_report — FUNCIONAL** ✓

Total: **~4.6 segundos**. Sin Ollama involucrado (no hay RAG en Q3).

**Spans Langfuse (Q3 real)**

09:48:14.159 classifier.predict_risk [67a34319] 15ms ← Tool: classify_risk
09:48:15.394 classifier.predict_risk [5af1edb9] 17ms ← Tool: generate_report (interno)
09:48:15.412 retriever.search [0b220545] 134ms
09:48:15.547 report.generate [155f2083] 3.2s

**BUG — Doble llamada al clasificador**

El agente ReAct llamó primero a classify_risk y luego a generate_report, que internamente
también llama a predict_risk. Mismo input, mismo output, dos veces. El PR #90
(fix/bug-doble-llamada-clasificador) está en el historial de la rama pero el bug sigue presente
en la imagen develop.

**Retrieval del informe —** ⚠ **Cobertura insuficiente**

Query: "obligaciones sistemas de riesgo alto_riesgo EU AI Act" con **k=3**

```
Doc recuperado Distancia Problema
EU AI Act Art. 47 (Declaración
conformidad)
```
```
0.2522 Solo una obligación
```
```
AESIA guía 2.3 (Niveles de riesgo) 0.2326 Guía interpretativa, no normativa
AESIA guía 5.2 (Entidades financieras) 0.2405 Solo menciona "reducir carga
administrativa"
```
Con k=3 y esta query no se recuperaron los artículos clave (Art. 9, 10, 13, 14, 15). El informe cubre
**solo Art. 47** cuando debería cubrir 6-7 artículos para un sistema de scoring crediticio.

**Calidad del informe**

**Lo que sale en Langfuse vs UI:**
El report.generate interno produce la referencia "artículo 2.3 del Reglamento Europeo de IA
(aeisa)" en la sección de clasificación. La UI muestra "Anexo III cat. 5.b del Reglamento
Europeo de IA (EU AI Act)" — el orquestador lo corrigió al sintetizar usando el resultado del
classify_risk previo. Comportamiento correcto del agente, pero frágil: depende de que el doble-call
ocurra.
**La guía AESIA aparece en "Citas Legales":**
"aeisa — 2.3 Niveles de riesgo del Reglamento Europeo de IA"


Material orientativo citado como fuente normativa.

**Mismo bug annex3_override (igual que Q2)**

"risk_level": "alto_riesgo",
"probabilities": { "inaceptable": 0.9865 }, ← contradicción
"shap_explanation": "Factores principales para 'inaceptable'" ← clase incorrecta

**Resumen Q3**

```
Métrica Valor Estado
Latencia total 4.6s ✓ Buena
Double call clasificador sí ⚠ Bug
Estructura del informe 5 secciones ✓
Art. EU AI Act reales recuperados 1 (Art. 47) ⚠ Insuficiente
k en retrieval 3 ⚠ Bajo
AESIA citada como fuente normativa sí ⚠
Disclaimer presente ✓
grounded true ✓
annex3_override bug presente ⚠
```
### Query 4

###### Input en chat UI

Tengo un sistema de IA que evalúa el riesgo de recidiva de presos para recomendar libertad
condicional. Clasifícalo, busca los artículos aplicables y genera un informe de cumplimiento.

###### Output en chat UI

## Informe de Cumplimiento del Sistema

## de IA

#### Resumen Ejecutivo

El sistema descrito es un sistema de IA que evalúa el riesgo de recidiva de presos
para recomendar libertad condicional. Este sistema ha sido clasificado como de alto
riesgo debido a las implicaciones significativas que tiene en la vida de las personas


evaluadas. En este informe se analiza su contexto regulatorio y se detallan las
obligaciones y requisitos legales aplicables según la normativa de la Unión Europea.

#### Clasificación de Riesgo

El sistema ha sido clasificado como de alto riesgo según el Anexo III cat. 6 del EU AI
Act. Este nivel de riesgo se justifica por la naturaleza crítica de las decisiones que el
sistema puede influir, las cuales pueden tener un impacto significativo en la vida y
los derechos fundamentales de los individuos.

#### Obligaciones Aplicables

Según el EU AI Act, los sistemas de alto riesgo están sujetos a los siguientes
requisitos:

1. Declaración UE de Conformidad (eu_ai_act — Artículo 47):
    ○ El proveedor debe redactar una declaración UE de conformidad
       por escrito en un formato legible por máquina, con firma
       electrónica o manuscrita, para cada sistema de IA de alto riesgo.
    ○ La declaración debe especificar el sistema de IA de alto riesgo
       para el que ha sido redactada y se mantendrá a disposición de
       las autoridades nacionales competentes durante un período de
       diez años.
    ○ La declaración contendrá toda la información necesaria para
       determinar el cumplimiento de los requisitos establecidos en la
       sección 2 del Reglamento Europeo de IA.
    ○ El proveedor asumirá la responsabilidad del cumplimiento de los
       requisitos establecidos en la sección 2.

#### Citas Legales

```
● eu_ai_act — Artículo 47: Declaración UE de conformidad.
● Anexo III cat. 6: Clasificación de sistemas de alto riesgo.
```
#### Recomendaciones

1. Redactar Declaración UE de Conformidad: El proveedor debe redactar y
    mantener actualizada la declaración UE de conformidad para el sistema de
    IA.
2. Garantizar Disponibilidad: Asegurar que la declaración esté disponible para
    las autoridades nacionales competentes durante el período requerido.
3. Cumplimiento de Requisitos: Asegurar que el sistema cumple con todos
    los requisitos establecidos en la normativa aplicable, especialmente en la
    sección 2 del Reglamento Europeo de IA.


Este informe se basa exclusivamente en las citas legales proporcionadas y no
incluye contenido inventado.

_Informe preliminar generado por IA. Consulte profesional jurídico._

###### Salida en docker logs

time=2026-03-02T09:49:27.199Z level=WARN source=cpu_linux.go:130 msg="failed to
parse CPU allowed micro secs" error="strconv.ParseInt: parsing \"max\": invalid syntax"
llama_model_loader: loaded meta data with 35 key-value pairs and 434 tensors from
/home/appuser/.ollama/models/blobs/sha256-5ee4f07cdb9beadbbb293e85803c569b01bd37
ed059d2715faa7bb405f31caa6 (version GGUF V3 (latest))
llama_model_loader: Dumping metadata keys/values. Note: KV overrides do not apply in
this output.
llama_model_loader: - kv 0: general.architecture str = qwen2
llama_model_loader: - kv 1: general.type str = model
llama_model_loader: - kv 2: general.name str = Qwen2.5 3B
Instruct
llama_model_loader: - kv 3: general.finetune str = Instruct
llama_model_loader: - kv 4: general.basename str = Qwen2.5
llama_model_loader: - kv 5: general.size_label str = 3B
llama_model_loader: - kv 6: general.license str = other
llama_model_loader: - kv 7: general.license.name str =
qwen-research
llama_model_loader: - kv 8: general.license.link str =
https://huggingface.co/Qwen/Qwen2.5-3...
llama_model_loader: - kv 9: general.base_model.count u32 = 1
llama_model_loader: - kv 10: general.base_model.0.name str = Qwen2.5
3B
llama_model_loader: - kv 11: general.base_model.0.organization str = Qwen
llama_model_loader: - kv 12: general.base_model.0.repo_url str =
https://huggingface.co/Qwen/Qwen2.5-3B
llama_model_loader: - kv 13: general.tags arr[str,2] = ["chat",
"text-generation"]
llama_model_loader: - kv 14: general.languages arr[str,1] = ["en"]
llama_model_loader: - kv 15: qwen2.block_count u32 = 36
llama_model_loader: - kv 16: qwen2.context_length u32 = 32768
llama_model_loader: - kv 17: qwen2.embedding_length u32 = 2048
llama_model_loader: - kv 18: qwen2.feed_forward_length u32 = 11008
llama_model_loader: - kv 19: qwen2.attention.head_count u32 = 16
llama_model_loader: - kv 20: qwen2.attention.head_count_kv u32 = 2
llama_model_loader: - kv 21: qwen2.rope.freq_base f32 =
1000000.000000
llama_model_loader: - kv 22: qwen2.attention.layer_norm_rms_epsilon f32 =
0.000001
llama_model_loader: - kv 23: general.file_type u32 = 15


llama_model_loader: - kv 24: tokenizer.ggml.model str = gpt2
llama_model_loader: - kv 25: tokenizer.ggml.pre str = qwen2
llama_model_loader: - kv 26: tokenizer.ggml.tokens arr[str,151936] = ["!", "\"",
"#", "$", "%", "&", "'", ...
llama_model_loader: - kv 27: tokenizer.ggml.token_type arr[i32,151936] = [1, 1,
1, 1, 1, 1, 1, 1, 1, 1, 1, 1, ...
llama_model_loader: - kv 28: tokenizer.ggml.merges arr[str,151387] = ["Ġ Ġ",
"ĠĠ ĠĠ", "i n", "Ġ t",...
llama_model_loader: - kv 29: tokenizer.ggml.eos_token_id u32 = 151645
llama_model_loader: - kv 30: tokenizer.ggml.padding_token_id u32 =
151643
llama_model_loader: - kv 31: tokenizer.ggml.bos_token_id u32 = 151643
llama_model_loader: - kv 32: tokenizer.ggml.add_bos_token bool = false
llama_model_loader: - kv 33: tokenizer.chat_template str = {%- if tools
%}\n {{- '<|im_start|>...
llama_model_loader: - kv 34: general.quantization_version u32 = 2
llama_model_loader: - type f32: 181 tensors
llama_model_loader: - type q4_K: 216 tensors
llama_model_loader: - type q6_K: 37 tensors
print_info: file format = GGUF V3 (latest)
print_info: file type = Q4_K - Medium
print_info: file size = 1.79 GiB (4.99 BPW)
load: printing all EOG tokens:
load: - 151643 ('<|endoftext|>')
load: - 151645 ('<|im_end|>')
load: - 151662 ('<|fim_pad|>')
load: - 151663 ('<|repo_name|>')
load: - 151664 ('<|file_sep|>')
load: special tokens cache size = 22
load: token to piece cache size = 0.9310 MB
print_info: arch = qwen2
print_info: vocab_only = 1
print_info: no_alloc = 0
print_info: model type = ?B
print_info: model params = 3.09 B
print_info: general.name = Qwen2.5 3B Instruct
print_info: vocab type = BPE
print_info: n_vocab = 151936
print_info: n_merges = 151387
print_info: BOS token = 151643 '<|endoftext|>'
print_info: EOS token = 151645 '<|im_end|>'
print_info: EOT token = 151645 '<|im_end|>'
print_info: PAD token = 151643 '<|endoftext|>'
print_info: LF token = 198 'Ċ'
print_info: FIM PRE token = 151659 '<|fim_prefix|>'
print_info: FIM SUF token = 151661 '<|fim_suffix|>'
print_info: FIM MID token = 151660 '<|fim_middle|>'
print_info: FIM PAD token = 151662 '<|fim_pad|>'


print_info: FIM REP token = 151663 '<|repo_name|>'
print_info: FIM SEP token = 151664 '<|file_sep|>'
print_info: EOG token = 151643 '<|endoftext|>'
print_info: EOG token = 151645 '<|im_end|>'
print_info: EOG token = 151662 '<|fim_pad|>'
print_info: EOG token = 151663 '<|repo_name|>'
print_info: EOG token = 151664 '<|file_sep|>'
print_info: max token length = 256
llama_model_load: vocab only - skipping tensors
time=2026-03-02T09:49:27.638Z level=INFO source=server.go:431 msg="starting runner"
cmd="/usr/local/bin/ollama runner --model
/home/appuser/.ollama/models/blobs/sha256-5ee4f07cdb9beadbbb293e85803c569b01bd37
ed059d2715faa7bb405f31caa6 --port 40671"
time=2026-03-02T09:49:27.639Z level=INFO source=sched.go:491 msg="system memory"
total="7.6 GiB" free="4.4 GiB" free_swap="0 B"
time=2026-03-02T09:49:27.639Z level=INFO source=server.go:498 msg="loading model"
"model layers"=37 requested=-1
time=2026-03-02T09:49:27.640Z level=INFO source=device.go:245 msg="model weights"
device=CPU size="1.8 GiB"
time=2026-03-02T09:49:27.640Z level=INFO source=device.go:256 msg="kv cache"
device=CPU size="144.0 MiB"
time=2026-03-02T09:49:27.640Z level=INFO source=device.go:272 msg="total memory"
size="1.9 GiB"
time=2026-03-02T09:49:27.658Z level=INFO source=runner.go:965 msg="starting go
runner"
load_backend: loaded CPU backend from /usr/local/lib/ollama/libggml-cpu-skylakex.so
time=2026-03-02T09:49:27.669Z level=INFO source=ggml.go:104 msg=system
CPU.0.SSE3=1 CPU.0.SSSE3=1 CPU.0.AVX=1 CPU.0.AVX2=1 CPU.0.F16C=1
CPU.0.FMA=1 CPU.0.BMI2=1 CPU.0.AVX512=1 CPU.0.LLAMAFILE=1
CPU.1.LLAMAFILE=1 compiler=cgo(gcc)
time=2026-03-02T09:49:27.670Z level=INFO source=runner.go:1001 msg="Server listening
on 127.0.0.1:40671"
time=2026-03-02T09:49:27.673Z level=INFO source=runner.go:895 msg=load
request="{Operation:commit LoraPath:[] Parallel:1 BatchSize:512 FlashAttention:Auto
KvSize:4096 KvCacheType: NumThreads:1 GPULayers:[] MultiUserCache:false
ProjectorPath: MainGPU:0 UseMmap:false}"
time=2026-03-02T09:49:27.674Z level=INFO source=server.go:1350 msg="waiting for llama
runner to start responding"
time=2026-03-02T09:49:27.675Z level=INFO source=server.go:1384 msg="waiting for
server to become available" status="llm server loading model"
llama_model_loader: loaded meta data with 35 key-value pairs and 434 tensors from
/home/appuser/.ollama/models/blobs/sha256-5ee4f07cdb9beadbbb293e85803c569b01bd37
ed059d2715faa7bb405f31caa6 (version GGUF V3 (latest))
llama_model_loader: Dumping metadata keys/values. Note: KV overrides do not apply in
this output.
llama_model_loader: - kv 0: general.architecture str = qwen2
llama_model_loader: - kv 1: general.type str = model


llama_model_loader: - kv 2: general.name str = Qwen2.5 3B
Instruct
llama_model_loader: - kv 3: general.finetune str = Instruct
llama_model_loader: - kv 4: general.basename str = Qwen2.5
llama_model_loader: - kv 5: general.size_label str = 3B
llama_model_loader: - kv 6: general.license str = other
llama_model_loader: - kv 7: general.license.name str =
qwen-research
llama_model_loader: - kv 8: general.license.link str =
https://huggingface.co/Qwen/Qwen2.5-3...
llama_model_loader: - kv 9: general.base_model.count u32 = 1
llama_model_loader: - kv 10: general.base_model.0.name str = Qwen2.5
3B
llama_model_loader: - kv 11: general.base_model.0.organization str = Qwen
llama_model_loader: - kv 12: general.base_model.0.repo_url str =
https://huggingface.co/Qwen/Qwen2.5-3B
llama_model_loader: - kv 13: general.tags arr[str,2] = ["chat",
"text-generation"]
llama_model_loader: - kv 14: general.languages arr[str,1] = ["en"]
llama_model_loader: - kv 15: qwen2.block_count u32 = 36
llama_model_loader: - kv 16: qwen2.context_length u32 = 32768
llama_model_loader: - kv 17: qwen2.embedding_length u32 = 2048
llama_model_loader: - kv 18: qwen2.feed_forward_length u32 = 11008
llama_model_loader: - kv 19: qwen2.attention.head_count u32 = 16
llama_model_loader: - kv 20: qwen2.attention.head_count_kv u32 = 2
llama_model_loader: - kv 21: qwen2.rope.freq_base f32 =
1000000.000000
llama_model_loader: - kv 22: qwen2.attention.layer_norm_rms_epsilon f32 =
0.000001
llama_model_loader: - kv 23: general.file_type u32 = 15
llama_model_loader: - kv 24: tokenizer.ggml.model str = gpt2
llama_model_loader: - kv 25: tokenizer.ggml.pre str = qwen2
llama_model_loader: - kv 26: tokenizer.ggml.tokens arr[str,151936] = ["!", "\"",
"#", "$", "%", "&", "'", ...
llama_model_loader: - kv 27: tokenizer.ggml.token_type arr[i32,151936] = [1, 1,
1, 1, 1, 1, 1, 1, 1, 1, 1, 1, ...
llama_model_loader: - kv 28: tokenizer.ggml.merges arr[str,151387] = ["Ġ Ġ",
"ĠĠ ĠĠ", "i n", "Ġ t",...
llama_model_loader: - kv 29: tokenizer.ggml.eos_token_id u32 = 151645
llama_model_loader: - kv 30: tokenizer.ggml.padding_token_id u32 =
151643
llama_model_loader: - kv 31: tokenizer.ggml.bos_token_id u32 = 151643
llama_model_loader: - kv 32: tokenizer.ggml.add_bos_token bool = false
llama_model_loader: - kv 33: tokenizer.chat_template str = {%- if tools
%}\n {{- '<|im_start|>...
llama_model_loader: - kv 34: general.quantization_version u32 = 2
llama_model_loader: - type f32: 181 tensors
llama_model_loader: - type q4_K: 216 tensors


llama_model_loader: - type q6_K: 37 tensors
print_info: file format = GGUF V3 (latest)
print_info: file type = Q4_K - Medium
print_info: file size = 1.79 GiB (4.99 BPW)
load: printing all EOG tokens:
load: - 151643 ('<|endoftext|>')
load: - 151645 ('<|im_end|>')
load: - 151662 ('<|fim_pad|>')
load: - 151663 ('<|repo_name|>')
load: - 151664 ('<|file_sep|>')
load: special tokens cache size = 22
load: token to piece cache size = 0.9310 MB
print_info: arch = qwen2
print_info: vocab_only = 0
print_info: no_alloc = 0
print_info: n_ctx_train = 32768
print_info: n_embd = 2048
print_info: n_embd_inp = 2048
print_info: n_layer = 36
print_info: n_head = 16
print_info: n_head_kv = 2
print_info: n_rot = 128
print_info: n_swa = 0
print_info: is_swa_any = 0
print_info: n_embd_head_k = 128
print_info: n_embd_head_v = 128
print_info: n_gqa = 8
print_info: n_embd_k_gqa = 256
print_info: n_embd_v_gqa = 256
print_info: f_norm_eps = 0.0e+00
print_info: f_norm_rms_eps = 1.0e-06
print_info: f_clamp_kqv = 0.0e+00
print_info: f_max_alibi_bias = 0.0e+00
print_info: f_logit_scale = 0.0e+00
print_info: f_attn_scale = 0.0e+00
print_info: n_ff = 11008
print_info: n_expert = 0
print_info: n_expert_used = 0
print_info: n_expert_groups = 0
print_info: n_group_used = 0
print_info: causal attn = 1
print_info: pooling type = -1
print_info: rope type = 2
print_info: rope scaling = linear
print_info: freq_base_train = 1000000.0
print_info: freq_scale_train = 1
print_info: n_ctx_orig_yarn = 32768
print_info: rope_yarn_log_mul= 0.0000


print_info: rope_finetuned = unknown
print_info: model type = 3B
print_info: model params = 3.09 B
print_info: general.name = Qwen2.5 3B Instruct
print_info: vocab type = BPE
print_info: n_vocab = 151936
print_info: n_merges = 151387
print_info: BOS token = 151643 '<|endoftext|>'
print_info: EOS token = 151645 '<|im_end|>'
print_info: EOT token = 151645 '<|im_end|>'
print_info: PAD token = 151643 '<|endoftext|>'
print_info: LF token = 198 'Ċ'
print_info: FIM PRE token = 151659 '<|fim_prefix|>'
print_info: FIM SUF token = 151661 '<|fim_suffix|>'
print_info: FIM MID token = 151660 '<|fim_middle|>'
print_info: FIM PAD token = 151662 '<|fim_pad|>'
print_info: FIM REP token = 151663 '<|repo_name|>'
print_info: FIM SEP token = 151664 '<|file_sep|>'
print_info: EOG token = 151643 '<|endoftext|>'
print_info: EOG token = 151645 '<|im_end|>'
print_info: EOG token = 151662 '<|fim_pad|>'
print_info: EOG token = 151663 '<|repo_name|>'
print_info: EOG token = 151664 '<|file_sep|>'
print_info: max token length = 256
load_tensors: loading model tensors, this can take a while... (mmap = false)
load_tensors: CPU model buffer size = 1834.82 MiB
llama_context: constructing llama_context
llama_context: n_seq_max = 1
llama_context: n_ctx = 4096
llama_context: n_ctx_seq = 4096
llama_context: n_batch = 512
llama_context: n_ubatch = 512
llama_context: causal_attn = 1
llama_context: flash_attn = auto
llama_context: kv_unified = false
llama_context: freq_base = 1000000.0
llama_context: freq_scale = 1
llama_context: n_ctx_seq (4096) < n_ctx_train (32768) -- the full capacity of the model will
not be utilized
llama_context: CPU output buffer size = 0.59 MiB
llama_kv_cache: CPU KV buffer size = 144.00 MiB
llama_kv_cache: size = 144.00 MiB ( 4096 cells, 36 layers, 1/1 seqs), K (f16): 72.00 MiB,
V (f16): 72.00 MiB
llama_context: Flash Attention was auto, set to enabled
llama_context: CPU compute buffer size = 304.75 MiB
llama_context: graph nodes = 1231
llama_context: graph splits = 1


time=2026-03-02T09:49:37.970Z level=INFO source=server.go:1388 msg="llama runner
started in 10.33 seconds"
time=2026-03-02T09:49:37.970Z level=INFO source=sched.go:566 msg="loaded runners"
count=1
time=2026-03-02T09:49:37.970Z level=INFO source=server.go:1350 msg="waiting for llama
runner to start responding"
time=2026-03-02T09:49:37.971Z level=INFO source=server.go:1388 msg="llama runner
started in 10.33 seconds"
[GIN] 2026/03/02 - 09:51:29 | 200 | 2m2s | 127.0.0.1 | POST "/api/chat"
[GIN] 2026/03/02 - 09:53:07 | 200 | 1m37s | 127.0.0.1 | POST "/api/chat"
[GIN] 2026/03/02 - 09:54:01 | 200 | 54.623319933s | 127.0.0.1 | POST "/api/chat"
[GIN] 2026/03/02 - 09:54:47 | 200 | 45.55384003s | 127.0.0.1 | POST "/api/chat"
[GIN] 2026/03/02 - 09:55:25 | 200 | 38.121144246s | 127.0.0.1 | POST "/api/chat"

###### Logs de langfuse en JSON

[
{
"id": "de6e129b-f2a3-498e-8693-b1c003c54d86",
"type": "SPAN",
"name": "classifier.predict_risk (de6e129b)",
"startTime": "2026-03-02T09:55:28.151Z",
"endTime": "2026-03-02T09:55:28.167Z",
"depth": 0,
"input": "{\"args\":[\"Sistema de IA que evalúa el riesgo de recidiva de presos para
recomendar libertad condicional\"],\"kwargs\":{}}",
"output":
"{\"risk_level\":\"alto_riesgo\",\"confidence\":0.85,\"probabilities\":{\"inaceptable\":0.9922,\"alto
\":0.0073,\"limitado\":0.0002,\"mínimo\":0.0003},\"shap_top_features\":[{\"feature\":\"num_pal
abras\",\"contribution\":1.0230586528778076},{\"feature\":\"svd_24\",\"contribution\":0.93559
78965759277},{\"feature\":\"svd_30\",\"contribution\":0.6751113533973694},{\"feature\":\"svd
_32\",\"contribution\":0.5668127536773682},{\"feature\":\"svd_2\",\"contribution\":0.52756577
73017883}],\"shap_explanation\":\"Factores principales para 'inaceptable': num_palabras,
svd_24, svd_30.\",\"annex3_override\":true,\"annex3_ref\":\"Anexo III cat.
6\",\"ml_prediction\":{\"risk_level\":\"inaceptable\",\"confidence\":0.992236316204071}}",
"metadata":
"{\"risk_level\":\"alto_riesgo\",\"confidence\":0.85,\"probabilities\":{\"inaceptable\":0.9922,\"alto
\":0.0073,\"limitado\":0.0002,\"mínimo\":0.0003}}"
},
{
"id": "66138a36-39ff-4ac8-a1a8-77b77fd74060",
"type": "SPAN",
"name": "retriever.search (66138a36)",
"startTime": "2026-03-02T09:55:28.167Z",
"endTime": "2026-03-02T09:55:28.288Z",
"depth": 0,
"input": "{\"args\":[\"obligaciones sistemas de riesgo alto_riesgo EU AI
Act\"],\"kwargs\":{\"k\":3}}",


"output": "[{\"id\":\"a587c0d87b3fb344a83171186e4378ce\",\"text\":\"Declaración UE de
conformidad\\n1. El proveedor redactará una declaración UE de conformidad por escrito en
un formato legible por máquina, con firma electrónica o manuscrita, para cada sistema de IA
de alto riesgo y la mantendrá a disposición de las autoridades nacionales competentes
durante un período de diez años a contar desde la introducción del sistema de IA de alto
riesgo en el mercado o su puesta en servicio. En la declaración UE de conformidad se
especificará el sistema de IA de alto riesgo para el que ha sido redactada. Se entregará una
copia de la declaración UE de conformidad a las autoridades nacionales competentes
pertinentes que lo soliciten.\\n2. En la declaración UE de conformidad constará que el
sistema de IA de alto riesgo de que se trate cumple los requisitos establecidos en la sección

2. La declaración UE de conformidad contendrá la información indicada en el anexo V y se
traducirá a una lengua que puedan entender fácilmente las autoridades nacionales
competentes del Estado o Estados miembros en que se introduzca en el mercado o
comercialice el sistema de IA de alto riesgo.\\n3. Cuando los sistemas de IA de alto riesgo
estén sujetos a otros actos legislativos de armonización de la Unión que también exijan una
declaración UE de conformidad, se elaborará una única declaración UE de conformidad con
respecto a todos el Derecho de la Unión aplicable al sistema de IA de alto riesgo. La
declaración contendrá toda la información necesaria para determinar los actos legislativos
de armonización de la Unión a los que se refiere la declaración.\\n4. Al elaborar la
declaración UE de conformidad, el proveedor asumirá la responsabilidad del cumplimiento
de los requisitos establecidos en la sección 2. El proveedor mantendrá actualizada la
declaración UE de conformidad según
proceda.\",\"metadata\":{\"source\":\"eu_ai_act\",\"doc_date\":\"13 junio
2024\",\"unit_type\":\"article\",\"unit_index\":54,\"file\":\"EU_AI_Act_2024_1689_ES.html\",\"u
nit_id\":\"47\",\"unit_title\":\"Artículo
47\",\"id\":\"a587c0d87b3fb344a83171186e4378ce\",\"doc_title\":\"L_202401689ES.000101.f
mx.xml\",\"sub_index\":0},\"distance\":0.2521938681602478},{\"id\":\"f017301705f02276959c
1fcba419dfc2\",\"text\":\"9\\nA) Sistemas prohibidos: los usos de IA que se encuentren en
este nivel de la jerarquía están\\nprohibidos debido al alto riego que entrañan: sistemas IA
que suponen una amenaza para la\\nseguridad, la vida o los derechos fundamentales. En
este nivel se encuentran, por ejemplo, los\\nsistemas con alguna de las siguientes
funciones:\\n• Manipulación subliminal del comportamiento de una persona de manera
que\\npueda causarle daños físicos o psicológicos a él o a otros.\\n• Explotación de
vulnerabilidades de grupos sociales para manipular su\\ncomportamiento de forma que
pueda causarles daño a ellos o a otros.\\n• Evaluación o clasificación de personas o grupos
por su comportamiento social que\\npueda perjudicarlos desproporcionadamente en el
ámbito del comportamiento\\nobservado, o perjudicarlos en ámbitos distintos a donde se
observó.\\n• Identificación biométrica en tiempo real en espacios de acceso público
para\\nautoridades policiales, salvo casos tasados y mediando autorización.\\nLa Comisión
Europea ha preparado unas directrices con el fin de aclarar la interpretación de\\nciertos
casos concretos (Guidelines on prohibited artificial intelligence practices established
by\\nRegulation (EU) 20241689 (AI Act)) 1.\\nB) Sistemas de Alto Riesgo: el segundo nivel
se reserva a los sistemas de alto riesgo, pero\\ncuyo uso está permitido, a los que el
Reglamento dedica la mayoría de los requisitos y\\nobligaciones que deben cumplir los
distintos roles que participan en la cadena de valor de la\\npuesta en uso de un sistema IA
(operadores). Se dividen en dos tipos de sistemas:\\nB1) Productos o componentes de
seguridad de alto riesgo contemplados en\\nlegislación de armonización:\\no Sistemas de IA
que sea un componente de seguridad de alguno de los productos\\ncontemplados en la


legislación de armonización de la Unión recogidos en el Anexo\\nI del Reglamento o,\\no
Que el propio sistema de IA como producto, deba someterse a una evaluación de
la\",\"metadata\":{\"doc_date\":\"10 diciembre
2025\",\"file\":\"guia_01_intro_reglamento_ia.pdf\",\"sub_index\":1,\"unit_type\":\"section\",\"u
nit_title\":\"2.3 Niveles de riesgo del Reglamento Europeo de
IA\",\"unit_id\":\"2.3\",\"doc_title\":\"1\",\"unit_index\":18,\"id\":\"f017301705f02276959c1fcba4
19dfc2\",\"source\":\"aesia\"},\"distance\":0.23257572948932648},{\"id\":\"45752f0ccbff08306f
afbdbb3920bc3e\",\"text\":\"cumplir con los nuevos requisitos regulatorios. En resumen, el
objetivo del texto es\\ngarantizar la regulación de la IA de alto riesgo en la UE, reduciendo la
carga administrativa\\ny de costos para los proveedores, al mismo tiempo que se asegura la
protección y\\nseguridad del responsable del despliegue final.\\nAI
Act\",\"metadata\":{\"file\":\"04-guia-del-sistema-de-gestion-de-la-calidad.pdf\",\"doc_title\":\"0\
",\"doc_date\":\"10 diciembre 2025\",\"sub_index\":1,\"unit_type\":\"section\",\"unit_title\":\"5.2
Entidades financieras y p roveedores sujetos a
legislación\",\"id\":\"45752f0ccbff08306fafbdbb3920bc3e\",\"unit_id\":\"5.2\",\"unit_index\":55,\
"source\":\"aesia\"},\"distance\":0.24050918221473694}]",
"metadata":
"{\"mode\":\"soft\",\"k\":3,\"n_results\":3,\"min_distance\":0.2326,\"max_distance\":0.2522}"
},
{
"id": "43f3e93e-5c84-49ca-b809-91e3d8582ac7",
"type": "SPAN",
"name": "report.generate (43f3e93e)",
"startTime": "2026-03-02T09:55:28.288Z",
"endTime": "2026-03-02T09:55:31.177Z",
"depth": 0,
"input": "{\"args\":[\"Sistema de IA que evalúa el riesgo de recidiva de presos para
recomendar libertad condicional\",\"alto_riesgo\",[\"eu_ai_act — Artículo 47\\nDeclaración
UE de conformidad\\n1. El proveedor redactará una declaración UE de conformidad por
escrito en un formato legible por máquina, con firma electrónica o manuscrita, para cada
sistema de IA de alto riesgo y la mantendrá a disposición de las autoridades nacionales
competentes durante un período de diez años a contar desde la introducción del sistema de
IA de alto riesgo en el mercado o su puesta en servicio. En la declaración UE de
conformidad se especificará el sistema de IA de alto riesgo para el que ha sido redactada.
Se entregará una copia de la declaración UE de conformidad a las autoridades nacionales
competentes pertinentes que lo soliciten.\\n2. En la declaración UE de conformidad
constará que el sistema de IA de alto riesgo de que se trate cumple los requisitos
establecidos en la sección 2. La declaración UE de conformidad contendrá la información
indicada en el anexo V y se traducirá a una lengua que puedan entender fácilmente las
autoridades nacionales competentes del Estado o Estados miembros en que se introduzca
en el mercado o comercialice el sistema de IA de alto riesgo.\\n3. Cuando los sistemas de
IA de alto riesgo estén sujetos a otros actos legislativos de armonización de la Unión que
también exijan una declaración UE de conformidad, se elaborará una única declaración UE
de conformidad con respecto a todos el Derecho de la Unión aplicable al sistema de IA de
alto riesgo. La declaración contendrá toda la información necesaria para determinar los
actos legislativos de armonización de la Unión a los que se refiere la declaración.\\n4. Al
elaborar la declaración UE de conformidad, el proveedor asumirá la responsabilidad del
cumplimiento de los requisitos establecidos en la sección 2. El proveedor mantendrá


actualizada la declaración UE de conformidad según proceda.\",\"aesia — 2.3 Niveles de
riesgo del Reglamento Europeo de IA\\n9\\nA) Sistemas prohibidos: los usos de IA que se
encuentren en este nivel de la jerarquía están\\nprohibidos debido al alto riego que
entrañan: sistemas IA que suponen una amenaza para la\\nseguridad, la vida o los
derechos fundamentales. En este nivel se encuentran, por ejemplo, los\\nsistemas con
alguna de las siguientes funciones:\\n• Manipulación subliminal del comportamiento de una
persona de manera que\\npueda causarle daños físicos o psicológicos a él o a otros.\\n•
Explotación de vulnerabilidades de grupos sociales para manipular su\\ncomportamiento de
forma que pueda causarles daño a ellos o a otros.\\n• Evaluación o clasificación de
personas o grupos por su comportamiento social que\\npueda perjudicarlos
desproporcionadamente en el ámbito del comportamiento\\nobservado, o perjudicarlos en
ámbitos distintos a donde se observó.\\n• Identificación biométrica en tiempo real en
espacios de acceso público para\\nautoridades policiales, salvo casos tasados y mediando
autorización.\\nLa Comisión Europea ha preparado unas directrices con el fin de aclarar la
interpretación de\\nciertos casos concretos (Guidelines on prohibited artificial intelligence
practices established by\\nRegulation (EU) 20241689 (AI Act)) 1.\\nB) Sistemas de Alto
Riesgo: el segundo nivel se reserva a los sistemas de alto riesgo, pero\\ncuyo uso está
permitido, a los que el Reglamento dedica la mayoría de los requisitos y\\nobligaciones que
deben cumplir los distintos roles que participan en la cadena de valor de la\\npuesta en uso
de un sistema IA (operadores). Se dividen en dos tipos de sistemas:\\nB1) Productos o
componentes de seguridad de alto riesgo contemplados en\\nlegislación de
armonización:\\no Sistemas de IA que sea un componente de seguridad de alguno de los
productos\\ncontemplados en la legislación de armonización de la Unión recogidos en el
Anexo\\nI del Reglamento o,\\no Que el propio sistema de IA como producto, deba
someterse a una evaluación de la\",\"aesia — 5.2 Entidades financieras y p roveedores
sujetos a legislación\\ncumplir con los nuevos requisitos regulatorios. En resumen, el
objetivo del texto es\\ngarantizar la regulación de la IA de alto riesgo en la UE, reduciendo la
carga administrativa\\ny de costos para los proveedores, al mismo tiempo que se asegura la
protección y\\nseguridad del responsable del despliegue final.\\nAI Act\"]],\"kwargs\":{}}",
"output": "# Informe de Cumplimiento del Sistema de IA\n\n## Resumen Ejecutivo\nEl
sistema descrito es un sistema de IA que evalúa el riesgo de recidiva de presos para
recomendar libertad condicional. Este sistema ha sido clasificado como de alto riesgo
debido a las implicaciones significativas que tiene en la vida de las personas evaluadas. En
este informe se analiza su contexto regulatorio y se detallan las obligaciones y requisitos
legales aplicables según la normativa de la Unión Europea.\n\n## Clasificación de
Riesgo\nEl sistema ha sido clasificado como de **alto riesgo** según el artículo 2.3 Niveles
de riesgo del Reglamento Europeo de IA (aesia). Este nivel de riesgo se justifica por la
naturaleza crítica de las decisiones que el sistema puede influir, las cuales pueden tener un
impacto significativo en la vida y los derechos fundamentales de los individuos.\n\n##
Obligaciones Aplicables\nSegún el artículo 2.3 Niveles de riesgo del Reglamento Europeo
de IA (aesia), los sistemas de alto riesgo están sujetos a los siguientes requisitos:\n\n1.
**Declaración UE de Conformidad (eu_ai_act — Artículo 47)**:\n - El proveedor debe
redactar una declaración UE de conformidad por escrito en un formato legible por máquina,
con firma electrónica o manuscrita, para cada sistema de IA de alto riesgo.\n - La
declaración debe especificar el sistema de IA de alto riesgo para el que ha sido redactada y
se mantendrá a disposición de las autoridades nacionales competentes durante un período
de diez años.\n - La declaración contendrá toda la información necesaria para determinar
el cumplimiento de los requisitos establecidos en la sección 2 del Reglamento Europeo de


IA.\n - El proveedor asumirá la responsabilidad del cumplimiento de los requisitos
establecidos en la sección 2.\n\n## Citas Legales\n- **eu_ai_act — Artículo 47**:
Declaración UE de conformidad.\n- **aesia — 2.3 Niveles de riesgo del Reglamento
Europeo de IA**: Clasificación de sistemas de alto riesgo.\n\n## Recomendaciones\n1.
**Redactar Declaración UE de Conformidad**: El proveedor debe redactar y mantener
actualizada la declaración UE de conformidad para el sistema de IA.\n2. **Garantizar
Disponibilidad**: Asegurar que la declaración esté disponible para las autoridades
nacionales competentes durante el período requerido.\n3. **Cumplimiento de Requisitos**:
Asegurar que el sistema cumple con todos los requisitos establecidos en la normativa
aplicable, especialmente en la sección 2 del Reglamento Europeo de IA.\n\nEste informe se
basa exclusivamente en las citas legales proporcionadas y no incluye contenido
inventado.\n\n---\n*Informe preliminar generado por IA. Consulte profesional jurídico.*",
"metadata":
"{\"risk_level\":\"alto_riesgo\",\"n_articles\":3,\"grounded\":true,\"model\":\"eu.amazon.nova-lit
e-v1:0\",\"report_length\":2662}"
}
]

###### Análisis de Code Claude

**Pipeline: generate_report solamente — FUNCIONAL** ✓

09:55:28.151 classifier.predict_risk [de6e129b] 16ms ← interno de generate_report
09:55:28.167 retriever.search [66138a36] 121ms
09:55:28.288 report.generate [43f3e93e] 2.9s
──────────────────────────────────────────────────────
TOTAL Q4: ~3 segundos

Los docker logs de Q4 muestran Ollama activo desde las 09:49:27 — ese es el tail del pipeline RAG
que quedó de Q3 (las 5 llamadas Ollama terminando a las 09:55:25). Q4 en sí no tuvo actividad
Ollama.

**Agente ignoró parte de la petición**

El usuario pidió explícitamente **tres operaciones** : "Clasifícalo, busca los artículos aplicables y genera
un informe." El agente solo ejecutó generate_report (una tool). No llamó a search_legal_docs por
separado.
Dos consecuencias:

1. La búsqueda de artículos aplicables se hizo internamente vía el retriever del generate_report
    (k=3, misma query genérica), no como una búsqueda RAG con grading
2. El usuario percibió que recibió los tres resultados (la UI muestra clasificación + artículos +
    informe), porque el orchestrador sintetizó todo a partir de una sola tool — correcto en
    apariencia pero incompleto en profundidad

**Clasificación —** ✓ **Legalmente correcta**


Anexo III cat. 6 = Administración de justicia y procesos democráticos. Es la categoría exacta para
sistemas de evaluación de riesgo de recidiva en decisiones judiciales.
Nota: el modelo ML predijo inaceptable (99.2%), que también es legalmente defendible — Art.
5(1)(b) prohíbe sistemas que evalúen riesgo de comportamiento futuro basado en perfilado. El
override a alto_riesgo es una decisión de diseño discutible pero no incorrecta.

**Mismo annex3_override bug (tercera vez consecutiva, Q2, Q3, Q4)**

"risk_level": "alto_riesgo",
"probabilities": { "inaceptable": 0.9922 }, ← contradicción
"shap_explanation": "Factores principales para 'inaceptable'" ← clase incorrecta

**Retrieval — mismos 3 docs que Q3**

Query: "obligaciones sistemas de riesgo alto_riesgo EU AI Act" con k=3
Recupera exactamente los mismos chunks que Q3:

```
● Art. 47 (Declaración conformidad)
● AESIA 2.3 (Niveles de riesgo)
● AESIA 5.2 (Entidades financieras)
```
La query es genérica para cualquier sistema alto_riesgo — no aprovecha que este caso es
específico de justicia/recidiva. No hay ningún artículo específico de justica en los resultados.

**Informe — mismas limitaciones que Q3**

El report.generate interno produce la referencia "artículo 2.3 Niveles de riesgo del
Reglamento Europeo de IA (aesia)" en la sección de clasificación. La UI muestra "Anexo III
cat. 6" — el orquestador lo corrigió al sintetizar, igual que en Q3.

**Resumen Q4**

```
Métrica Valor Estado
Latencia total ~3s ✓ Excelente
Tool elegida generate_report ⚠ Ignora "busca artículos"
Clasificación alto_riesgo, Anexo III cat. 6 ✓ Correcta
annex3_override bug presente ⚠ (igual Q2, Q3)
shap_explanation clase incorrecta presente ⚠
Retrieval Art. 47 + AESIA genérico ⚠ No específico de justicia
AESIA como fuente normativa sí ⚠
Disclaimer presente ✓
```

grounded true ✓


### Query 1

###### Input en chat UI

¿Qué obligaciones tiene un sistema de IA de alto riesgo según el EU AI Act?

###### Salida en chat UI

Según el EU AI Act, las obligaciones de los sistemas de IA de alto riesgo se
establecen en el Artículo 25. A continuación, se exponen las obligaciones
específicas para los proveedores de sistemas de IA de alto riesgo:

1. Distribuidores, Importadores, Responsables del Despliegue o Terceros
    como Proveedores de Sistemas de IA de Alto Riesgo:
       ○ Cualquier distribuidor, importador, responsable del despliegue o
          tercero será considerado proveedor de un sistema de IA de alto
          riesgo a los efectos del presente Reglamento y estará sujeto a las
          obligaciones del proveedor previstas en el artículo 16 en
          cualquiera de las siguientes circunstancias:
             ■ a) Cuando ponga su nombre o marca en un sistema de
                IA de alto riesgo previamente introducido en el mercado
                o puesto en servicio, sin perjuicio de los acuerdos
                contractuales que estipulen que las obligaciones se
                asignan de otro modo.
             ■ b) Cuando modifique sustancialmente un sistema de IA
                de alto riesgo que ya haya sido introducido en el
                mercado o puesto en servicio de tal manera que siga
                siendo un sistema de IA de alto riesgo con arreglo al
                artículo 6.
             ■ c) Cuando modifique la finalidad prevista de un sistema
                de IA, incluido un sistema de IA de uso general, que no
                haya sido considerado de alto riesgo y ya haya sido
                introducido en el mercado o puesto en servicio, de tal
                manera que el sistema de IA de que se trate se
                convierta en un sistema de IA de alto riesgo de
                conformidad con el artículo 6.

Estas obligaciones se encuentran detalladas en el Artículo 25 del EU AI Act.

Fuentes:

```
● EU AI Act, Artículo 25.
```

_Informe preliminar generado por IA. Consulte profesional jurídico._

###### Salida en docker logs

2026-03-02 16:44:28,521 INFO botocore.credentials Found credentials from IAM Role:
NormaBot_Agent_EC2_Role
2026-03-02 16:44:28,658 INFO langchain_aws.chat_models.bedrock_converse Using
Bedrock Converse API to generate response
2026-03-02 16:44:30,374 INFO chromadb.telemetry.product.posthog Anonymized telemetry
enabled. See https://docs.trychroma.com/telemetry for more information.
2026-03-02 16:44:35,288 INFO sentence_transformers.SentenceTransformer Use pytorch
device_name: cpu
2026-03-02 16:44:35,288 INFO sentence_transformers.SentenceTransformer Load
pretrained SentenceTransformer: intfloat/multilingual-e5-base
Batches: 100%|██████████| 1/1 [00:00<00:00, 3.46it/s]
time=2026-03-02T16:44:46.051Z level=WARN source=cpu_linux.go:130 msg="failed to
parse CPU allowed micro secs" error="strconv.ParseInt: parsing \"max\": invalid syntax"
llama_model_loader: loaded meta data with 35 key-value pairs and 434 tensors from
/home/appuser/.ollama/models/blobs/sha256-5ee4f07cdb9beadbbb293e85803c569b01bd37
ed059d2715faa7bb405f31caa6 (version GGUF V3 (latest))
llama_model_loader: Dumping metadata keys/values. Note: KV overrides do not apply in
this output.
llama_model_loader: - kv 0: general.architecture str = qwen2
llama_model_loader: - kv 1: general.type str = model
llama_model_loader: - kv 2: general.name str = Qwen2.5 3B
Instruct
llama_model_loader: - kv 3: general.finetune str = Instruct
llama_model_loader: - kv 4: general.basename str = Qwen2.5
llama_model_loader: - kv 5: general.size_label str = 3B
llama_model_loader: - kv 6: general.license str = other
llama_model_loader: - kv 7: general.license.name str =
qwen-research
llama_model_loader: - kv 8: general.license.link str =
https://huggingface.co/Qwen/Qwen2.5-3...
llama_model_loader: - kv 9: general.base_model.count u32 = 1
llama_model_loader: - kv 10: general.base_model.0.name str = Qwen2.5
3B
llama_model_loader: - kv 11: general.base_model.0.organization str = Qwen
llama_model_loader: - kv 12: general.base_model.0.repo_url str =
https://huggingface.co/Qwen/Qwen2.5-3B
llama_model_loader: - kv 13: general.tags arr[str,2] = ["chat",
"text-generation"]
llama_model_loader: - kv 14: general.languages arr[str,1] = ["en"]
llama_model_loader: - kv 15: qwen2.block_count u32 = 36
llama_model_loader: - kv 16: qwen2.context_length u32 = 32768
llama_model_loader: - kv 17: qwen2.embedding_length u32 = 2048
llama_model_loader: - kv 18: qwen2.feed_forward_length u32 = 11008


llama_model_loader: - kv 19: qwen2.attention.head_count u32 = 16
llama_model_loader: - kv 20: qwen2.attention.head_count_kv u32 = 2
llama_model_loader: - kv 21: qwen2.rope.freq_base f32 =
1000000.000000
llama_model_loader: - kv 22: qwen2.attention.layer_norm_rms_epsilon f32 =
0.000001
llama_model_loader: - kv 23: general.file_type u32 = 15
llama_model_loader: - kv 24: tokenizer.ggml.model str = gpt2
llama_model_loader: - kv 25: tokenizer.ggml.pre str = qwen2
llama_model_loader: - kv 26: tokenizer.ggml.tokens arr[str,151936] = ["!", "\"",
"#", "$", "%", "&", "'", ...
llama_model_loader: - kv 27: tokenizer.ggml.token_type arr[i32,151936] = [1, 1,
1, 1, 1, 1, 1, 1, 1, 1, 1, 1, ...
llama_model_loader: - kv 28: tokenizer.ggml.merges arr[str,151387] = ["Ġ Ġ",
"ĠĠ ĠĠ", "i n", "Ġ t",...
llama_model_loader: - kv 29: tokenizer.ggml.eos_token_id u32 = 151645
llama_model_loader: - kv 30: tokenizer.ggml.padding_token_id u32 =
151643
llama_model_loader: - kv 31: tokenizer.ggml.bos_token_id u32 = 151643
llama_model_loader: - kv 32: tokenizer.ggml.add_bos_token bool = false
llama_model_loader: - kv 33: tokenizer.chat_template str = {%- if tools
%}\n {{- '<|im_start|>...
llama_model_loader: - kv 34: general.quantization_version u32 = 2
llama_model_loader: - type f32: 181 tensors
llama_model_loader: - type q4_K: 216 tensors
llama_model_loader: - type q6_K: 37 tensors
print_info: file format = GGUF V3 (latest)
print_info: file type = Q4_K - Medium
print_info: file size = 1.79 GiB (4.99 BPW)
load: printing all EOG tokens:
load: - 151643 ('<|endoftext|>')
load: - 151645 ('<|im_end|>')
load: - 151662 ('<|fim_pad|>')
load: - 151663 ('<|repo_name|>')
load: - 151664 ('<|file_sep|>')
load: special tokens cache size = 22
load: token to piece cache size = 0.9310 MB
print_info: arch = qwen2
print_info: vocab_only = 1
print_info: no_alloc = 0
print_info: model type = ?B
print_info: model params = 3.09 B
print_info: general.name = Qwen2.5 3B Instruct
print_info: vocab type = BPE
print_info: n_vocab = 151936
print_info: n_merges = 151387
print_info: BOS token = 151643 '<|endoftext|>'
print_info: EOS token = 151645 '<|im_end|>'


print_info: EOT token = 151645 '<|im_end|>'
print_info: PAD token = 151643 '<|endoftext|>'
print_info: LF token = 198 'Ċ'
print_info: FIM PRE token = 151659 '<|fim_prefix|>'
print_info: FIM SUF token = 151661 '<|fim_suffix|>'
print_info: FIM MID token = 151660 '<|fim_middle|>'
print_info: FIM PAD token = 151662 '<|fim_pad|>'
print_info: FIM REP token = 151663 '<|repo_name|>'
print_info: FIM SEP token = 151664 '<|file_sep|>'
print_info: EOG token = 151643 '<|endoftext|>'
print_info: EOG token = 151645 '<|im_end|>'
print_info: EOG token = 151662 '<|fim_pad|>'
print_info: EOG token = 151663 '<|repo_name|>'
print_info: EOG token = 151664 '<|file_sep|>'
print_info: max token length = 256
llama_model_load: vocab only - skipping tensors
time=2026-03-02T16:44:46.483Z level=INFO source=server.go:431 msg="starting runner"
cmd="/usr/local/bin/ollama runner --model
/home/appuser/.ollama/models/blobs/sha256-5ee4f07cdb9beadbbb293e85803c569b01bd37
ed059d2715faa7bb405f31caa6 --port 46821"
time=2026-03-02T16:44:46.483Z level=INFO source=sched.go:491 msg="system memory"
total="7.6 GiB" free="4.5 GiB" free_swap="0 B"
time=2026-03-02T16:44:46.484Z level=INFO source=server.go:498 msg="loading model"
"model layers"=37 requested=-1
time=2026-03-02T16:44:46.485Z level=INFO source=device.go:245 msg="model weights"
device=CPU size="1.8 GiB"
time=2026-03-02T16:44:46.486Z level=INFO source=device.go:256 msg="kv cache"
device=CPU size="144.0 MiB"
time=2026-03-02T16:44:46.486Z level=INFO source=device.go:272 msg="total memory"
size="1.9 GiB"
time=2026-03-02T16:44:46.502Z level=INFO source=runner.go:965 msg="starting go
runner"
load_backend: loaded CPU backend from /usr/local/lib/ollama/libggml-cpu-skylakex.so
time=2026-03-02T16:44:46.514Z level=INFO source=ggml.go:104 msg=system
CPU.0.SSE3=1 CPU.0.SSSE3=1 CPU.0.AVX=1 CPU.0.AVX2=1 CPU.0.F16C=1
CPU.0.FMA=1 CPU.0.BMI2=1 CPU.0.AVX512=1 CPU.0.LLAMAFILE=1
CPU.1.LLAMAFILE=1 compiler=cgo(gcc)
time=2026-03-02T16:44:46.515Z level=INFO source=runner.go:1001 msg="Server listening
on 127.0.0.1:46821"
time=2026-03-02T16:44:46.519Z level=INFO source=runner.go:895 msg=load
request="{Operation:commit LoraPath:[] Parallel:1 BatchSize:512 FlashAttention:Auto
KvSize:4096 KvCacheType: NumThreads:1 GPULayers:[] MultiUserCache:false
ProjectorPath: MainGPU:0 UseMmap:false}"
time=2026-03-02T16:44:46.520Z level=INFO source=server.go:1350 msg="waiting for llama
runner to start responding"
time=2026-03-02T16:44:46.521Z level=INFO source=server.go:1384 msg="waiting for
server to become available" status="llm server loading model"


llama_model_loader: loaded meta data with 35 key-value pairs and 434 tensors from
/home/appuser/.ollama/models/blobs/sha256-5ee4f07cdb9beadbbb293e85803c569b01bd37
ed059d2715faa7bb405f31caa6 (version GGUF V3 (latest))
llama_model_loader: Dumping metadata keys/values. Note: KV overrides do not apply in
this output.
llama_model_loader: - kv 0: general.architecture str = qwen2
llama_model_loader: - kv 1: general.type str = model
llama_model_loader: - kv 2: general.name str = Qwen2.5 3B
Instruct
llama_model_loader: - kv 3: general.finetune str = Instruct
llama_model_loader: - kv 4: general.basename str = Qwen2.5
llama_model_loader: - kv 5: general.size_label str = 3B
llama_model_loader: - kv 6: general.license str = other
llama_model_loader: - kv 7: general.license.name str =
qwen-research
llama_model_loader: - kv 8: general.license.link str =
https://huggingface.co/Qwen/Qwen2.5-3...
llama_model_loader: - kv 9: general.base_model.count u32 = 1
llama_model_loader: - kv 10: general.base_model.0.name str = Qwen2.5
3B
llama_model_loader: - kv 11: general.base_model.0.organization str = Qwen
llama_model_loader: - kv 12: general.base_model.0.repo_url str =
https://huggingface.co/Qwen/Qwen2.5-3B
llama_model_loader: - kv 13: general.tags arr[str,2] = ["chat",
"text-generation"]
llama_model_loader: - kv 14: general.languages arr[str,1] = ["en"]
llama_model_loader: - kv 15: qwen2.block_count u32 = 36
llama_model_loader: - kv 16: qwen2.context_length u32 = 32768
llama_model_loader: - kv 17: qwen2.embedding_length u32 = 2048
llama_model_loader: - kv 18: qwen2.feed_forward_length u32 = 11008
llama_model_loader: - kv 19: qwen2.attention.head_count u32 = 16
llama_model_loader: - kv 20: qwen2.attention.head_count_kv u32 = 2
llama_model_loader: - kv 21: qwen2.rope.freq_base f32 =
1000000.000000
llama_model_loader: - kv 22: qwen2.attention.layer_norm_rms_epsilon f32 =
0.000001
llama_model_loader: - kv 23: general.file_type u32 = 15
llama_model_loader: - kv 24: tokenizer.ggml.model str = gpt2
llama_model_loader: - kv 25: tokenizer.ggml.pre str = qwen2
llama_model_loader: - kv 26: tokenizer.ggml.tokens arr[str,151936] = ["!", "\"",
"#", "$", "%", "&", "'", ...
llama_model_loader: - kv 27: tokenizer.ggml.token_type arr[i32,151936] = [1, 1,
1, 1, 1, 1, 1, 1, 1, 1, 1, 1, ...
llama_model_loader: - kv 28: tokenizer.ggml.merges arr[str,151387] = ["Ġ Ġ",
"ĠĠ ĠĠ", "i n", "Ġ t",...
llama_model_loader: - kv 29: tokenizer.ggml.eos_token_id u32 = 151645
llama_model_loader: - kv 30: tokenizer.ggml.padding_token_id u32 =
151643


llama_model_loader: - kv 31: tokenizer.ggml.bos_token_id u32 = 151643
llama_model_loader: - kv 32: tokenizer.ggml.add_bos_token bool = false
llama_model_loader: - kv 33: tokenizer.chat_template str = {%- if tools
%}\n {{- '<|im_start|>...
llama_model_loader: - kv 34: general.quantization_version u32 = 2
llama_model_loader: - type f32: 181 tensors
llama_model_loader: - type q4_K: 216 tensors
llama_model_loader: - type q6_K: 37 tensors
print_info: file format = GGUF V3 (latest)
print_info: file type = Q4_K - Medium
print_info: file size = 1.79 GiB (4.99 BPW)
load: printing all EOG tokens:
load: - 151643 ('<|endoftext|>')
load: - 151645 ('<|im_end|>')
load: - 151662 ('<|fim_pad|>')
load: - 151663 ('<|repo_name|>')
load: - 151664 ('<|file_sep|>')
load: special tokens cache size = 22
load: token to piece cache size = 0.9310 MB
print_info: arch = qwen2
print_info: vocab_only = 0
print_info: no_alloc = 0
print_info: n_ctx_train = 32768
print_info: n_embd = 2048
print_info: n_embd_inp = 2048
print_info: n_layer = 36
print_info: n_head = 16
print_info: n_head_kv = 2
print_info: n_rot = 128
print_info: n_swa = 0
print_info: is_swa_any = 0
print_info: n_embd_head_k = 128
print_info: n_embd_head_v = 128
print_info: n_gqa = 8
print_info: n_embd_k_gqa = 256
print_info: n_embd_v_gqa = 256
print_info: f_norm_eps = 0.0e+00
print_info: f_norm_rms_eps = 1.0e-06
print_info: f_clamp_kqv = 0.0e+00
print_info: f_max_alibi_bias = 0.0e+00
print_info: f_logit_scale = 0.0e+00
print_info: f_attn_scale = 0.0e+00
print_info: n_ff = 11008
print_info: n_expert = 0
print_info: n_expert_used = 0
print_info: n_expert_groups = 0
print_info: n_group_used = 0
print_info: causal attn = 1


print_info: pooling type = -1
print_info: rope type = 2
print_info: rope scaling = linear
print_info: freq_base_train = 1000000.0
print_info: freq_scale_train = 1
print_info: n_ctx_orig_yarn = 32768
print_info: rope_yarn_log_mul= 0.0000
print_info: rope_finetuned = unknown
print_info: model type = 3B
print_info: model params = 3.09 B
print_info: general.name = Qwen2.5 3B Instruct
print_info: vocab type = BPE
print_info: n_vocab = 151936
print_info: n_merges = 151387
print_info: BOS token = 151643 '<|endoftext|>'
print_info: EOS token = 151645 '<|im_end|>'
print_info: EOT token = 151645 '<|im_end|>'
print_info: PAD token = 151643 '<|endoftext|>'
print_info: LF token = 198 'Ċ'
print_info: FIM PRE token = 151659 '<|fim_prefix|>'
print_info: FIM SUF token = 151661 '<|fim_suffix|>'
print_info: FIM MID token = 151660 '<|fim_middle|>'
print_info: FIM PAD token = 151662 '<|fim_pad|>'
print_info: FIM REP token = 151663 '<|repo_name|>'
print_info: FIM SEP token = 151664 '<|file_sep|>'
print_info: EOG token = 151643 '<|endoftext|>'
print_info: EOG token = 151645 '<|im_end|>'
print_info: EOG token = 151662 '<|fim_pad|>'
print_info: EOG token = 151663 '<|repo_name|>'
print_info: EOG token = 151664 '<|file_sep|>'
print_info: max token length = 256
load_tensors: loading model tensors, this can take a while... (mmap = false)
load_tensors: CPU model buffer size = 1834.82 MiB
llama_context: constructing llama_context
llama_context: n_seq_max = 1
llama_context: n_ctx = 4096
llama_context: n_ctx_seq = 4096
llama_context: n_batch = 512
llama_context: n_ubatch = 512
llama_context: causal_attn = 1
llama_context: flash_attn = auto
llama_context: kv_unified = false
llama_context: freq_base = 1000000.0
llama_context: freq_scale = 1
llama_context: n_ctx_seq (4096) < n_ctx_train (32768) -- the full capacity of the model will
not be utilized
llama_context: CPU output buffer size = 0.59 MiB
llama_kv_cache: CPU KV buffer size = 144.00 MiB


llama_kv_cache: size = 144.00 MiB ( 4096 cells, 36 layers, 1/1 seqs), K (f16): 72.00 MiB,
V (f16): 72.00 MiB
llama_context: Flash Attention was auto, set to enabled
llama_context: CPU compute buffer size = 304.75 MiB
llama_context: graph nodes = 1231
llama_context: graph splits = 1
time=2026-03-02T16:45:00.831Z level=INFO source=server.go:1388 msg="llama runner
started in 14.35 seconds"
time=2026-03-02T16:45:00.831Z level=INFO source=sched.go:566 msg="loaded runners"
count=1
time=2026-03-02T16:45:00.831Z level=INFO source=server.go:1350 msg="waiting for llama
runner to start responding"
time=2026-03-02T16:45:00.832Z level=INFO source=server.go:1388 msg="llama runner
started in 14.35 seconds"
[GIN] 2026/03/02 - 16:45:20 | 200 | 34.329972434s | 127.0.0.1 | POST "/api/chat"
[GIN] 2026/03/02 - 16:46:19 | 200 | 59.308961501s | 127.0.0.1 | POST "/api/chat"
[GIN] 2026/03/02 - 16:47:21 | 200 | 1m1s | 127.0.0.1 | POST "/api/chat"
[GIN] 2026/03/02 - 16:47:31 | 200 | 10.429273874s | 127.0.0.1 | POST "/api/chat"
[GIN] 2026/03/02 - 16:48:35 | 200 | 1m3s | 127.0.0.1 | POST "/api/chat"
2026-03-02 16:48:35,154 INFO langchain_aws.chat_models.bedrock_converse Using
Bedrock Converse API to generate response
2026-03-02 16:48:36,932 INFO langchain_aws.chat_models.bedrock_converse Using
Bedrock Converse API to generate response

###### Logs de langfuse en JSON

[
{
"id": "73d1c19b-1fd1-4c6c-9213-2a07ad9e8a11",
"type": "SPAN",
"name": "rag.retrieve (73d1c19b)",
"startTime": "2026-03-02T16:44:29.699Z",
"endTime": "2026-03-02T16:44:45.864Z",
"depth": 0,
"input": "{\"args\":[\"Obligaciones de sistemas de IA de alto riesgo según el EU AI
Act\"],\"kwargs\":{}}",
"output": "[{\"doc\":\"Obligaciones de los proveedores y responsables del despliegue de
sistemas de IA de alto riesgo y de otras
partes\",\"metadata\":{\"unit_index\":20,\"id\":\"1927ec2cec85c21d989d73a8d932b5c0\",\"unit
_type\":\"section\",\"doc_date\":\"13 junio
2024\",\"doc_title\":\"L_202401689ES.000101.fmx.xml\",\"source\":\"eu_ai_act\",\"sub_index\"
:0,\"unit_id\":\"3\",\"file\":\"EU_AI_Act_2024_1689_ES.html\",\"unit_title\":\"SECCIÓN
3\"},\"score\":0.7862892150878906},{\"doc\":\"Obligaciones de los responsables del
despliegue de sistemas de IA de alto riesgo\\n1. Los responsables del despliegue de
sistemas de IA de alto riesgo adoptarán medidas técnicas y organizativas adecuadas para
garantizar que utilizan dichos sistemas con arreglo a las instrucciones de uso que los
acompañen, de acuerdo con los apartados 3 y 6.\\n2. Los responsables del despliegue
encomendarán la supervisión humana a personas físicas que tengan la competencia, la


formación y la autoridad necesarias.\\n3. Las obligaciones previstas en los apartados 1 y 2
no afectan a otras obligaciones que el Derecho nacional o de la Unión imponga a los
responsables del despliegue ni a su libertad para organizar sus propios recursos y
actividades con el fin de poner en práctica las medidas de supervisión humana que indique
el proveedor.\\n4. Sin perjuicio de lo dispuesto en los apartados 1 y 2, el responsable del
despliegue se asegurará de que los datos de entrada sean pertinentes y suficientemente
representativos en vista de la finalidad prevista del sistema de IA de alto riesgo, en la
medida en que ejerza el control sobre dichos
datos.\",\"metadata\":{\"sub_index\":0,\"doc_title\":\"L_202401689ES.000101.fmx.xml\",\"unit_
id\":\"26\",\"unit_type\":\"article\",\"unit_index\":31,\"source\":\"eu_ai_act\",\"id\":\"6894451b30
952f00cc47f204c382d6eb\",\"unit_title\":\"Artículo 26\",\"doc_date\":\"13 junio
2024\",\"file\":\"EU_AI_Act_2024_1689_ES.html\"},\"score\":0.7854478359222412},{\"doc\":\"
Responsabilidades a lo largo de la cadena de valor de la IA\\n1. Cualquier distribuidor,
importador, responsable del despliegue o tercero será considerado proveedor de un sistema
de IA de alto riesgo a los efectos del presente Reglamento y estará sujeto a las obligaciones
del proveedor previstas en el artículo 16 en cualquiera de las siguientes
circunstancias:\\na)\\ncuando ponga su nombre o marca en un sistema de IA de alto riesgo
previamente introducido en el mercado o puesto en servicio, sin perjuicio de los acuerdos
contractuales que estipulen que las obligaciones se asignan de otro modo;\\nb)\\ncuando
modifique sustancialmente un sistema de IA de alto riesgo que ya haya sido introducido en
el mercado o puesto en servicio de tal manera que siga siendo un sistema de IA de alto
riesgo con arreglo al artículo 6;\\nc)\\ncuando modifique la finalidad prevista de un sistema
de IA, incluido un sistema de IA de uso general, que no haya sido considerado de alto
riesgo y ya haya sido introducido en el mercado o puesto en servicio, de tal manera que el
sistema de IA de que se trate se convierta en un sistema de IA de alto riesgo de
conformidad con el artículo 6.\",\"metadata\":{\"unit_title\":\"Artículo
25\",\"doc_title\":\"L_202401689ES.000101.fmx.xml\",\"id\":\"8d84e19594df27c6cca8e9961a
ac43a6\",\"unit_index\":30,\"unit_type\":\"article\",\"doc_date\":\"13 junio
2024\",\"sub_index\":0,\"unit_id\":\"25\",\"source\":\"eu_ai_act\",\"file\":\"EU_AI_Act_2024_168
9_ES.html\"},\"score\":0.7791342735290527},{\"doc\":\"Obligaciones de los proveedores de
modelos de IA de uso general con riesgo
sistémico\",\"metadata\":{\"unit_index\":66,\"unit_id\":\"3\",\"doc_date\":\"13 junio
2024\",\"unit_type\":\"section\",\"id\":\"b99e0d02811935240ce38d51196bdd7f\",\"file\":\"EU_AI
_Act_2024_1689_ES.html\",\"doc_title\":\"L_202401689ES.000101.fmx.xml\",\"sub_index\":0
,\"unit_title\":\"SECCIÓN
3\",\"source\":\"eu_ai_act\"},\"score\":0.7715327441692352},{\"doc\":\"por parte del
proveedor, si este proporciona al responsable del despliegue el\\nsistema de IA como un
MLSaaS ( Machine Learning as a Service ) u otras formas de\\ncomercialización y puesta
en marcha que impliquen una instalación automática por\\nel responsable del despliegue
donde no haya configuración del sistema.\\n● Si el sistema de IA va a ser entregado al
responsable del despliegue en un formato\\non-premise o in-cloud, gestionado por el
responsable del despliegue, el proveedor\\ndebe proporcionar unas instrucciones
adecuadas para realizar la protección del\\nsistema especialmente durante el tiempo de
inferencia del sistema de IA en\\nproducción. El proceso de instalación del sistema de IA
debe contar con\\nmecanismos que garanticen que la instalación tenga en cuenta las
instrucciones de\\nmanera obligatoria, bien a través de pr ocedimientos de script
automáticos o semi\\nautomáticos, la obligación de disponer de las instrucciones abiertas
para el proceso\\nantes de continuar, la solicitud explicita de la lectura de estas o la


referencia a la\\nlectura especifica a conocer para cada paso del proceso.\\n● Las
actualizaciones del sistema de inteligencia artificial de alto riesgo deben de ser\\ntratadas
con todas las medidas aplicables descritas en esta guía.\\nComo complemento a estas
medidas organizativas, el proveedor deberá alinear las\\nsiguientes medidas
técnicas:\",\"metadata\":{\"id\":\"62018f0d02a5fb86c271b25dc9bc6365\",\"sub_index\":2,\"unit
_title\":\"4.1.1 Medidas aplicables\",\"doc_date\":\"10 diciembre
2025\",\"file\":\"11-guia-ciberseguridad.pdf\",\"unit_index\":43,\"unit_id\":\"4.1.1\",\"unit_type\":\
"subsection\",\"doc_title\":\"Empresas desarrollando cumplimiento de
requisitos\",\"source\":\"aesia\"},\"score\":0.7807244211435318}]",
"metadata": "{\"k\":5,\"n_docs_retrieved\":5}"
},
{
"id": "87961e49-40fe-4f82-98d7-538572b3da54",
"type": "SPAN",
"name": "retriever.search (87961e49)",
"startTime": "2026-03-02T16:44:29.700Z",
"endTime": "2026-03-02T16:44:45.863Z",
"depth": 1,
"input": "{\"args\":[\"Obligaciones de sistemas de IA de alto riesgo según el EU AI
Act\"],\"kwargs\":{\"k\":5,\"mode\":\"soft\"}}",
"output": "[{\"id\":\"1927ec2cec85c21d989d73a8d932b5c0\",\"text\":\"Obligaciones de los
proveedores y responsables del despliegue de sistemas de IA de alto riesgo y de otras
partes\",\"metadata\":{\"unit_index\":20,\"id\":\"1927ec2cec85c21d989d73a8d932b5c0\",\"unit
_type\":\"section\",\"doc_date\":\"13 junio
2024\",\"doc_title\":\"L_202401689ES.000101.fmx.xml\",\"source\":\"eu_ai_act\",\"sub_index\"
:0,\"unit_id\":\"3\",\"file\":\"EU_AI_Act_2024_1689_ES.html\",\"unit_title\":\"SECCIÓN
3\"},\"distance\":0.21371078491210938},{\"id\":\"6894451b30952f00cc47f204c382d6eb\",\"te
xt\":\"Obligaciones de los responsables del despliegue de sistemas de IA de alto riesgo\\n1.
Los responsables del despliegue de sistemas de IA de alto riesgo adoptarán medidas
técnicas y organizativas adecuadas para garantizar que utilizan dichos sistemas con arreglo
a las instrucciones de uso que los acompañen, de acuerdo con los apartados 3 y 6.\\n2.
Los responsables del despliegue encomendarán la supervisión humana a personas físicas
que tengan la competencia, la formación y la autoridad necesarias.\\n3. Las obligaciones
previstas en los apartados 1 y 2 no afectan a otras obligaciones que el Derecho nacional o
de la Unión imponga a los responsables del despliegue ni a su libertad para organizar sus
propios recursos y actividades con el fin de poner en práctica las medidas de supervisión
humana que indique el proveedor.\\n4. Sin perjuicio de lo dispuesto en los apartados 1 y 2,
el responsable del despliegue se asegurará de que los datos de entrada sean pertinentes y
suficientemente representativos en vista de la finalidad prevista del sistema de IA de alto
riesgo, en la medida en que ejerza el control sobre dichos
datos.\",\"metadata\":{\"sub_index\":0,\"doc_title\":\"L_202401689ES.000101.fmx.xml\",\"unit_
id\":\"26\",\"unit_type\":\"article\",\"unit_index\":31,\"source\":\"eu_ai_act\",\"id\":\"6894451b30
952f00cc47f204c382d6eb\",\"unit_title\":\"Artículo 26\",\"doc_date\":\"13 junio
2024\",\"file\":\"EU_AI_Act_2024_1689_ES.html\"},\"distance\":0.2145521640777588},{\"id\":\
"8d84e19594df27c6cca8e9961aac43a6\",\"text\":\"Responsabilidades a lo largo de la
cadena de valor de la IA\\n1. Cualquier distribuidor, importador, responsable del despliegue
o tercero será considerado proveedor de un sistema de IA de alto riesgo a los efectos del
presente Reglamento y estará sujeto a las obligaciones del proveedor previstas en el


artículo 16 en cualquiera de las siguientes circunstancias:\\na)\\ncuando ponga su nombre o
marca en un sistema de IA de alto riesgo previamente introducido en el mercado o puesto
en servicio, sin perjuicio de los acuerdos contractuales que estipulen que las obligaciones
se asignan de otro modo;\\nb)\\ncuando modifique sustancialmente un sistema de IA de alto
riesgo que ya haya sido introducido en el mercado o puesto en servicio de tal manera que
siga siendo un sistema de IA de alto riesgo con arreglo al artículo 6;\\nc)\\ncuando modifique
la finalidad prevista de un sistema de IA, incluido un sistema de IA de uso general, que no
haya sido considerado de alto riesgo y ya haya sido introducido en el mercado o puesto en
servicio, de tal manera que el sistema de IA de que se trate se convierta en un sistema de
IA de alto riesgo de conformidad con el artículo 6.\",\"metadata\":{\"unit_title\":\"Artículo
25\",\"doc_title\":\"L_202401689ES.000101.fmx.xml\",\"id\":\"8d84e19594df27c6cca8e9961a
ac43a6\",\"unit_index\":30,\"unit_type\":\"article\",\"doc_date\":\"13 junio
2024\",\"sub_index\":0,\"unit_id\":\"25\",\"source\":\"eu_ai_act\",\"file\":\"EU_AI_Act_2024_168
9_ES.html\"},\"distance\":0.22086572647094727},{\"id\":\"b99e0d02811935240ce38d51196b
dd7f\",\"text\":\"Obligaciones de los proveedores de modelos de IA de uso general con
riesgo sistémico\",\"metadata\":{\"unit_index\":66,\"unit_id\":\"3\",\"doc_date\":\"13 junio
2024\",\"unit_type\":\"section\",\"id\":\"b99e0d02811935240ce38d51196bdd7f\",\"file\":\"EU_AI
_Act_2024_1689_ES.html\",\"doc_title\":\"L_202401689ES.000101.fmx.xml\",\"sub_index\":0
,\"unit_title\":\"SECCIÓN
3\",\"source\":\"eu_ai_act\"},\"distance\":0.22846725583076477},{\"id\":\"62018f0d02a5fb86c
271b25dc9bc6365\",\"text\":\"por parte del proveedor, si este proporciona al responsable del
despliegue el\\nsistema de IA como un MLSaaS ( Machine Learning as a Service ) u otras
formas de\\ncomercialización y puesta en marcha que impliquen una instalación automática
por\\nel responsable del despliegue donde no haya configuración del sistema.\\n● Si el
sistema de IA va a ser entregado al responsable del despliegue en un formato\\non-premise
o in-cloud, gestionado por el responsable del despliegue, el proveedor\\ndebe proporcionar
unas instrucciones adecuadas para realizar la protección del\\nsistema especialmente
durante el tiempo de inferencia del sistema de IA en\\nproducción. El proceso de instalación
del sistema de IA debe contar con\\nmecanismos que garanticen que la instalación tenga en
cuenta las instrucciones de\\nmanera obligatoria, bien a través de pr ocedimientos de script
automáticos o semi\\nautomáticos, la obligación de disponer de las instrucciones abiertas
para el proceso\\nantes de continuar, la solicitud explicita de la lectura de estas o la
referencia a la\\nlectura especifica a conocer para cada paso del proceso.\\n● Las
actualizaciones del sistema de inteligencia artificial de alto riesgo deben de ser\\ntratadas
con todas las medidas aplicables descritas en esta guía.\\nComo complemento a estas
medidas organizativas, el proveedor deberá alinear las\\nsiguientes medidas
técnicas:\",\"metadata\":{\"id\":\"62018f0d02a5fb86c271b25dc9bc6365\",\"sub_index\":2,\"unit
_title\":\"4.1.1 Medidas aplicables\",\"doc_date\":\"10 diciembre
2025\",\"file\":\"11-guia-ciberseguridad.pdf\",\"unit_index\":43,\"unit_id\":\"4.1.1\",\"unit_type\":\
"subsection\",\"doc_title\":\"Empresas desarrollando cumplimiento de
requisitos\",\"source\":\"aesia\"},\"distance\":0.2192755788564682}]",
"metadata":
"{\"mode\":\"soft\",\"k\":5,\"n_results\":5,\"min_distance\":0.2137,\"max_distance\":0.2285}"
},
{
"id": "4e325f53-4cfa-44ae-b6ca-ce126828538c",
"type": "SPAN",
"name": "rag.grade (4e325f53)",


"startTime": "2026-03-02T16:44:45.865Z",
"endTime": "2026-03-02T16:48:35.143Z",
"depth": 0,
"input": "{\"args\":[\"Obligaciones de sistemas de IA de alto riesgo según el EU AI
Act\",[{\"doc\":\"Obligaciones de los proveedores y responsables del despliegue de sistemas
de IA de alto riesgo y de otras
partes\",\"metadata\":{\"unit_index\":20,\"id\":\"1927ec2cec85c21d989d73a8d932b5c0\",\"unit
_type\":\"section\",\"doc_date\":\"13 junio
2024\",\"doc_title\":\"L_202401689ES.000101.fmx.xml\",\"source\":\"eu_ai_act\",\"sub_index\"
:0,\"unit_id\":\"3\",\"file\":\"EU_AI_Act_2024_1689_ES.html\",\"unit_title\":\"SECCIÓN
3\"},\"score\":0.7862892150878906},{\"doc\":\"Obligaciones de los responsables del
despliegue de sistemas de IA de alto riesgo\\n1. Los responsables del despliegue de
sistemas de IA de alto riesgo adoptarán medidas técnicas y organizativas adecuadas para
garantizar que utilizan dichos sistemas con arreglo a las instrucciones de uso que los
acompañen, de acuerdo con los apartados 3 y 6.\\n2. Los responsables del despliegue
encomendarán la supervisión humana a personas físicas que tengan la competencia, la
formación y la autoridad necesarias.\\n3. Las obligaciones previstas en los apartados 1 y 2
no afectan a otras obligaciones que el Derecho nacional o de la Unión imponga a los
responsables del despliegue ni a su libertad para organizar sus propios recursos y
actividades con el fin de poner en práctica las medidas de supervisión humana que indique
el proveedor.\\n4. Sin perjuicio de lo dispuesto en los apartados 1 y 2, el responsable del
despliegue se asegurará de que los datos de entrada sean pertinentes y suficientemente
representativos en vista de la finalidad prevista del sistema de IA de alto riesgo, en la
medida en que ejerza el control sobre dichos
datos.\",\"metadata\":{\"sub_index\":0,\"doc_title\":\"L_202401689ES.000101.fmx.xml\",\"unit_
id\":\"26\",\"unit_type\":\"article\",\"unit_index\":31,\"source\":\"eu_ai_act\",\"id\":\"6894451b30
952f00cc47f204c382d6eb\",\"unit_title\":\"Artículo 26\",\"doc_date\":\"13 junio
2024\",\"file\":\"EU_AI_Act_2024_1689_ES.html\"},\"score\":0.7854478359222412},{\"doc\":\"
Responsabilidades a lo largo de la cadena de valor de la IA\\n1. Cualquier distribuidor,
importador, responsable del despliegue o tercero será considerado proveedor de un sistema
de IA de alto riesgo a los efectos del presente Reglamento y estará sujeto a las obligaciones
del proveedor previstas en el artículo 16 en cualquiera de las siguientes
circunstancias:\\na)\\ncuando ponga su nombre o marca en un sistema de IA de alto riesgo
previamente introducido en el mercado o puesto en servicio, sin perjuicio de los acuerdos
contractuales que estipulen que las obligaciones se asignan de otro modo;\\nb)\\ncuando
modifique sustancialmente un sistema de IA de alto riesgo que ya haya sido introducido en
el mercado o puesto en servicio de tal manera que siga siendo un sistema de IA de alto
riesgo con arreglo al artículo 6;\\nc)\\ncuando modifique la finalidad prevista de un sistema
de IA, incluido un sistema de IA de uso general, que no haya sido considerado de alto
riesgo y ya haya sido introducido en el mercado o puesto en servicio, de tal manera que el
sistema de IA de que se trate se convierta en un sistema de IA de alto riesgo de
conformidad con el artículo 6.\",\"metadata\":{\"unit_title\":\"Artículo
25\",\"doc_title\":\"L_202401689ES.000101.fmx.xml\",\"id\":\"8d84e19594df27c6cca8e9961a
ac43a6\",\"unit_index\":30,\"unit_type\":\"article\",\"doc_date\":\"13 junio
2024\",\"sub_index\":0,\"unit_id\":\"25\",\"source\":\"eu_ai_act\",\"file\":\"EU_AI_Act_2024_168
9_ES.html\"},\"score\":0.7791342735290527},{\"doc\":\"Obligaciones de los proveedores de
modelos de IA de uso general con riesgo
sistémico\",\"metadata\":{\"unit_index\":66,\"unit_id\":\"3\",\"doc_date\":\"13 junio


2024\",\"unit_type\":\"section\",\"id\":\"b99e0d02811935240ce38d51196bdd7f\",\"file\":\"EU_AI
_Act_2024_1689_ES.html\",\"doc_title\":\"L_202401689ES.000101.fmx.xml\",\"sub_index\":0
,\"unit_title\":\"SECCIÓN
3\",\"source\":\"eu_ai_act\"},\"score\":0.7715327441692352},{\"doc\":\"por parte del
proveedor, si este proporciona al responsable del despliegue el\\nsistema de IA como un
MLSaaS ( Machine Learning as a Service ) u otras formas de\\ncomercialización y puesta
en marcha que impliquen una instalación automática por\\nel responsable del despliegue
donde no haya configuración del sistema.\\n● Si el sistema de IA va a ser entregado al
responsable del despliegue en un formato\\non-premise o in-cloud, gestionado por el
responsable del despliegue, el proveedor\\ndebe proporcionar unas instrucciones
adecuadas para realizar la protección del\\nsistema especialmente durante el tiempo de
inferencia del sistema de IA en\\nproducción. El proceso de instalación del sistema de IA
debe contar con\\nmecanismos que garanticen que la instalación tenga en cuenta las
instrucciones de\\nmanera obligatoria, bien a través de pr ocedimientos de script
automáticos o semi\\nautomáticos, la obligación de disponer de las instrucciones abiertas
para el proceso\\nantes de continuar, la solicitud explicita de la lectura de estas o la
referencia a la\\nlectura especifica a conocer para cada paso del proceso.\\n● Las
actualizaciones del sistema de inteligencia artificial de alto riesgo deben de ser\\ntratadas
con todas las medidas aplicables descritas en esta guía.\\nComo complemento a estas
medidas organizativas, el proveedor deberá alinear las\\nsiguientes medidas
técnicas:\",\"metadata\":{\"id\":\"62018f0d02a5fb86c271b25dc9bc6365\",\"sub_index\":2,\"unit
_title\":\"4.1.1 Medidas aplicables\",\"doc_date\":\"10 diciembre
2025\",\"file\":\"11-guia-ciberseguridad.pdf\",\"unit_index\":43,\"unit_id\":\"4.1.1\",\"unit_type\":\
"subsection\",\"doc_title\":\"Empresas desarrollando cumplimiento de
requisitos\",\"source\":\"aesia\"},\"score\":0.7807244211435318}]],\"kwargs\":{}}",
"output": "[{\"doc\":\"Responsabilidades a lo largo de la cadena de valor de la IA\\n1.
Cualquier distribuidor, importador, responsable del despliegue o tercero será considerado
proveedor de un sistema de IA de alto riesgo a los efectos del presente Reglamento y
estará sujeto a las obligaciones del proveedor previstas en el artículo 16 en cualquiera de
las siguientes circunstancias:\\na)\\ncuando ponga su nombre o marca en un sistema de IA
de alto riesgo previamente introducido en el mercado o puesto en servicio, sin perjuicio de
los acuerdos contractuales que estipulen que las obligaciones se asignan de otro
modo;\\nb)\\ncuando modifique sustancialmente un sistema de IA de alto riesgo que ya haya
sido introducido en el mercado o puesto en servicio de tal manera que siga siendo un
sistema de IA de alto riesgo con arreglo al artículo 6;\\nc)\\ncuando modifique la finalidad
prevista de un sistema de IA, incluido un sistema de IA de uso general, que no haya sido
considerado de alto riesgo y ya haya sido introducido en el mercado o puesto en servicio, de
tal manera que el sistema de IA de que se trate se convierta en un sistema de IA de alto
riesgo de conformidad con el artículo 6.\",\"metadata\":{\"unit_title\":\"Artículo
25\",\"doc_title\":\"L_202401689ES.000101.fmx.xml\",\"id\":\"8d84e19594df27c6cca8e9961a
ac43a6\",\"unit_index\":30,\"unit_type\":\"article\",\"doc_date\":\"13 junio
2024\",\"sub_index\":0,\"unit_id\":\"25\",\"source\":\"eu_ai_act\",\"file\":\"EU_AI_Act_2024_168
9_ES.html\"},\"score\":0.7791342735290527}]",
"metadata": "{\"n_docs_in\":5,\"n_relevant\":1,\"method\":\"llm\"}"
},
{
"id": "6a25a1f4-c1c0-4e7c-b76a-59d2353f55ed",
"type": "SPAN",


"name": "rag.generate (6a25a1f4)",
"startTime": "2026-03-02T16:48:35.144Z",
"endTime": "2026-03-02T16:48:36.927Z",
"depth": 0,
"input": "{\"args\":[\"Obligaciones de sistemas de IA de alto riesgo según el EU AI
Act\",[{\"doc\":\"Responsabilidades a lo largo de la cadena de valor de la IA\\n1. Cualquier
distribuidor, importador, responsable del despliegue o tercero será considerado proveedor
de un sistema de IA de alto riesgo a los efectos del presente Reglamento y estará sujeto a
las obligaciones del proveedor previstas en el artículo 16 en cualquiera de las siguientes
circunstancias:\\na)\\ncuando ponga su nombre o marca en un sistema de IA de alto riesgo
previamente introducido en el mercado o puesto en servicio, sin perjuicio de los acuerdos
contractuales que estipulen que las obligaciones se asignan de otro modo;\\nb)\\ncuando
modifique sustancialmente un sistema de IA de alto riesgo que ya haya sido introducido en
el mercado o puesto en servicio de tal manera que siga siendo un sistema de IA de alto
riesgo con arreglo al artículo 6;\\nc)\\ncuando modifique la finalidad prevista de un sistema
de IA, incluido un sistema de IA de uso general, que no haya sido considerado de alto
riesgo y ya haya sido introducido en el mercado o puesto en servicio, de tal manera que el
sistema de IA de que se trate se convierta en un sistema de IA de alto riesgo de
conformidad con el artículo 6.\",\"metadata\":{\"unit_title\":\"Artículo
25\",\"doc_title\":\"L_202401689ES.000101.fmx.xml\",\"id\":\"8d84e19594df27c6cca8e9961a
ac43a6\",\"unit_index\":30,\"unit_type\":\"article\",\"doc_date\":\"13 junio
2024\",\"sub_index\":0,\"unit_id\":\"25\",\"source\":\"eu_ai_act\",\"file\":\"EU_AI_Act_2024_168
9_ES.html\"},\"score\":0.7791342735290527}]],\"kwargs\":{}}",
"output": "{\"answer\":\"**Obligaciones de sistemas de IA de alto riesgo según el EU AI
Act**\\n\\nSegún el EU AI Act, las obligaciones de los sistemas de IA de alto riesgo se
establecen en el Artículo 25, que detalla las responsabilidades a lo largo de la cadena de
valor de la IA. A continuación, se exponen las obligaciones específicas para los proveedores
de sistemas de IA de alto riesgo:\\n\\n1. **Distribuidores, Importadores, Responsables del
Despliegue o Terceros como Proveedores de Sistemas de IA de Alto Riesgo:**\\n -
Cualquier distribuidor, importador, responsable del despliegue o tercero será considerado
proveedor de un sistema de IA de alto riesgo a los efectos del presente Reglamento y
estará sujeto a las obligaciones del proveedor previstas en el artículo 16 en cualquiera de
las siguientes circunstancias:\\n - **a) Cuando ponga su nombre o marca en un sistema
de IA de alto riesgo previamente introducido en el mercado o puesto en servicio, sin
perjuicio de los acuerdos contractuales que estipulen que las obligaciones se asignan de
otro modo.**\\n - **b) Cuando modifique sustancialmente un sistema de IA de alto riesgo
que ya haya sido introducido en el mercado o puesto en servicio de tal manera que siga
siendo un sistema de IA de alto riesgo con arreglo al artículo 6.**\\n - **c) Cuando
modifique la finalidad prevista de un sistema de IA, incluido un sistema de IA de uso
general, que no haya sido considerado de alto riesgo y ya haya sido introducido en el
mercado o puesto en servicio, de tal manera que el sistema de IA de que se trate se
convierta en un sistema de IA de alto riesgo de conformidad con el artículo 6.**\\n\\nEstas
obligaciones se encuentran detalladas en el Artículo 25 del EU AI Act.\\n\\n**Fuentes:**\\n-
EU AI Act, Artículo 25.\\n\\n_Informe preliminar generado por IA. Consulte profesional
jurídico._\",\"sources\":[{\"unit_title\":\"Artículo
25\",\"doc_title\":\"L_202401689ES.000101.fmx.xml\",\"id\":\"8d84e19594df27c6cca8e9961a
ac43a6\",\"unit_index\":30,\"unit_type\":\"article\",\"doc_date\":\"13 junio


2024\",\"sub_index\":0,\"unit_id\":\"25\",\"source\":\"eu_ai_act\",\"file\":\"EU_AI_Act_2024_168
9_ES.html\"}],\"grounded\":true}",
"metadata": "{\"n_context_docs\":1,\"grounded\":true}"
}
]

###### Análisis de Code Claude

**Lo que funcionó:**

```
Componente Estado Detalle
ChromaDB + embeddings OK 5 docs recuperados, distancias 0.21-0.23 (buen rango)
retrieve() OK mode=soft, k=5, 16s (embeddings en CPU)
grade() Funciona
l
```
```
Método llm, 5 docs in → 1 doc out
```
```
generate() OK 1.8s, grounded=true, disclaimer presente, cita exacta
Langfuse OK Todos los spans trackeados con metadata
```
**Problemas identificados:**

**1. Latencia crítica — grade es el cuello de botella**
retrieve: 16s
grade: ~3m50s ← Ollama en CPU, 5 llamadas secuenciales
generate: 2s
Total: ~4 minutos

Los logs GIN lo confirman: 5 POST /api/chat de 34s, 59s, 61s, 10s, 63s — una llamada al LLM por
documento.

**2. Grader demasiado agresivo**
Filtró 4/5 documentos. Rechazó el **Artículo 26** (obligaciones de los responsables del despliegue) que
es directamente relevante a la query. La respuesta final queda incompleta — solo cubre Art. 25
(cadena de valor) cuando la pregunta pedía obligaciones en general.
**3. Calidad de respuesta — parcialmente correcta**
La respuesta es factualmente correcta pero incompleta. Falta:

```
● Art. 16 (obligaciones del proveedor)
● Art. 26 (obligaciones del responsable del despliegue)
● Requisitos técnicos (Art. 9-15: gestión de riesgos, datos, documentación, transparencia,
supervisión humana)
```

### Query 2

###### Input en chat UI

Tengo un sistema que analiza currículums automáticamente para filtrar candidatos en procesos de
selección. ¿En qué nivel de riesgo lo clasificarías?

###### Salida en chat UI

Tu sistema de análisis de currículums automático para filtrar candidatos en procesos
de selección se clasificaría en el nivel de riesgo ALTO.

Esta clasificación se basa en que el sistema afecta a los usuarios al tomar
decisiones importantes sobre sus oportunidades laborales. La referencia legal
utilizada para esta clasificación es el Anexo III cat. 4.a del EU AI Act, que cubre las
limitaciones para sistemas de IA que afectan derechos fundamentales o que podrían
dar lugar a perjuicios graves.

_Informe preliminar generado por IA. Consulte profesional jurídico._

###### Salida en docker logs

2026-03-02 16:50:07,164 INFO langchain_aws.chat_models.bedrock_converse Using
Bedrock Converse API to generate response
2026-03-02 16:50:07,987 INFO src.classifier.main Cargando modelo desde metadata: Exp
2: XGBoost + SVD + GS (augmented Anexo III)
2026-03-02 16:50:08,486 INFO src.classifier.main Clasificador cargado: XGBClassifier (107
features, pipeline=tfidf_svd_manual) desde
/app/src/classifier/classifier_dataset_fusionado/model
2026-03-02 16:50:08,540 INFO src.classifier.main Anexo III override: ML='inaceptable'
(99%) → 'alto_riesgo' [Anexo III cat. 4.a]
2026-03-02 16:50:08,547 INFO langchain_aws.chat_models.bedrock_converse Using
Bedrock Converse API to generate response

###### Logs de langfuse en JSON

[
{
"id": "0279dcfe-b520-43e0-aeea-626b0b5c4f64",
"type": "SPAN",
"name": "classifier.predict_risk (0279dcfe)",
"startTime": "2026-03-02T16:50:07.985Z",
"endTime": "2026-03-02T16:50:08.541Z",
"depth": 0,
"input": "{\"args\":[\"Un sistema que analiza currículums automáticamente para filtrar
candidatos en procesos de selección\"],\"kwargs\":{}}",


"output":
"{\"risk_level\":\"alto_riesgo\",\"confidence\":0.85,\"probabilities\":{\"alto\":0.0375,\"limitado\":0.
0375,\"alto_riesgo\":0.85,\"mínimo\":0.0375,\"inaceptable\":0.0375},\"shap_top_features\":[{\"f
eature\":\"num_palabras\",\"contribution\":0.8221570253372192},{\"feature\":\"svd_24\",\"cont
ribution\":0.6246916651725769},{\"feature\":\"svd_30\",\"contribution\":0.5895200967788696
},{\"feature\":\"svd_2\",\"contribution\":0.5856242775917053},{\"feature\":\"svd_12\",\"contribu
tion\":0.48583847284317017}],\"annex3_override\":true,\"annex3_ref\":\"Anexo III cat.
4.a\",\"ml_prediction\":{\"risk_level\":\"inaceptable\",\"confidence\":0.9939029812812805,\"pro
babilities\":{\"inaceptable\":0.9939,\"alto\":0.0019,\"limitado\":0.0002,\"mínimo\":0.004}},\"shap
_explanation\":\"Factores principales para 'alto_riesgo': num_palabras, svd_24, svd_30.\"}",
"metadata":
"{\"risk_level\":\"alto_riesgo\",\"confidence\":0.85,\"probabilities\":{\"alto\":0.0375,\"limitado\":0.
0375,\"alto_riesgo\":0.85,\"mínimo\":0.0375,\"inaceptable\":0.0375}}"
}
]

###### Análisis de Code Claude

**Lo que funcionó:**

```
Componente Estado Detalle
```
```
Orchestrator routing OK Bedrock eligió correctamente el clasificador, no RAG
```
```
Model load OK classifier_dataset_fusionado/model, 107 features,
tfidf_svd_manual
```
```
ML prediction OK XGBoost: "inaceptable" 99.39%
```
```
Annex III override OK Corrección a "alto_riesgo" vía Anexo III cat. 4.a
```
```
Latencia Excelente ~0.6 segundos total
```
```
Langfuse OK Span completo con probabilities, SHAP, metadata
```
```
Disclaimer + cita
legal
```
```
OK Anexo III cat. 4.a citado correctamente
```

**La clasificación final es legalmente correcta** — cribado de CVs cae en Annex III cat. 4.a (sistemas IA
en empleo) → alto riesgo.
**Problemas identificados:**

**1. SHAP features no interpretables**

"shap_top_features": [

{"feature": "num_palabras", "contribution": 0.82},

{"feature": "svd_24", "contribution": 0.62},

{"feature": "svd_30", "contribution": 0.59}

]

svd_24, svd_30 son dimensiones latentes — no significan nada para un usuario ni para un evaluador.
Esto debilita la explicabilidad del sistema en la presentación.

**2. Probabilidades post-override hardcodeadas**

"probabilities": {"alto": 0.0375, "limitado": 0.0375,

"alto_riesgo": 0.85, "mínimo": 0.0375, "inaceptable": 0.0375}

Las cuatro clases no-overrideadas tienen exactamente el mismo valor. Parece una distribución
artificial, no una redistribución real de probabilidades. Pasa desapercibido en la UI pero cualquier
evaluador que vea los logs lo notará.

**3. Discrepancia ML vs. final no explicada al usuario**
El modelo dijo "inaceptable" (99%), el sistema entregó "alto_riesgo". La UI no menciona que hubo un
override. Para transparencia sería útil indicarlo.

**Veredicto Query 2:** Funcionamiento correcto y rápido. Los problemas son de
presentación/explicabilidad, no de pipeline.


### Query 3

###### Input en chat UI

Genera un informe de cumplimiento para un sistema de scoring crediticio automático.

###### Output en chat UI

## Informe de Cumplimiento del Sistema

## de Scoring Crediticio Automático

#### 1. Resumen Ejecutivo

El sistema descrito es un sistema de scoring crediticio automático que evalúa la
solvencia crediticia de los usuarios basándose en varios factores como el historial
de pagos, ingresos y deudas. Este sistema ha sido clasificado como de alto riesgo
debido a la naturaleza sensible y crítica de las decisiones que toma.

#### 2. Clasificación de Riesgo

El sistema ha sido clasificado como de alto riesgo según el Anexo III cat. 5.b del
Reglamento de IA (AI Act), que establece que se debe establecer, implantar,
documentar y mantener un sistema de gestión de riesgos en relación con los
sistemas de IA de alto riesgo.

#### 3. Obligaciones Aplicables

Según el nivel de riesgo asignado, el sistema debe cumplir con las siguientes
obligaciones:

**3.1 Sistema de Gestión de Riesgos**

De acuerdo con el Anexo III cat. 5.b del AI Act:

"Se establecerá, implantará, documentará y mantendrá un sistema de gestión de
riesgos en relación con los sistemas de IA de alto riesgo."

**3.2 Conservación de la Documentación**

De acuerdo con el Art. 18 del AI Act:

"Se conservará la documentación necesaria para demostrar el cumplimiento de los
requisitos del Reglamento."

**3.3 Transparencia y Comunicación de Información**


De acuerdo con el Art. 13 del AI Act:

"Se debe aclarar y comunicar información relevante a los responsables del
despliegue del sistema."

**3.4 Precisión, Solidez y Ciberseguridad**

De acuerdo con el Art. 15 del AI Act:

"Se debe garantizar la precisión, solidez y ciberseguridad del sistema,
específicamente en los puntos uno, dos y tres."

**3.5 Vigilancia Humana**

De acuerdo con el AI Act:

"Este capítulo del documento recoge el detalle de las medidas necesarias para
cubrir los requisitos de Vigilancia humana expuestos en el artículo 14 del
Reglamento."

#### 4. Citas Legales

```
● AI Act, Anexo III cat. 5.b - Sistema de gestión de riesgos
● AI Act, Art. 13 - Transparencia y comunicación de información
● AI Act, Art. 15 - Precisión, solidez y ciberseguridad
● AI Act, Art. 18 - Conservación de la documentación
```
#### 5. Recomendaciones

```
● Implementar un sistema de gestión de riesgos detallado y documentado
según el Anexo III cat. 5.b.
● Mantener documentación adecuada para demostrar el cumplimiento según
el Art. 18.
● Comunicar información relevante a los responsables del despliegue según
el Art. 13.
● Garantizar la precisión, solidez y ciberseguridad del sistema según el Art.
15.
● Establecer medidas de vigilancia humana según el Art. 14.
```
No se dispone de información suficiente en el corpus consultado para otras
secciones.

_Informe preliminar generado por IA. Consulte profesional jurídico._


###### Salida en docker logs

2026-03-02 16:51:05,923 INFO langchain_aws.chat_models.bedrock_converse Using
Bedrock Converse API to generate response
2026-03-02 16:51:06,791 INFO src.classifier.main Anexo III override: ML='inaceptable'
(96%) → 'alto_riesgo' [Anexo III cat. 5.b]
2026-03-02 16:51:06,798 INFO langchain_aws.chat_models.bedrock_converse Using
Bedrock Converse API to generate response
Batches: 100%|██████████| 1/1 [00:00<00:00, 7.02it/s]
Batches: 100%|██████████| 1/1 [00:00<00:00, 7.74it/s]
Batches: 100%|██████████| 1/1 [00:00<00:00, 10.61it/s]
Batches: 100%|██████████| 1/1 [00:00<00:00, 8.52it/s]
Batches: 100%|██████████| 1/1 [00:00<00:00, 7.67it/s]
Batches: 100%|██████████| 1/1 [00:00<00:00, 9.81it/s]
2026-03-02 16:51:08,380 INFO langchain_aws.chat_models.bedrock_converse Using
Bedrock Converse API to generate response
2026-03-02 16:51:11,901 INFO langchain_aws.chat_models.bedrock_converse Using
Bedrock Converse API to generate response

###### Logs de langfuse en JSON

Sigue duplicando.

[
{
"id": "afb01f38-d96f-419c-82f5-6b793c27a71a",
"type": "SPAN",
"name": "classifier.predict_risk (afb01f38)",
"startTime": "2026-03-02T16:51:06.777Z",
"endTime": "2026-03-02T16:51:06.792Z",
"depth": 0,
"input": "{\"args\":[\"Un sistema de scoring crediticio automático que evalúa la solvencia
crediticia de los usuarios basado en varios factores como historial de pagos, ingresos y
deudas.\"],\"kwargs\":{}}",
"output":
"{\"risk_level\":\"alto_riesgo\",\"confidence\":0.85,\"probabilities\":{\"alto\":0.0375,\"limitado\":0.
0375,\"alto_riesgo\":0.85,\"mínimo\":0.0375,\"inaceptable\":0.0375},\"shap_top_features\":[{\"f
eature\":\"svd_30\",\"contribution\":0.6615961790084839},{\"feature\":\"svd_24\",\"contributio
n\":0.6521779894828796},{\"feature\":\"svd_2\",\"contribution\":0.4997721016407013},{\"feat
ure\":\"svd_10\",\"contribution\":-0.3754081130027771},{\"feature\":\"svd_22\",\"contribution\":
0.32340407371520996}],\"annex3_override\":true,\"annex3_ref\":\"Anexo III cat.
5.b\",\"ml_prediction\":{\"risk_level\":\"inaceptable\",\"confidence\":0.9608787298202515,\"pro
babilities\":{\"inaceptable\":0.9609,\"alto\":0.0186,\"limitado\":0.0145,\"mínimo\":0.006}},\"shap
_explanation\":\"Factores principales para 'alto_riesgo': svd_30, svd_24, svd_2.\"}",
"metadata":
"{\"risk_level\":\"alto_riesgo\",\"confidence\":0.85,\"probabilities\":{\"alto\":0.0375,\"limitado\":0.
0375,\"alto_riesgo\":0.85,\"mínimo\":0.0375,\"inaceptable\":0.0375}}"
}


]

[
{
"id": "37ad0d6f-9244-42b7-9ffd-f1e459f3dea0",
"type": "SPAN",
"name": "retriever.search (37ad0d6f)",
"startTime": "2026-03-02T16:51:07.580Z",
"endTime": "2026-03-02T16:51:07.739Z",
"depth": 0,
"input": "{\"args\":[\"sistema de gestión de riesgos Artículo 9\"],\"kwargs\":{\"k\":1}}",
"output": "[{\"id\":\"adefc1a372f0bc58a3f2c19b63d7b372\",\"text\":\"Art.9 – Sistema de
gestión de riesgos\\n1. Se establecerá, implantará, documentará y mantendrá un sistema
de\\ngestión de riesgos en relación con los sistemas de IA de alto
riesgo.\",\"metadata\":{\"id\":\"adefc1a372f0bc58a3f2c19b63d7b372\",\"doc_date\":\"10
diciembre
2025\",\"doc_title\":\"0\",\"file\":\"05-guia-de-gestion-de-riesgos.pdf\",\"source\":\"aesia\",\"unit
_id\":\"3.2\",\"sub_index\":0,\"unit_type\":\"section\",\"unit_title\":\"3.2 Contenido del
artículo\",\"unit_index\":41},\"distance\":0.1656419038772583}]",
"metadata":
"{\"mode\":\"soft\",\"k\":1,\"n_results\":1,\"min_distance\":0.1656,\"max_distance\":0.1656}"
},
{
"id": "916f6c8f-0b9a-434a-95d9-828d08ea3028",
"type": "SPAN",
"name": "retriever.search (916f6c8f)",
"startTime": "2026-03-02T16:51:07.739Z",
"endTime": "2026-03-02T16:51:07.879Z",
"depth": 0,
"input": "{\"args\":[\"datos y gobernanza de datos Artículo 10\"],\"kwargs\":{\"k\":1}}",
"output": "[{\"id\":\"b635ddb8fe0af6d5ff92ad445bd39591\",\"text\":\"Artículo 10.
Tratamiento de datos de naturaleza penal.\\nTítulo III. Derechos de las personas.\\nCapítulo
I. Transparencia e
información.\",\"metadata\":{\"file\":\"LOPDGDD_LO_3_2018_BOE.pdf\",\"source\":\"lopd_rgp
d\",\"unit_index\":9,\"unit_title\":\"Artículo
10\",\"unit_id\":\"10\",\"sub_index\":0,\"id\":\"b635ddb8fe0af6d5ff92ad445bd39591\",\"doc_title
\":\"LOPDGDD_LO_3_2018_BOE.pdf\",\"unit_type\":\"article\"},\"distance\":0.2534858286380
768}]",
"metadata":
"{\"mode\":\"soft\",\"k\":1,\"n_results\":1,\"min_distance\":0.2535,\"max_distance\":0.2535}"
},
{
"id": "eb9ab1fd-d693-477c-9e78-b58d1b22b2e5",
"type": "SPAN",
"name": "retriever.search (eb9ab1fd)",
"startTime": "2026-03-02T16:51:07.879Z",
"endTime": "2026-03-02T16:51:07.984Z",
"depth": 0,


"input": "{\"args\":[\"documentación técnica Artículo 11\"],\"kwargs\":{\"k\":1}}",
"output": "[{\"id\":\"3eb1d9726155138a8d383dcb84d910d5\",\"text\":\"artículo 97 al objeto
de modificar el anexo IV, cuando sea necesario, para\\ngarantizar que, en vista de los
avances técnicos, la documentación técnica\\nproporcione toda la información necesaria
para evaluar si el sistema cumple los\\nrequisitos establecidos en la presente sección.\\nAI
Act\\n\\n11\\nArt.18 – Conservación de la
documentación\",\"metadata\":{\"unit_type\":\"chapter\",\"source\":\"aesia\",\"id\":\"3eb1d9726
155138a8d383dcb84d910d5\",\"unit_title\":\"3. La Comisión estará facultada para adoptar
actos delegados con arreglo
al\",\"doc_title\":\"0\",\"file\":\"15-guia-documentacion-tecnica.pdf\",\"doc_date\":\"10
diciembre
2025\",\"unit_id\":\"3\",\"unit_index\":29,\"sub_index\":0},\"distance\":0.2466273158788681}]",
"metadata":
"{\"mode\":\"soft\",\"k\":1,\"n_results\":1,\"min_distance\":0.2466,\"max_distance\":0.2466}"
},
{
"id": "238a2477-e3d7-4e0d-b728-b147b3849702",
"type": "SPAN",
"name": "retriever.search (238a2477)",
"startTime": "2026-03-02T16:51:07.985Z",
"endTime": "2026-03-02T16:51:08.115Z",
"depth": 0,
"input": "{\"args\":[\"transparencia información usuarios Artículo 13\"],\"kwargs\":{\"k\":1}}",
"output": "[{\"id\":\"23846950d86cb3a8f0ba5b43fe88ce7f\",\"text\":\"Art.13 – Transparencia
y comunicación de información a\\nlos responsables del
despliegue\",\"metadata\":{\"unit_index\":35,\"unit_id\":\"3.2\",\"doc_date\":\"10 diciembre
2025\",\"file\":\"08-guia-transparencia.pdf\",\"doc_title\":\"0\",\"id\":\"23846950d86cb3a8f0ba5
b43fe88ce7f\",\"sub_index\":0,\"unit_title\":\"3.2. Contenido de los artículos en el Reglamento
de IA\",\"unit_type\":\"section\",\"source\":\"aesia\"},\"distance\":0.2604348063468933}]",
"metadata":
"{\"mode\":\"soft\",\"k\":1,\"n_results\":1,\"min_distance\":0.2604,\"max_distance\":0.2604}"
},
{
"id": "00c9491e-883b-4422-a677-57b8002d9845",
"type": "SPAN",
"name": "retriever.search (00c9491e)",
"startTime": "2026-03-02T16:51:08.115Z",
"endTime": "2026-03-02T16:51:08.256Z",
"depth": 0,
"input": "{\"args\":[\"vigilancia y supervisión humana Artículo 14\"],\"kwargs\":{\"k\":1}}",
"output": "[{\"id\":\"6671fefb499211861453865b2a2fd76e\",\"text\":\"Este capítulo del
documento recoge el detalle de las medidas necesarias para cubrir los\\nrequisitos de
Vigilancia humana expuestos en el artículo 14 del
Reglamento.\",\"metadata\":{\"unit_index\":44,\"doc_date\":\"10 diciembre
2025\",\"file\":\"06-guia-vigilancia-humana.pdf\",\"sub_index\":0,\"source\":\"aesia\",\"unit_type
\":\"section\",\"unit_title\":\"4.2 Medidas aplicables para conseguir la Vigilancia
Humana\",\"unit_id\":\"4.2\",\"doc_title\":\"Empresas


desarrollando\",\"id\":\"6671fefb499211861453865b2a2fd76e\"},\"distance\":0.230919376015
66315}]",
"metadata":
"{\"mode\":\"soft\",\"k\":1,\"n_results\":1,\"min_distance\":0.2309,\"max_distance\":0.2309}"
},
{
"id": "051235f6-d01b-44bb-be35-44b90fbea9df",
"type": "SPAN",
"name": "retriever.search (051235f6)",
"startTime": "2026-03-02T16:51:08.256Z",
"endTime": "2026-03-02T16:51:08.369Z",
"depth": 0,
"input": "{\"args\":[\"precisión robustez y ciberseguridad Artículo 15\"],\"kwargs\":{\"k\":1}}",
"output": "[{\"id\":\"a2b1b4aa97262299719ca1d4f9bc7b0b\",\"text\":\"Aclarar, que dentro
del artículo 15 en el que se trata de precisión, solidez y ciberseguridad, se\\nhabla
específicamente de precisión exclusivamente en los puntos uno, dos y tres.\\nArt.15 –
Precisión, solidez y
ciberseguridad\",\"metadata\":{\"unit_type\":\"section\",\"unit_index\":42,\"id\":\"a2b1b4aa9726
2299719ca1d4f9bc7b0b\",\"file\":\"09-guia-de-precision.pdf\",\"unit_title\":\"3.2 Contenido de
los artículos en el Reglamento de IA\",\"doc_title\":\"0\",\"unit_id\":\"3.2\",\"doc_date\":\"10
diciembre 2025\",\"source\":\"aesia\",\"sub_index\":0},\"distance\":0.1884719878435135}]",
"metadata":
"{\"mode\":\"soft\",\"k\":1,\"n_results\":1,\"min_distance\":0.1885,\"max_distance\":0.1885}"
},
{
"id": "57ba1b27-8222-492e-ad61-b49a20d37eeb",
"type": "SPAN",
"name": "report.generate (57ba1b27)",
"startTime": "2026-03-02T16:51:08.369Z",
"endTime": "2026-03-02T16:51:11.896Z",
"depth": 0,
"input": "{\"args\":[\"Un sistema de scoring crediticio automático que evalúa la solvencia
crediticia de los usuarios basado en varios factores como historial de pagos, ingresos y
deudas.\",\"alto_riesgo\",[\"aesia — 3.2 Contenido del artículo\\nArt.9 – Sistema de gestión
de riesgos\\n1. Se establecerá, implantará, documentará y mantendrá un sistema
de\\ngestión de riesgos en relación con los sistemas de IA de alto riesgo.\",\"lopd_rgpd —
Artículo 10\\nArtículo 10. Tratamiento de datos de naturaleza penal.\\nTítulo III. Derechos de
las personas.\\nCapítulo I. Transparencia e información.\",\"aesia — 3. La Comisión estará
facultada para adoptar actos delegados con arreglo al\\nartículo 97 al objeto de modificar el
anexo IV, cuando sea necesario, para\\ngarantizar que, en vista de los avances técnicos, la
documentación técnica\\nproporcione toda la información necesaria para evaluar si el
sistema cumple los\\nrequisitos establecidos en la presente sección.\\nAI
Act\\n\\n11\\nArt.18 – Conservación de la documentación\",\"aesia — 3.2. Contenido de los
artículos en el Reglamento de IA\\nArt.13 – Transparencia y comunicación de información
a\\nlos responsables del despliegue\",\"aesia — 4.2 Medidas aplicables para conseguir la
Vigilancia Humana\\nEste capítulo del documento recoge el detalle de las medidas
necesarias para cubrir los\\nrequisitos de Vigilancia humana expuestos en el artículo 14 del
Reglamento.\",\"aesia — 3.2 Contenido de los artículos en el Reglamento de IA\\nAclarar,


que dentro del artículo 15 en el que se trata de precisión, solidez y ciberseguridad,
se\\nhabla específicamente de precisión exclusivamente en los puntos uno, dos y
tres.\\nArt.15 – Precisión, solidez y ciberseguridad\"]],\"kwargs\":{}}",
"output": "# Informe de Cumplimiento del Sistema de Scoring Crediticio Automático\n\n##

1. Resumen Ejecutivo\nEl sistema descrito es un sistema de scoring crediticio automático
que evalúa la solvencia crediticia de los usuarios basándose en varios factores como el
historial de pagos, ingresos y deudas. Este sistema ha sido clasificado como de alto riesgo
debido a la naturaleza sensible y crítica de las decisiones que toma.\n\n## 2. Clasificación
de Riesgo\nEl sistema ha sido clasificado como de **alto riesgo** según el **Art. 9** del
Reglamento de IA (AI Act), que establece que se debe establecer, implantar, documentar y
mantener un sistema de gestión de riesgos en relación con los sistemas de IA de alto
riesgo.\n\n## 3. Obligaciones Aplicables\nSegún el nivel de riesgo asignado, el sistema
debe cumplir con las siguientes obligaciones:\n\n### 3.1 Sistema de Gestión de
Riesgos\nDe acuerdo con el **Art. 9** del AI Act:\n> \"Se establecerá, implantará,
documentará y mantendrá un sistema de gestión de riesgos en relación con los sistemas de
IA de alto riesgo.\"\n\n### 3.2 Conservación de la Documentación\nDe acuerdo con el **Art.
18** del AI Act:\n> \"Se conservará la documentación necesaria para demostrar el
cumplimiento de los requisitos del Reglamento.\"\n\n### 3.3 Transparencia y Comunicación
de Información\nDe acuerdo con el **Art. 13** del AI Act:\n> \"Se debe aclarar y comunicar
información relevante a los responsables del despliegue del sistema.\"\n\n### 3.4 Precisión,
Solidez y Ciberseguridad\nDe acuerdo con el **Art. 15** del AI Act:\n> \"Se debe garantizar
la precisión, solidez y ciberseguridad del sistema, específicamente en los puntos uno, dos y
tres.\"\n\n### 3.5 Vigilancia Humana\nDe acuerdo con el AI Act:\n> \"Este capítulo del
documento recoge el detalle de las medidas necesarias para cubrir los requisitos de
Vigilancia humana expuestos en el artículo 14 del Reglamento.\"\n\n## 4. Citas Legales\n-
**AI Act, Art. 9** - Sistema de gestión de riesgos\n- **AI Act, Art. 13** - Transparencia y
comunicación de información\n- **AI Act, Art. 15** - Precisión, solidez y ciberseguridad\n-
**AI Act, Art. 18** - Conservación de la documentación\n\n## 5. Recomendaciones\n-
**Implementar un sistema de gestión de riesgos** detallado y documentado según el Art.
9.\n- **Mantener documentación adecuada** para demostrar el cumplimiento según el Art.
18.\n- **Comunicar información relevante** a los responsables del despliegue según el Art.
13.\n- **Garantizar la precisión, solidez y ciberseguridad** del sistema según el Art. 15.\n-
**Establecer medidas de vigilancia humana** según el Art. 14.\n\nNo se dispone de
información suficiente en el corpus consultado para otras secciones.\n\n---\n*Informe
preliminar generado por IA. Consulte profesional jurídico.*",
"metadata":
"{\"risk_level\":\"alto_riesgo\",\"n_articles\":6,\"grounded\":true,\"model\":\"eu.amazon.nova-lit
e-v1:0\",\"report_length\":2729}"
}
]

###### Análisis de Code Claude

**Lo que funcionó:**

```
Componente Estado Detalle
Routing multi-tool OK Bedrock orquestó: classifier → 6×retriever → report.generate
```

```
Classifier OK "inaceptable" → override → "alto_riesgo" [Anexo III cat. 5.b]
6 retriever.search (k=1) Parcial 4/6 correctos, 2 fallidos
report.generate OK Bedrock Nova Lite, 3.5s, markdown estructurado
Latencia total Buena ~5s (sin Ollama = sin cuello de botella)
Disclaimer + citas reales OK ✓
```
**Problema 1: Retrieval falla en 2 de 6 artículos**

```
Query de retrieval Esperado Obtenido Distancia
"datos y gobernanza Artículo 10" EU AI Act Art. 10 LOPD Art. 10 (datos penales) 0.2535
"documentación técnica Artículo 11" EU AI Act Art. 11 Chunk sobre Art. 18 + Annex IV 0.2466
```
Resultado: el informe final **no incluye Art. 10 ni Art. 11** , dos obligaciones críticas para sistemas de
alto riesgo (gobernanza de datos y documentación técnica). Falta también Art. 12 (registro de
eventos).
**Problema 2: "Sigue duplicando"**
No veo duplicados en el JSON que compartiste, pero mencionas que persiste. ¿Puedes confirmar
dónde lo ves — en la Langfuse UI (trazas duplicadas), en los docker logs (spans repetidos), o en el
output del chat?
**Problema 3: Discrepancia Langfuse vs UI**
El span report.generate dice _"según el Art. 9"_ en la clasificación, pero la UI muestra _"según el Anexo
III cat. 5.b"_. Esto indica que Bedrock reescribió el report en un paso final post-report.generate — lo
cual es correcto en contenido pero significa que el output del tool y lo que ve el usuario difieren.
Puede ser confuso para debugging.

**Resumen de los 3 queries hasta ahora:**

```
Q1 (RAG) Q2 (Clasificador) Q3 (Informe)
Pipeline completo ✓ ✓ ✓
Latencia aceptable ✗ ~4min ✓ <1s ✓ ~5s
Calidad respuesta Parcial Buena Parcial
Citas legales correctas ✓ ✓ Parcial (2 errores)
Langfuse ✓ ✓ ✓ (+ bug duplicado?)
```

### Query 4

###### Input en chat UI

Tengo un sistema de IA que evalúa el riesgo de recidiva de presos para recomendar libertad
condicional. Clasifícalo, busca los artículos aplicables y genera un informe de cumplimiento.

###### Output en chat UI

Aquí tienes el análisis y el informe generado para tu sistema de IA que evalúa el
riesgo de recidiva de presos para recomendar libertad condicional:

#### 1. Clasificación de Riesgo

Clasificación: ALTO_RIESGO Confianza: 85% Referencia legal: Anexo III cat. 6

#### 2. Obligaciones Aplicables

1. Sistema de Gestión de Riesgos (Art. 9 del Reglamento de IA)
2. Conservación de la Documentación (Art. 18 del Reglamento de IA)
3. Transparencia y Comunicación de Información (Art. 13 del Reglamento de
    IA)
4. Vigilancia Humana (Capítulo del Reglamento sobre Vigilancia Humana)
5. Precisión, Solidez y Ciberseguridad (Puntos uno, dos y tres del Art. 15 del
    Reglamento de IA)

#### 3. Recomendaciones

```
● Implementar un sistema de gestión de riesgos conforme al Art. 9 del
Reglamento de IA.
● Documentar adecuadamente el sistema de gestión de riesgos y mantener
la documentación actualizada.
● Asegurar la transparencia y comunicación de información a los
responsables del despliegue, según el Art. 13 del Reglamento de IA.
● Establecer medidas de vigilancia humana conforme al Art. 14 del
Reglamento de IA.
● Garantizar la precisión, solidez y ciberseguridad del sistema,
específicamente en los puntos uno, dos y tres del Art. 15 del Reglamento
de IA.
● Conservar la documentación según lo establecido en el Art. 18 del
Reglamento de IA.
```
**Informe preliminar generado por IA. Consulte profesional jurídico.**

Este informe se basa en los análisis y las obligaciones normativas según el EU AI
Act y la legislación española de IA. Recuerda que, para asegurar el cumplimiento


completo y evitar cualquier riesgo de no conformidad, es esencial consultar a un
profesional jurídico especializado en inteligencia artificial.

Si tienes más preguntas o necesitas detalles adicionales, no dudes en preguntar.

###### Salida en docker logs

2026-03-02 16:52:47,379 INFO langchain_aws.chat_models.bedrock_converse Using
Bedrock Converse API to generate response
2026-03-02 16:52:48,744 INFO src.classifier.main Anexo III override: ML='inaceptable'
(99%) → 'alto_riesgo' [Anexo III cat. 6]
2026-03-02 16:52:48,748 INFO src.classifier.main Anexo III override: ML='inaceptable'
(99%) → 'alto_riesgo' [Anexo III cat. 6]
Batches: 100%|██████████| 1/1 [00:00<00:00, 5.93it/s]
Batches: 100%|██████████| 1/1 [00:00<00:00, 3.62it/s]
Batches: 100%|██████████| 1/1 [00:00<00:00, 5.58it/s]
Batches: 100%|██████████| 1/1 [00:00<00:00, 8.30it/s]
Batches: 100%|██████████| 1/1 [00:00<00:00, 7.90it/s]
Batches: 100%|██████████| 1/1 [00:00<00:00, 7.08it/s]
Batches: 100%|██████████| 1/1 [00:00<00:00, 7.86it/s]
2026-03-02 16:52:49,708 INFO langchain_aws.chat_models.bedrock_converse Using
Bedrock Converse API to generate response
[GIN] 2026/03/02 - 16:54:00 | 200 | 1m11s | 127.0.0.1 | POST "/api/chat"
[GIN] 2026/03/02 - 16:55:15 | 200 | 1m14s | 127.0.0.1 | POST "/api/chat"
[GIN] 2026/03/02 - 16:56:55 | 200 | 1m39s | 127.0.0.1 | POST "/api/chat"
[GIN] 2026/03/02 - 16:57:52 | 200 | 57.388177525s | 127.0.0.1 | POST "/api/chat"
[GIN] 2026/03/02 - 16:59:05 | 200 | 1m13s | 127.0.0.1 | POST "/api/chat"
2026-03-02 16:59:05,907 INFO langchain_aws.chat_models.bedrock_converse Using
Bedrock Converse API to generate response

###### Logs de langfuse en JSON

[
{
"id": "dc6dc9a3-ad87-45b9-8513-b70f316e54cb",
"type": "SPAN",
"name": "classifier.predict_risk (dc6dc9a3)",
"startTime": "2026-03-02T16:52:48.713Z",
"endTime": "2026-03-02T16:52:48.745Z",
"depth": 0,
"input": "{\"args\":[\"Un sistema de IA que evalúa el riesgo de recidiva de presos para
recomendar libertad condicional\"],\"kwargs\":{}}",
"output":
"{\"risk_level\":\"alto_riesgo\",\"confidence\":0.85,\"probabilities\":{\"alto\":0.0375,\"limitado\":0.
0375,\"alto_riesgo\":0.85,\"mínimo\":0.0375,\"inaceptable\":0.0375},\"shap_top_features\":[{\"f
eature\":\"num_palabras\",\"contribution\":1.0230586528778076},{\"feature\":\"svd_24\",\"cont
ribution\":0.9355978965759277},{\"feature\":\"svd_30\",\"contribution\":0.6751113533973694}


,{\"feature\":\"svd_32\",\"contribution\":0.5668127536773682},{\"feature\":\"svd_2\",\"contributi
on\":0.5275657773017883}],\"annex3_override\":true,\"annex3_ref\":\"Anexo III cat.
6\",\"ml_prediction\":{\"risk_level\":\"inaceptable\",\"confidence\":0.992236316204071,\"proba
bilities\":{\"inaceptable\":0.9922,\"alto\":0.0073,\"limitado\":0.0002,\"mínimo\":0.0003}},\"shap_
explanation\":\"Factores principales para 'alto_riesgo': num_palabras, svd_24, svd_30.\"}",
"metadata":
"{\"risk_level\":\"alto_riesgo\",\"confidence\":0.85,\"probabilities\":{\"alto\":0.0375,\"limitado\":0.
0375,\"alto_riesgo\":0.85,\"mínimo\":0.0375,\"inaceptable\":0.0375}}"
}
]

[
{
"id": "c9804b8c-2d9a-40dc-8c7d-12c392301ea6",
"type": "SPAN",
"name": "rag.retrieve (c9804b8c)",
"startTime": "2026-03-02T16:52:48.717Z",
"endTime": "2026-03-02T16:52:49.034Z",
"depth": 0,
"input": "{\"args\":[\"sistema de IA evalúa riesgo recidiva presos libertad condicional
normativa EU AI Act y legislación española de IA\"],\"kwargs\":{}}",
"output": "[{\"doc\":\"Procedimiento aplicable a escala nacional a los sistemas de IA que
presenten un riesgo\\n1. Los sistemas de IA que presentan un riesgo se entenderán como
«productos que presentan un riesgo» tal como se definen en el artículo 3, punto 19, del
Reglamento (UE) 2019/1020, en la medida en que presenten riegos que afecten a la salud,
la seguridad o los derechos fundamentales de las personas.\\n2. Cuando la autoridad de
vigilancia del mercado de un Estado miembro tenga motivos suficientes para considerar que
un sistema de IA presenta un riesgo mencionado en el apartado 1 del presente artículo,
efectuará una evaluación del sistema de IA de que se trate para verificar su cumplimiento de
todos los requisitos y obligaciones establecidos en el presente Reglamento. Debe prestarse
una especial atención a los sistemas de IA que presenten un riesgo para los colectivos
vulnerables. Cuando se detecten riesgos para los derechos fundamentales, la autoridad de
vigilancia del mercado informará también a las autoridades u organismos públicos
nacionales pertinentes a que se refiere el artículo 77, apartado 1, y cooperará plenamente
con ellos. Los operadores pertinentes cooperarán en lo necesario con la autoridad de
vigilancia del mercado y con las demás autoridades u organismos públicos nacionales a que
se refiere el artículo 77, apartado 1.\",\"metadata\":{\"doc_date\":\"13 junio
2024\",\"id\":\"3308e8cfc3db373d8520ec6798a48cb0\",\"unit_id\":\"79\",\"file\":\"EU_AI_Act_2
024_1689_ES.html\",\"doc_title\":\"L_202401689ES.000101.fmx.xml\",\"source\":\"eu_ai_act\
",\"sub_index\":0,\"unit_title\":\"Artículo
79\",\"unit_type\":\"article\",\"unit_index\":101},\"score\":0.7201481461524963},{\"doc\":\"de
otros derechos en juego, como por ejemplo la no discriminación en el tratamiento
de\\ndatos. De este modo, a la hora de realizar un análisis de riesgos o evaluación de
impacto\\nde un sistema de IA de alto riesgo, será especialmente impor tante para la
organización\\ntener en cuenta los instrumentos que se hayan desarrollado para el
cumplimiento de la\\nprotección de datos. Es más, la mejor práctica será desarrollar
conjuntamente estos análisis\\nde riesgos de impacto en derechos y, para ello, in tegrar,
cooperar o coordinar con los\\nsujetos que en la organización tengan especiales


atribuciones en la materia, como pueda\\nser el delegado de protección de datos.\\nPosible
Vulneración: Anexo II y III del Reglamento\\nSon plenamente válidos los ejemplos indicados
previamente mencionados en el derecho\\nal respeto a la vida privada y familiar.\\n4)
Libertades de expresión y de información, de reunión y de asociación. Artículo 11\\ny 12 de
la Carta.\\n3 Más información en :
https://www.lavozdegalicia.es/noticia/sociedad/2017/12/21/lista-juguetes-espia-crece-tras-an
alisis-\\nadvierte-riesgos-intolerables-dos-robots/0003_201712G21P28991.htm\\nhttps://ww
w.aepd.es/es/node/824\\n4 Más información
en:\\nhttps://www.incibe.es/incibe/informacion-corporativa/con-quien-trabajamos/proyectos-e
uropeos/is4k\",\"metadata\":{\"doc_date\":\"10 diciembre
2025\",\"unit_index\":81,\"sub_index\":7,\"unit_id\":\"8.1.2\",\"doc_title\":\"0\",\"file\":\"05-guia-d
e-gestion-de-riesgos.pdf\",\"unit_type\":\"subsection\",\"id\":\"f8da8a95be217c0ed5b2559d26
6e2ccc\",\"unit_title\":\"8.1.2 Anexo A.II - Elementos relacionados con la Carta de los
Derechos\",\"source\":\"aesia\"},\"score\":0.7441806197166443},{\"doc\":\"9\\nA) Sistemas
prohibidos: los usos de IA que se encuentren en este nivel de la jerarquía están\\nprohibidos
debido al alto riego que entrañan: sistemas IA que suponen una amenaza para
la\\nseguridad, la vida o los derechos fundamentales. En este nivel se encuentran, por
ejemplo, los\\nsistemas con alguna de las siguientes funciones:\\n• Manipulación subliminal
del comportamiento de una persona de manera que\\npueda causarle daños físicos o
psicológicos a él o a otros.\\n• Explotación de vulnerabilidades de grupos sociales para
manipular su\\ncomportamiento de forma que pueda causarles daño a ellos o a otros.\\n•
Evaluación o clasificación de personas o grupos por su comportamiento social que\\npueda
perjudicarlos desproporcionadamente en el ámbito del comportamiento\\nobservado, o
perjudicarlos en ámbitos distintos a donde se observó.\\n• Identificación biométrica en
tiempo real en espacios de acceso público para\\nautoridades policiales, salvo casos
tasados y mediando autorización.\\nLa Comisión Europea ha preparado unas directrices con
el fin de aclarar la interpretación de\\nciertos casos concretos (Guidelines on prohibited
artificial intelligence practices established by\\nRegulation (EU) 20241689 (AI Act)) 1.\\nB)
Sistemas de Alto Riesgo: el segundo nivel se reserva a los sistemas de alto riesgo,
pero\\ncuyo uso está permitido, a los que el Reglamento dedica la mayoría de los requisitos
y\\nobligaciones que deben cumplir los distintos roles que participan en la cadena de valor
de la\\npuesta en uso de un sistema IA (operadores). Se dividen en dos tipos de
sistemas:\\nB1) Productos o componentes de seguridad de alto riesgo contemplados
en\\nlegislación de armonización:\\no Sistemas de IA que sea un componente de seguridad
de alguno de los productos\\ncontemplados en la legislación de armonización de la Unión
recogidos en el Anexo\\nI del Reglamento o,\\no Que el propio sistema de IA como
producto, deba someterse a una evaluación de
la\",\"metadata\":{\"sub_index\":1,\"unit_index\":18,\"source\":\"aesia\",\"doc_date\":\"10
diciembre 2025\",\"unit_title\":\"2.3 Niveles de riesgo del Reglamento Europeo de
IA\",\"unit_id\":\"2.3\",\"unit_type\":\"section\",\"file\":\"guia_01_intro_reglamento_ia.pdf\",\"id\":
\"f017301705f02276959c1fcba419dfc2\",\"doc_title\":\"1\"},\"score\":0.7407159209251404},{\
"doc\":\"Art.13.3f - Transparencia y comunicación de\\ninformación a los responsables del
despliegue\\ncuando proceda, una descripción de los mecanismos incluidos en el sistema
de\\nIA de alto riesgo que permita a los responsables del despliegue recabar,\\nalmacenar e
interpretar correctamente los archivos de registro de conformidad\\ncon el artículo 12.\\nAI
Act\\nAI Act\\n\\n26\\nQué entendemos\\nEn la línea de facilitar el entendimiento y uso
apropiado de los sistemas por parte de los\\nusuarios, se trata de describir e implantar los
mecanismos contenidos dentro del propio\\nsistema de IA de alto riesgo para permitir que


los usuarios del propio sistema puedan recoger,\\nguardar e interpretar correctamente los
logs, siempre que estos sean considerados\\nrelevantes. Pretende definir el alcance de lo
que una IA transparente debería ser.\\nConcretamente, menciona que los usuarios del
sistema deberían poder recog er, guardar e\\ninterpretar los logs del sistema siempre que
estos sean relevantes.\\nMedidas para llevarlo a cabo\\n• Las indicadas en la guía del
artículo 12 del Reglamento Europeo de la IA
(Registros).\\n\\n27\",\"metadata\":{\"unit_type\":\"subsection\",\"doc_date\":\"10 diciembre
2025\",\"file\":\"08-guia-transparencia.pdf\",\"source\":\"aesia\",\"doc_title\":\"0\",\"unit_id\":\"4.
3.6\",\"id\":\"c7fd5519725ea103444e499c4fd94879\",\"unit_title\":\"4.3.6. Apartado 3f.
Archivos de
registro\",\"unit_index\":52,\"sub_index\":0},\"score\":0.7324605286121368},{\"doc\":\"Como
norma general, el Reglamento se aplica por igual a las organizaciones privadas, a\\nlas
administraciones públicas y a las entidades del sector público. Ahora bien, se establece\\nla
obligación adicional para sistema de alto riesgo, que consiste en el desarrollo de
una\\nevaluación de impacto relativa a los derechos fundamentales.\\nCon el objetivo de
garantizar eficazmente la protección de los derechos fundamentales por\\nmedio de la
determinación de los riesgos específicos para los derechos de las personas y\\ncolectivos
que se vean afectados.\\nEIDF o FRIAs\\n(Evaluación de Impacto relativa a los derechos
fundamentales)\\nObligatoria antes del despliegue de un sistema de alto riesgo*\\nRealizada
por responsables de despliegue.\\nContenido\\n• Descripción procesos de uso del
sistema.\\n• Período de tiempo y frecuencia de uso.\\n• Categoría personas físicas y
colectivos afectados\\n• Riesgos de perjuicio específicos\\n• Descripción medidas de
supervisión humana\\n• Medidas en caso de que el riesgo se materialice (Mecanismos de
reclamación)\\nSistema utilizado en casos similares , responsable de despliegue basarse en
EIDF\\nrealizadas previamente o existentes.\\nParte del contenido ya incluido en EIPD
(Evaluación de Impacto de Protección de Datos),\\nEIDF la complementará.\\nNotificación a
AESIA (Pendiente de publicación modelo cuestionario por la AI Office)\\n*Excepción:
Infraestructuras Críticas\\n\\n14\",\"metadata\":{\"unit_id\":\"2.4.3\",\"doc_date\":\"10
diciembre 2025\",\"unit_index\":21,\"unit_title\":\"2.4.3 Particulares de los operadores del
sector
público\",\"file\":\"guia_01_intro_reglamento_ia.pdf\",\"doc_title\":\"1\",\"id\":\"410dbd9ea732c
c0ebd32f03d06220fb6\",\"source\":\"aesia\",\"sub_index\":0,\"unit_type\":\"subsection\"},\"sco
re\":0.7322337329387665}]",
"metadata": "{\"k\":5,\"n_docs_retrieved\":5}"
},
{
"id": "cdaded96-49d6-44a8-94c1-cff832601c2e",
"type": "SPAN",
"name": "retriever.search (cdaded96)",
"startTime": "2026-03-02T16:52:48.717Z",
"endTime": "2026-03-02T16:52:49.033Z",
"depth": 1,
"input": "{\"args\":[\"sistema de IA evalúa riesgo recidiva presos libertad condicional
normativa EU AI Act y legislación española de IA\"],\"kwargs\":{\"k\":5,\"mode\":\"soft\"}}",
"output": "[{\"id\":\"3308e8cfc3db373d8520ec6798a48cb0\",\"text\":\"Procedimiento
aplicable a escala nacional a los sistemas de IA que presenten un riesgo\\n1. Los sistemas
de IA que presentan un riesgo se entenderán como «productos que presentan un riesgo» tal
como se definen en el artículo 3, punto 19, del Reglamento (UE) 2019/1020, en la medida


en que presenten riegos que afecten a la salud, la seguridad o los derechos fundamentales
de las personas.\\n2. Cuando la autoridad de vigilancia del mercado de un Estado miembro
tenga motivos suficientes para considerar que un sistema de IA presenta un riesgo
mencionado en el apartado 1 del presente artículo, efectuará una evaluación del sistema de
IA de que se trate para verificar su cumplimiento de todos los requisitos y obligaciones
establecidos en el presente Reglamento. Debe prestarse una especial atención a los
sistemas de IA que presenten un riesgo para los colectivos vulnerables. Cuando se detecten
riesgos para los derechos fundamentales, la autoridad de vigilancia del mercado informará
también a las autoridades u organismos públicos nacionales pertinentes a que se refiere el
artículo 77, apartado 1, y cooperará plenamente con ellos. Los operadores pertinentes
cooperarán en lo necesario con la autoridad de vigilancia del mercado y con las demás
autoridades u organismos públicos nacionales a que se refiere el artículo 77, apartado
1.\",\"metadata\":{\"doc_date\":\"13 junio
2024\",\"id\":\"3308e8cfc3db373d8520ec6798a48cb0\",\"unit_id\":\"79\",\"file\":\"EU_AI_Act_2
024_1689_ES.html\",\"doc_title\":\"L_202401689ES.000101.fmx.xml\",\"source\":\"eu_ai_act\
",\"sub_index\":0,\"unit_title\":\"Artículo
79\",\"unit_type\":\"article\",\"unit_index\":101},\"distance\":0.27985185384750366},{\"id\":\"f8
da8a95be217c0ed5b2559d266e2ccc\",\"text\":\"de otros derechos en juego, como por
ejemplo la no discriminación en el tratamiento de\\ndatos. De este modo, a la hora de
realizar un análisis de riesgos o evaluación de impacto\\nde un sistema de IA de alto riesgo,
será especialmente impor tante para la organización\\ntener en cuenta los instrumentos que
se hayan desarrollado para el cumplimiento de la\\nprotección de datos. Es más, la mejor
práctica será desarrollar conjuntamente estos análisis\\nde riesgos de impacto en derechos
y, para ello, in tegrar, cooperar o coordinar con los\\nsujetos que en la organización tengan
especiales atribuciones en la materia, como pueda\\nser el delegado de protección de
datos.\\nPosible Vulneración: Anexo II y III del Reglamento\\nSon plenamente válidos los
ejemplos indicados previamente mencionados en el derecho\\nal respeto a la vida privada y
familiar.\\n4) Libertades de expresión y de información, de reunión y de asociación. Artículo
11\\ny 12 de la Carta.\\n3 Más información en :
https://www.lavozdegalicia.es/noticia/sociedad/2017/12/21/lista-juguetes-espia-crece-tras-an
alisis-\\nadvierte-riesgos-intolerables-dos-robots/0003_201712G21P28991.htm\\nhttps://ww
w.aepd.es/es/node/824\\n4 Más información
en:\\nhttps://www.incibe.es/incibe/informacion-corporativa/con-quien-trabajamos/proyectos-e
uropeos/is4k\",\"metadata\":{\"doc_date\":\"10 diciembre
2025\",\"unit_index\":81,\"sub_index\":7,\"unit_id\":\"8.1.2\",\"doc_title\":\"0\",\"file\":\"05-guia-d
e-gestion-de-riesgos.pdf\",\"unit_type\":\"subsection\",\"id\":\"f8da8a95be217c0ed5b2559d26
6e2ccc\",\"unit_title\":\"8.1.2 Anexo A.II - Elementos relacionados con la Carta de los
Derechos\",\"source\":\"aesia\"},\"distance\":0.2558193802833557},{\"id\":\"f017301705f0227
6959c1fcba419dfc2\",\"text\":\"9\\nA) Sistemas prohibidos: los usos de IA que se encuentren
en este nivel de la jerarquía están\\nprohibidos debido al alto riego que entrañan: sistemas
IA que suponen una amenaza para la\\nseguridad, la vida o los derechos fundamentales. En
este nivel se encuentran, por ejemplo, los\\nsistemas con alguna de las siguientes
funciones:\\n• Manipulación subliminal del comportamiento de una persona de manera
que\\npueda causarle daños físicos o psicológicos a él o a otros.\\n• Explotación de
vulnerabilidades de grupos sociales para manipular su\\ncomportamiento de forma que
pueda causarles daño a ellos o a otros.\\n• Evaluación o clasificación de personas o grupos
por su comportamiento social que\\npueda perjudicarlos desproporcionadamente en el
ámbito del comportamiento\\nobservado, o perjudicarlos en ámbitos distintos a donde se


observó.\\n• Identificación biométrica en tiempo real en espacios de acceso público
para\\nautoridades policiales, salvo casos tasados y mediando autorización.\\nLa Comisión
Europea ha preparado unas directrices con el fin de aclarar la interpretación de\\nciertos
casos concretos (Guidelines on prohibited artificial intelligence practices established
by\\nRegulation (EU) 20241689 (AI Act)) 1.\\nB) Sistemas de Alto Riesgo: el segundo nivel
se reserva a los sistemas de alto riesgo, pero\\ncuyo uso está permitido, a los que el
Reglamento dedica la mayoría de los requisitos y\\nobligaciones que deben cumplir los
distintos roles que participan en la cadena de valor de la\\npuesta en uso de un sistema IA
(operadores). Se dividen en dos tipos de sistemas:\\nB1) Productos o componentes de
seguridad de alto riesgo contemplados en\\nlegislación de armonización:\\no Sistemas de IA
que sea un componente de seguridad de alguno de los productos\\ncontemplados en la
legislación de armonización de la Unión recogidos en el Anexo\\nI del Reglamento o,\\no
Que el propio sistema de IA como producto, deba someterse a una evaluación de
la\",\"metadata\":{\"sub_index\":1,\"unit_index\":18,\"source\":\"aesia\",\"doc_date\":\"10
diciembre 2025\",\"unit_title\":\"2.3 Niveles de riesgo del Reglamento Europeo de
IA\",\"unit_id\":\"2.3\",\"unit_type\":\"section\",\"file\":\"guia_01_intro_reglamento_ia.pdf\",\"id\":
\"f017301705f02276959c1fcba419dfc2\",\"doc_title\":\"1\"},\"distance\":0.2592840790748596
},{\"id\":\"c7fd5519725ea103444e499c4fd94879\",\"text\":\"Art.13.3f - Transparencia y
comunicación de\\ninformación a los responsables del despliegue\\ncuando proceda, una
descripción de los mecanismos incluidos en el sistema de\\nIA de alto riesgo que permita a
los responsables del despliegue recabar,\\nalmacenar e interpretar correctamente los
archivos de registro de conformidad\\ncon el artículo 12.\\nAI Act\\nAI Act\\n\\n26\\nQué
entendemos\\nEn la línea de facilitar el entendimiento y uso apropiado de los sistemas por
parte de los\\nusuarios, se trata de describir e implantar los mecanismos contenidos dentro
del propio\\nsistema de IA de alto riesgo para permitir que los usuarios del propio sistema
puedan recoger,\\nguardar e interpretar correctamente los logs, siempre que estos sean
considerados\\nrelevantes. Pretende definir el alcance de lo que una IA transparente
debería ser.\\nConcretamente, menciona que los usuarios del sistema deberían poder recog
er, guardar e\\ninterpretar los logs del sistema siempre que estos sean
relevantes.\\nMedidas para llevarlo a cabo\\n• Las indicadas en la guía del artículo 12 del
Reglamento Europeo de la IA
(Registros).\\n\\n27\",\"metadata\":{\"unit_type\":\"subsection\",\"doc_date\":\"10 diciembre
2025\",\"file\":\"08-guia-transparencia.pdf\",\"source\":\"aesia\",\"doc_title\":\"0\",\"unit_id\":\"4.
3.6\",\"id\":\"c7fd5519725ea103444e499c4fd94879\",\"unit_title\":\"4.3.6. Apartado 3f.
Archivos de
registro\",\"unit_index\":52,\"sub_index\":0},\"distance\":0.26753947138786316},{\"id\":\"410d
bd9ea732cc0ebd32f03d06220fb6\",\"text\":\"Como norma general, el Reglamento se aplica
por igual a las organizaciones privadas, a\\nlas administraciones públicas y a las entidades
del sector público. Ahora bien, se establece\\nla obligación adicional para sistema de alto
riesgo, que consiste en el desarrollo de una\\nevaluación de impacto relativa a los derechos
fundamentales.\\nCon el objetivo de garantizar eficazmente la protección de los derechos
fundamentales por\\nmedio de la determinación de los riesgos específicos para los
derechos de las personas y\\ncolectivos que se vean afectados.\\nEIDF o
FRIAs\\n(Evaluación de Impacto relativa a los derechos fundamentales)\\nObligatoria antes
del despliegue de un sistema de alto riesgo*\\nRealizada por responsables de
despliegue.\\nContenido\\n• Descripción procesos de uso del sistema.\\n• Período de tiempo
y frecuencia de uso.\\n• Categoría personas físicas y colectivos afectados\\n• Riesgos de
perjuicio específicos\\n• Descripción medidas de supervisión humana\\n• Medidas en caso


de que el riesgo se materialice (Mecanismos de reclamación)\\nSistema utilizado en casos
similares , responsable de despliegue basarse en EIDF\\nrealizadas previamente o
existentes.\\nParte del contenido ya incluido en EIPD (Evaluación de Impacto de Protección
de Datos),\\nEIDF la complementará.\\nNotificación a AESIA (Pendiente de publicación
modelo cuestionario por la AI Office)\\n*Excepción: Infraestructuras
Críticas\\n\\n14\",\"metadata\":{\"unit_id\":\"2.4.3\",\"doc_date\":\"10 diciembre
2025\",\"unit_index\":21,\"unit_title\":\"2.4.3 Particulares de los operadores del sector
público\",\"file\":\"guia_01_intro_reglamento_ia.pdf\",\"doc_title\":\"1\",\"id\":\"410dbd9ea732c
c0ebd32f03d06220fb6\",\"source\":\"aesia\",\"sub_index\":0,\"unit_type\":\"subsection\"},\"dist
ance\":0.2677662670612335}]",
"metadata":
"{\"mode\":\"soft\",\"k\":5,\"n_results\":5,\"min_distance\":0.2558,\"max_distance\":0.2799}"
},
{
"id": "d3929521-51b2-4652-942f-37890f0cded8",
"type": "SPAN",
"name": "rag.grade (d3929521)",
"startTime": "2026-03-02T16:52:49.034Z",
"endTime": "2026-03-02T16:59:05.902Z",
"depth": 0,
"input": "{\"args\":[\"sistema de IA evalúa riesgo recidiva presos libertad condicional
normativa EU AI Act y legislación española de IA\",[{\"doc\":\"Procedimiento aplicable a
escala nacional a los sistemas de IA que presenten un riesgo\\n1. Los sistemas de IA que
presentan un riesgo se entenderán como «productos que presentan un riesgo» tal como se
definen en el artículo 3, punto 19, del Reglamento (UE) 2019/1020, en la medida en que
presenten riegos que afecten a la salud, la seguridad o los derechos fundamentales de las
personas.\\n2. Cuando la autoridad de vigilancia del mercado de un Estado miembro tenga
motivos suficientes para considerar que un sistema de IA presenta un riesgo mencionado en
el apartado 1 del presente artículo, efectuará una evaluación del sistema de IA de que se
trate para verificar su cumplimiento de todos los requisitos y obligaciones establecidos en el
presente Reglamento. Debe prestarse una especial atención a los sistemas de IA que
presenten un riesgo para los colectivos vulnerables. Cuando se detecten riesgos para los
derechos fundamentales, la autoridad de vigilancia del mercado informará también a las
autoridades u organismos públicos nacionales pertinentes a que se refiere el artículo 77,
apartado 1, y cooperará plenamente con ellos. Los operadores pertinentes cooperarán en lo
necesario con la autoridad de vigilancia del mercado y con las demás autoridades u
organismos públicos nacionales a que se refiere el artículo 77, apartado
1.\",\"metadata\":{\"doc_date\":\"13 junio
2024\",\"id\":\"3308e8cfc3db373d8520ec6798a48cb0\",\"unit_id\":\"79\",\"file\":\"EU_AI_Act_2
024_1689_ES.html\",\"doc_title\":\"L_202401689ES.000101.fmx.xml\",\"source\":\"eu_ai_act\
",\"sub_index\":0,\"unit_title\":\"Artículo
79\",\"unit_type\":\"article\",\"unit_index\":101},\"score\":0.7201481461524963},{\"doc\":\"de
otros derechos en juego, como por ejemplo la no discriminación en el tratamiento
de\\ndatos. De este modo, a la hora de realizar un análisis de riesgos o evaluación de
impacto\\nde un sistema de IA de alto riesgo, será especialmente impor tante para la
organización\\ntener en cuenta los instrumentos que se hayan desarrollado para el
cumplimiento de la\\nprotección de datos. Es más, la mejor práctica será desarrollar
conjuntamente estos análisis\\nde riesgos de impacto en derechos y, para ello, in tegrar,


cooperar o coordinar con los\\nsujetos que en la organización tengan especiales
atribuciones en la materia, como pueda\\nser el delegado de protección de datos.\\nPosible
Vulneración: Anexo II y III del Reglamento\\nSon plenamente válidos los ejemplos indicados
previamente mencionados en el derecho\\nal respeto a la vida privada y familiar.\\n4)
Libertades de expresión y de información, de reunión y de asociación. Artículo 11\\ny 12 de
la Carta.\\n3 Más información en :
https://www.lavozdegalicia.es/noticia/sociedad/2017/12/21/lista-juguetes-espia-crece-tras-an
alisis-\\nadvierte-riesgos-intolerables-dos-robots/0003_201712G21P28991.htm\\nhttps://ww
w.aepd.es/es/node/824\\n4 Más información
en:\\nhttps://www.incibe.es/incibe/informacion-corporativa/con-quien-trabajamos/proyectos-e
uropeos/is4k\",\"metadata\":{\"doc_date\":\"10 diciembre
2025\",\"unit_index\":81,\"sub_index\":7,\"unit_id\":\"8.1.2\",\"doc_title\":\"0\",\"file\":\"05-guia-d
e-gestion-de-riesgos.pdf\",\"unit_type\":\"subsection\",\"id\":\"f8da8a95be217c0ed5b2559d26
6e2ccc\",\"unit_title\":\"8.1.2 Anexo A.II - Elementos relacionados con la Carta de los
Derechos\",\"source\":\"aesia\"},\"score\":0.7441806197166443},{\"doc\":\"9\\nA) Sistemas
prohibidos: los usos de IA que se encuentren en este nivel de la jerarquía están\\nprohibidos
debido al alto riego que entrañan: sistemas IA que suponen una amenaza para
la\\nseguridad, la vida o los derechos fundamentales. En este nivel se encuentran, por
ejemplo, los\\nsistemas con alguna de las siguientes funciones:\\n• Manipulación subliminal
del comportamiento de una persona de manera que\\npueda causarle daños físicos o
psicológicos a él o a otros.\\n• Explotación de vulnerabilidades de grupos sociales para
manipular su\\ncomportamiento de forma que pueda causarles daño a ellos o a otros.\\n•
Evaluación o clasificación de personas o grupos por su comportamiento social que\\npueda
perjudicarlos desproporcionadamente en el ámbito del comportamiento\\nobservado, o
perjudicarlos en ámbitos distintos a donde se observó.\\n• Identificación biométrica en
tiempo real en espacios de acceso público para\\nautoridades policiales, salvo casos
tasados y mediando autorización.\\nLa Comisión Europea ha preparado unas directrices con
el fin de aclarar la interpretación de\\nciertos casos concretos (Guidelines on prohibited
artificial intelligence practices established by\\nRegulation (EU) 20241689 (AI Act)) 1.\\nB)
Sistemas de Alto Riesgo: el segundo nivel se reserva a los sistemas de alto riesgo,
pero\\ncuyo uso está permitido, a los que el Reglamento dedica la mayoría de los requisitos
y\\nobligaciones que deben cumplir los distintos roles que participan en la cadena de valor
de la\\npuesta en uso de un sistema IA (operadores). Se dividen en dos tipos de
sistemas:\\nB1) Productos o componentes de seguridad de alto riesgo contemplados
en\\nlegislación de armonización:\\no Sistemas de IA que sea un componente de seguridad
de alguno de los productos\\ncontemplados en la legislación de armonización de la Unión
recogidos en el Anexo\\nI del Reglamento o,\\no Que el propio sistema de IA como
producto, deba someterse a una evaluación de
la\",\"metadata\":{\"sub_index\":1,\"unit_index\":18,\"source\":\"aesia\",\"doc_date\":\"10
diciembre 2025\",\"unit_title\":\"2.3 Niveles de riesgo del Reglamento Europeo de
IA\",\"unit_id\":\"2.3\",\"unit_type\":\"section\",\"file\":\"guia_01_intro_reglamento_ia.pdf\",\"id\":
\"f017301705f02276959c1fcba419dfc2\",\"doc_title\":\"1\"},\"score\":0.7407159209251404},{\
"doc\":\"Art.13.3f - Transparencia y comunicación de\\ninformación a los responsables del
despliegue\\ncuando proceda, una descripción de los mecanismos incluidos en el sistema
de\\nIA de alto riesgo que permita a los responsables del despliegue recabar,\\nalmacenar e
interpretar correctamente los archivos de registro de conformidad\\ncon el artículo 12.\\nAI
Act\\nAI Act\\n\\n26\\nQué entendemos\\nEn la línea de facilitar el entendimiento y uso
apropiado de los sistemas por parte de los\\nusuarios, se trata de describir e implantar los


mecanismos contenidos dentro del propio\\nsistema de IA de alto riesgo para permitir que
los usuarios del propio sistema puedan recoger,\\nguardar e interpretar correctamente los
logs, siempre que estos sean considerados\\nrelevantes. Pretende definir el alcance de lo
que una IA transparente debería ser.\\nConcretamente, menciona que los usuarios del
sistema deberían poder recog er, guardar e\\ninterpretar los logs del sistema siempre que
estos sean relevantes.\\nMedidas para llevarlo a cabo\\n• Las indicadas en la guía del
artículo 12 del Reglamento Europeo de la IA
(Registros).\\n\\n27\",\"metadata\":{\"unit_type\":\"subsection\",\"doc_date\":\"10 diciembre
2025\",\"file\":\"08-guia-transparencia.pdf\",\"source\":\"aesia\",\"doc_title\":\"0\",\"unit_id\":\"4.
3.6\",\"id\":\"c7fd5519725ea103444e499c4fd94879\",\"unit_title\":\"4.3.6. Apartado 3f.
Archivos de
registro\",\"unit_index\":52,\"sub_index\":0},\"score\":0.7324605286121368},{\"doc\":\"Como
norma general, el Reglamento se aplica por igual a las organizaciones privadas, a\\nlas
administraciones públicas y a las entidades del sector público. Ahora bien, se establece\\nla
obligación adicional para sistema de alto riesgo, que consiste en el desarrollo de
una\\nevaluación de impacto relativa a los derechos fundamentales.\\nCon el objetivo de
garantizar eficazmente la protección de los derechos fundamentales por\\nmedio de la
determinación de los riesgos específicos para los derechos de las personas y\\ncolectivos
que se vean afectados.\\nEIDF o FRIAs\\n(Evaluación de Impacto relativa a los derechos
fundamentales)\\nObligatoria antes del despliegue de un sistema de alto riesgo*\\nRealizada
por responsables de despliegue.\\nContenido\\n• Descripción procesos de uso del
sistema.\\n• Período de tiempo y frecuencia de uso.\\n• Categoría personas físicas y
colectivos afectados\\n• Riesgos de perjuicio específicos\\n• Descripción medidas de
supervisión humana\\n• Medidas en caso de que el riesgo se materialice (Mecanismos de
reclamación)\\nSistema utilizado en casos similares , responsable de despliegue basarse en
EIDF\\nrealizadas previamente o existentes.\\nParte del contenido ya incluido en EIPD
(Evaluación de Impacto de Protección de Datos),\\nEIDF la complementará.\\nNotificación a
AESIA (Pendiente de publicación modelo cuestionario por la AI Office)\\n*Excepción:
Infraestructuras Críticas\\n\\n14\",\"metadata\":{\"unit_id\":\"2.4.3\",\"doc_date\":\"10
diciembre 2025\",\"unit_index\":21,\"unit_title\":\"2.4.3 Particulares de los operadores del
sector
público\",\"file\":\"guia_01_intro_reglamento_ia.pdf\",\"doc_title\":\"1\",\"id\":\"410dbd9ea732c
c0ebd32f03d06220fb6\",\"source\":\"aesia\",\"sub_index\":0,\"unit_type\":\"subsection\"},\"sco
re\":0.7322337329387665}]],\"kwargs\":{}}",
"output": "[]",
"metadata": "{\"n_docs_in\":5,\"n_relevant\":0,\"method\":\"llm\"}"
}
]

[
{
"id": "ed12a05b-ed0c-4f73-9d55-e41889cfd2db",
"type": "SPAN",
"name": "classifier.predict_risk (ed12a05b)",
"startTime": "2026-03-02T16:52:48.724Z",
"endTime": "2026-03-02T16:52:48.749Z",
"depth": 0,


"input": "{\"args\":[\"Un sistema de IA que evalúa el riesgo de recidiva de presos para
recomendar libertad condicional\"],\"kwargs\":{}}",
"output":
"{\"risk_level\":\"alto_riesgo\",\"confidence\":0.85,\"probabilities\":{\"alto\":0.0375,\"limitado\":0.
0375,\"alto_riesgo\":0.85,\"mínimo\":0.0375,\"inaceptable\":0.0375},\"shap_top_features\":[{\"f
eature\":\"num_palabras\",\"contribution\":1.0230586528778076},{\"feature\":\"svd_24\",\"cont
ribution\":0.9355978965759277},{\"feature\":\"svd_30\",\"contribution\":0.6751113533973694}
,{\"feature\":\"svd_32\",\"contribution\":0.5668127536773682},{\"feature\":\"svd_2\",\"contributi
on\":0.5275657773017883}],\"annex3_override\":true,\"annex3_ref\":\"Anexo III cat.
6\",\"ml_prediction\":{\"risk_level\":\"inaceptable\",\"confidence\":0.992236316204071,\"proba
bilities\":{\"inaceptable\":0.9922,\"alto\":0.0073,\"limitado\":0.0002,\"mínimo\":0.0003}},\"shap_
explanation\":\"Factores principales para 'alto_riesgo': num_palabras, svd_24, svd_30.\"}",
"metadata":
"{\"risk_level\":\"alto_riesgo\",\"confidence\":0.85,\"probabilities\":{\"alto\":0.0375,\"limitado\":0.
0375,\"alto_riesgo\":0.85,\"mínimo\":0.0375,\"inaceptable\":0.0375}}"
},
{
"id": "3bf53cb2-5586-4057-8bc1-4e6b979be279",
"type": "SPAN",
"name": "retriever.search (3bf53cb2)",
"startTime": "2026-03-02T16:52:48.750Z",
"endTime": "2026-03-02T16:52:48.932Z",
"depth": 0,
"input": "{\"args\":[\"sistema de gestión de riesgos Artículo 9\"],\"kwargs\":{\"k\":1}}",
"output": "[{\"id\":\"adefc1a372f0bc58a3f2c19b63d7b372\",\"text\":\"Art.9 – Sistema de
gestión de riesgos\\n1. Se establecerá, implantará, documentará y mantendrá un sistema
de\\ngestión de riesgos en relación con los sistemas de IA de alto
riesgo.\",\"metadata\":{\"id\":\"adefc1a372f0bc58a3f2c19b63d7b372\",\"unit_index\":41,\"unit_
type\":\"section\",\"unit_id\":\"3.2\",\"file\":\"05-guia-de-gestion-de-riesgos.pdf\",\"unit_title\":\"3.
2 Contenido del artículo\",\"doc_date\":\"10 diciembre
2025\",\"doc_title\":\"0\",\"sub_index\":0,\"source\":\"aesia\"},\"distance\":0.165641903877258
3}]",
"metadata":
"{\"mode\":\"soft\",\"k\":1,\"n_results\":1,\"min_distance\":0.1656,\"max_distance\":0.1656}"
},
{
"id": "bda831bc-f6b8-4b2a-b91b-961d01d69495",
"type": "SPAN",
"name": "retriever.search (bda831bc)",
"startTime": "2026-03-02T16:52:48.932Z",
"endTime": "2026-03-02T16:52:49.143Z",
"depth": 0,
"input": "{\"args\":[\"datos y gobernanza de datos Artículo 10\"],\"kwargs\":{\"k\":1}}",
"output": "[{\"id\":\"b635ddb8fe0af6d5ff92ad445bd39591\",\"text\":\"Artículo 10.
Tratamiento de datos de naturaleza penal.\\nTítulo III. Derechos de las personas.\\nCapítulo
I. Transparencia e
información.\",\"metadata\":{\"unit_id\":\"10\",\"source\":\"lopd_rgpd\",\"sub_index\":0,\"unit_in
dex\":9,\"unit_type\":\"article\",\"unit_title\":\"Artículo


10\",\"id\":\"b635ddb8fe0af6d5ff92ad445bd39591\",\"file\":\"LOPDGDD_LO_3_2018_BOE.pd
f\",\"doc_title\":\"LOPDGDD_LO_3_2018_BOE.pdf\"},\"distance\":0.2534858286380768}]",
"metadata":
"{\"mode\":\"soft\",\"k\":1,\"n_results\":1,\"min_distance\":0.2535,\"max_distance\":0.2535}"
},
{
"id": "c83283c5-0723-46a5-a855-99e02311771c",
"type": "SPAN",
"name": "retriever.search (c83283c5)",
"startTime": "2026-03-02T16:52:49.143Z",
"endTime": "2026-03-02T16:52:49.276Z",
"depth": 0,
"input": "{\"args\":[\"documentación técnica Artículo 11\"],\"kwargs\":{\"k\":1}}",
"output": "[{\"id\":\"3eb1d9726155138a8d383dcb84d910d5\",\"text\":\"artículo 97 al objeto
de modificar el anexo IV, cuando sea necesario, para\\ngarantizar que, en vista de los
avances técnicos, la documentación técnica\\nproporcione toda la información necesaria
para evaluar si el sistema cumple los\\nrequisitos establecidos en la presente sección.\\nAI
Act\\n\\n11\\nArt.18 – Conservación de la documentación\",\"metadata\":{\"unit_title\":\"3. La
Comisión estará facultada para adoptar actos delegados con arreglo al\",\"doc_date\":\"10
diciembre
2025\",\"id\":\"3eb1d9726155138a8d383dcb84d910d5\",\"file\":\"15-guia-documentacion-tecn
ica.pdf\",\"sub_index\":0,\"source\":\"aesia\",\"unit_type\":\"chapter\",\"unit_id\":\"3\",\"doc_title\
":\"0\",\"unit_index\":29},\"distance\":0.2466273158788681}]",
"metadata":
"{\"mode\":\"soft\",\"k\":1,\"n_results\":1,\"min_distance\":0.2466,\"max_distance\":0.2466}"
},
{
"id": "67dcd19f-768a-43db-bf89-c9d864aa5c53",
"type": "SPAN",
"name": "retriever.search (67dcd19f)",
"startTime": "2026-03-02T16:52:49.276Z",
"endTime": "2026-03-02T16:52:49.416Z",
"depth": 0,
"input": "{\"args\":[\"transparencia información usuarios Artículo 13\"],\"kwargs\":{\"k\":1}}",
"output": "[{\"id\":\"23846950d86cb3a8f0ba5b43fe88ce7f\",\"text\":\"Art.13 – Transparencia
y comunicación de información a\\nlos responsables del
despliegue\",\"metadata\":{\"id\":\"23846950d86cb3a8f0ba5b43fe88ce7f\",\"unit_index\":35,\"
unit_type\":\"section\",\"unit_title\":\"3.2. Contenido de los artículos en el Reglamento de
IA\",\"sub_index\":0,\"doc_date\":\"10 diciembre
2025\",\"file\":\"08-guia-transparencia.pdf\",\"unit_id\":\"3.2\",\"source\":\"aesia\",\"doc_title\":\"
0\"},\"distance\":0.2604348063468933}]",
"metadata":
"{\"mode\":\"soft\",\"k\":1,\"n_results\":1,\"min_distance\":0.2604,\"max_distance\":0.2604}"
},
{
"id": "57368bfa-ad6b-4b2a-8dd7-9ef64e87ea98",
"type": "SPAN",
"name": "retriever.search (57368bfa)",


"startTime": "2026-03-02T16:52:49.416Z",
"endTime": "2026-03-02T16:52:49.569Z",
"depth": 0,
"input": "{\"args\":[\"vigilancia y supervisión humana Artículo 14\"],\"kwargs\":{\"k\":1}}",
"output": "[{\"id\":\"6671fefb499211861453865b2a2fd76e\",\"text\":\"Este capítulo del
documento recoge el detalle de las medidas necesarias para cubrir los\\nrequisitos de
Vigilancia humana expuestos en el artículo 14 del
Reglamento.\",\"metadata\":{\"id\":\"6671fefb499211861453865b2a2fd76e\",\"file\":\"06-guia-v
igilancia-humana.pdf\",\"unit_type\":\"section\",\"unit_title\":\"4.2 Medidas aplicables para
conseguir la Vigilancia Humana\",\"doc_title\":\"Empresas
desarrollando\",\"unit_index\":44,\"unit_id\":\"4.2\",\"source\":\"aesia\",\"doc_date\":\"10
diciembre 2025\",\"sub_index\":0},\"distance\":0.23091937601566315}]",
"metadata":
"{\"mode\":\"soft\",\"k\":1,\"n_results\":1,\"min_distance\":0.2309,\"max_distance\":0.2309}"
},
{
"id": "dc47d4ad-6911-4a47-a514-0b7d7adcefbe",
"type": "SPAN",
"name": "retriever.search (dc47d4ad)",
"startTime": "2026-03-02T16:52:49.570Z",
"endTime": "2026-03-02T16:52:49.706Z",
"depth": 0,
"input": "{\"args\":[\"precisión robustez y ciberseguridad Artículo 15\"],\"kwargs\":{\"k\":1}}",
"output": "[{\"id\":\"a2b1b4aa97262299719ca1d4f9bc7b0b\",\"text\":\"Aclarar, que dentro
del artículo 15 en el que se trata de precisión, solidez y ciberseguridad, se\\nhabla
específicamente de precisión exclusivamente en los puntos uno, dos y tres.\\nArt.15 –
Precisión, solidez y
ciberseguridad\",\"metadata\":{\"file\":\"09-guia-de-precision.pdf\",\"unit_title\":\"3.2 Contenido
de los artículos en el Reglamento de
IA\",\"source\":\"aesia\",\"unit_type\":\"section\",\"unit_id\":\"3.2\",\"sub_index\":0,\"unit_index\"
:42,\"doc_date\":\"10 diciembre
2025\",\"doc_title\":\"0\",\"id\":\"a2b1b4aa97262299719ca1d4f9bc7b0b\"},\"distance\":0.18847
19878435135}]",
"metadata":
"{\"mode\":\"soft\",\"k\":1,\"n_results\":1,\"min_distance\":0.1885,\"max_distance\":0.1885}"
},
{
"id": "133b043d-c0e6-4b18-83af-b06c8b9ac4a4",
"type": "SPAN",
"name": "report.generate (133b043d)",
"startTime": "2026-03-02T16:52:49.707Z",
"endTime": "2026-03-02T16:52:52.862Z",
"depth": 0,
"input": "{\"args\":[\"Un sistema de IA que evalúa el riesgo de recidiva de presos para
recomendar libertad condicional\",\"alto_riesgo\",[\"aesia — 3.2 Contenido del artículo\\nArt.9

- Sistema de gestión de riesgos\\n1. Se establecerá, implantará, documentará y mantendrá
un sistema de\\ngestión de riesgos en relación con los sistemas de IA de alto
riesgo.\",\"lopd_rgpd — Artículo 10\\nArtículo 10. Tratamiento de datos de naturaleza


penal.\\nTítulo III. Derechos de las personas.\\nCapítulo I. Transparencia e
información.\",\"aesia — 3. La Comisión estará facultada para adoptar actos delegados con
arreglo al\\nartículo 97 al objeto de modificar el anexo IV, cuando sea necesario,
para\\ngarantizar que, en vista de los avances técnicos, la documentación
técnica\\nproporcione toda la información necesaria para evaluar si el sistema cumple
los\\nrequisitos establecidos en la presente sección.\\nAI Act\\n\\n11\\nArt.18 –
Conservación de la documentación\",\"aesia — 3.2. Contenido de los artículos en el
Reglamento de IA\\nArt.13 – Transparencia y comunicación de información a\\nlos
responsables del despliegue\",\"aesia — 4.2 Medidas aplicables para conseguir la Vigilancia
Humana\\nEste capítulo del documento recoge el detalle de las medidas necesarias para
cubrir los\\nrequisitos de Vigilancia humana expuestos en el artículo 14 del
Reglamento.\",\"aesia — 3.2 Contenido de los artículos en el Reglamento de IA\\nAclarar,
que dentro del artículo 15 en el que se trata de precisión, solidez y ciberseguridad,
se\\nhabla específicamente de precisión exclusivamente en los puntos uno, dos y
tres.\\nArt.15 – Precisión, solidez y ciberseguridad\"]],\"kwargs\":{}}",
"output": "# Informe de Cumplimiento del EU AI Act y Normativa Española de IA\n\n## 1.
Resumen Ejecutivo\nEl sistema descrito es un sistema de IA que evalúa el riesgo de
recidiva de presos para recomendar libertad condicional. Dada la naturaleza crítica de sus
decisiones, este sistema ha sido clasificado como de alto riesgo. \n\n## 2. Clasificación de
Riesgo\nEl sistema ha sido clasificado como de alto riesgo debido a la naturaleza de sus
decisiones, las cuales pueden tener un impacto significativo en la vida de las personas. Este
nivel de riesgo se justifica con base en el Art. 9 del Reglamento de IA, que establece la
necesidad de un sistema de gestión de riesgos para sistemas de IA de alto riesgo.\n\n## 3.
Obligaciones Aplicables\nSegún el nivel de riesgo asignado, el sistema debe cumplir con las
siguientes obligaciones:\n\n### Sistema de Gestión de Riesgos\n\"Se establecerá,
implantará, documentará y mantendrá un sistema de gestión de riesgos en relación con los
sistemas de IA de alto riesgo.\" (Art. 9 del Reglamento de IA)\n\n### Conservación de la
Documentación\n\"Art.18 – Conservación de la documentación\" (Reglamento de IA)\n\n###
Transparencia y Comunicación de Información\n\"Art.13 – Transparencia y comunicación de
información a los responsables del despliegue\" (Reglamento de IA)\n\n### Vigilancia
Humana\n\"Este capítulo del documento recoge el detalle de las medidas necesarias para
cubrir los requisitos de Vigilancia humana expuestos en el artículo 14 del Reglamento.\"
(Reglamento de IA)\n\n### Precisión, Solidez y Ciberseguridad\n\"Aclarar, que dentro del
artículo 15 en el que se trata de precisión, solidez y ciberseguridad, se habla
específicamente de precisión exclusivamente en los puntos uno, dos y tres.\" (Reglamento
de IA)\n\n## 4. Citas Legales\n- Art. 9 – Sistema de gestión de riesgos (Reglamento de
IA)\n- Art. 10 – Tratamiento de datos de naturaleza penal (LOPD/RGPD)\n- Art. 13 –
Transparencia y comunicación de información a los responsables del despliegue
(Reglamento de IA)\n- Art. 14 – Medidas aplicables para conseguir la Vigilancia Humana
(Reglamento de IA)\n- Art. 15 – Precisión, solidez y ciberseguridad (Reglamento de IA)\n-
Art. 18 – Conservación de la documentación (Reglamento de IA)\n\n## 5.
Recomendaciones\n- **Implementar un sistema de gestión de riesgos** conforme al Art. 9
del Reglamento de IA.\n- **Documentar adecuadamente** el sistema de gestión de riesgos
y mantener la documentación actualizada.\n- **Asegurar la transparencia y comunicación**
de información a los responsables del despliegue, según el Art. 13 del Reglamento de IA.\n-
**Establecer medidas de vigilancia humana** conforme al Art. 14 del Reglamento de IA.\n-
**Garantizar la precisión, solidez y ciberseguridad** del sistema, específicamente en los
puntos uno, dos y tres del Art. 15 del Reglamento de IA.\n- **Conservar la documentación**


según lo establecido en el Art. 18 del Reglamento de IA.\n\nNo se dispone de información
suficiente en el corpus consultado para abordar otros aspectos como la precisión en el
contexto del Art. 15 del Reglamento de IA.\n\n---\n*Informe preliminar generado por IA.
Consulte profesional jurídico.*",
"metadata":
"{\"risk_level\":\"alto_riesgo\",\"n_articles\":6,\"grounded\":true,\"model\":\"eu.amazon.nova-lit
e-v1:0\",\"report_length\":3113}"
}
]

###### Análisis de Code Claude

**1. Bug doble llamada — causa raíz confirmada**
    1. classifier.predict_risk (dc6dc9a3) → startTime: 16:52:48.713Z (depth:0)
    2. rag.retrieve (c9804b8c) → startTime: 16:52:48.717Z (depth:0) ← 4ms después
    3. classifier.predict_risk (ed12a05b) → startTime: 16:52:48.724Z (depth:0) ← 11ms después

Bedrock disparó **3 tool calls en paralelo** : classifier + rag + classifier (otra vez). No es un retry — es el
orchestrator eligiendo el mismo tool dos veces en la misma respuesta. El bug es en cómo Bedrock
construye su lista de herramientas a invocar, no en el tool en sí.

**2. RAG grade → output vacío**
    4. "output": "[]",
    5. "metadata": {"n_docs_in": 5, "n_relevant": 0, "method": "llm"}

Los 5 docs recuperados (Art. 79, guías AESIA sobre derechos fundamentales, niveles de riesgo,
transparencia, EIDF) **no respondían a la query específica**. Qwen los rechazó correctamente. El
problema es la recuperación, no el grader — el retriever devolvió docs genéricos de contexto, no Art. 5
(prohibiciones) ni Annex III cat. 6.

**3. El pipeline tardó 6 minutos por una búsqueda que devolvió cero resultados**
    6. rag.grade: 16:52:49.034Z → 16:59:05.902Z = 6m16s para llegar a []
    7. report.generate: 16:52:49.707Z → 16:52:52.862Z = 3.2s ← ya había terminado

El report terminó en 3 segundos. El sistema esperó 6 minutos más (rag.grade ejecutando 5 llamadas
a Ollama) para después descartar todo. **El RAG bloqueó la respuesta 6 minutos aportando cero valor.**

**4. Art. 10 LOPD — bug reproducible**
Idéntico al Q3: "datos y gobernanza de datos Artículo 10" → recupera LOPD Art. 10 (datos
penales) con distancia 0.2535. El chunk de EU AI Act Art. 10 no se está encontrando. Es un problema
de indexación o chunking, no de semántica.

**Cuadro completo de los 4 queries:**


```
Problema Q1 Q2 Q3 Q4
```
```
Pipeline
end-to-end
```
```
✓ ✓ ✓ ✓
```
```
Latencia
aceptable
```
```
✗ 4min ✓ ✓ ~5s ✗ 6min
```
```
Bug doble
clasificador
```
```
— — ✓ log ✓ Langfuse
```
```
RAG grade
agresivo /
vacío
```
```
4 → 1 doc — — 5 → 0 docs
```
```
Art.10 LOPD en
vez de EU
AI Act
```
```
— — ✓ ✓
```
```
Art.11 chunk
incorrecto
```
```
— — ✓ ✓
```
```
Ollama bloquea
por 0
utilidad
```
```
— — — ✓ 6min
```
**Tres bugs con fix concreto posible antes de la presentación:**

1. **Bug doble clasificador** — hay que revisar cómo el orchestrator registra las tools para que
    Bedrock no llame al mismo tool dos veces en paralelo
2. **Art. 10 EU AI Act no se recupera** — hay un chunk de LOPD Art. 10 que gana semanticamente
    al de EU AI Act; posible fix con filtro por source o re-indexación
3. **RAG bloquea cuando el resultado es vacío** — si n_relevant=0 tras grade, se puede hacer un
    early exit y no esperar a que todas las llamadas Ollama terminen; o aplicar un timeout al
    grader
**8.**


##### NormaBot — Bugs E2E (2026-03-02, imagen develop)

**Test realizado:** 4 queries contra la imagen desplegada en EC2. Observabilidad vía Langfuse + docker
logs.

**BUG-01 — Doble llamada al clasificador**

**Severidad:** Media | **Afecta:** Queries que combinan clasificador + otras tools
El orquestador (Bedrock ReAct) dispara el clasificador dos veces en paralelo cuando la query activa
múltiples tools simultáneamente. Confirmado en Q4 vía Langfuse: dos spans
classifier.predict_risk con el mismo input, separados por 11ms.
dc6dc9a3 → startTime: 16:52:48.713Z
ed12a05b → startTime: 16:52:48.724Z ← duplicado

El PR #95 no resolvió el caso raíz. El bug está en cómo el orchestrator registra/invoca las tools, no en
el tool en sí.

**BUG-02 — Latencia crítica en RAG (Ollama grader en CPU)**

**Severidad:** Alta | **Afecta:** Cualquier query que active el RAG tool
El step rag.grade llama a Ollama Qwen2.5:3b de forma **secuencial** , una llamada por documento, en
CPU. Con k=5 documentos el tiempo varía entre 4 y 6 minutos.
Q1: retrieve 16s + grade 3m50s + generate 2s = ~4min total
Q4: retrieve 0.3s + grade 6m16s (output=[]) = 6min bloqueado por nada

En Q4 el grader tardó 6 minutos para devolver 0 documentos útiles. El report (la otra tool activa en
paralelo) ya había terminado en 3 segundos.
**Fix posible:** early exit si n_relevant=0 tras las primeras N llamadas, o timeout configurable en el
grader.

**BUG-03 — Retrieval de Art. 10 EU AI Act recupera LOPD en su lugar**

**Severidad:** Media | **Afecta:** Informes de cumplimiento (report tool)
La query interna "datos y gobernanza de datos Artículo 10" devuelve consistentemente el Art.
10 de la LOPD (tratamiento de datos penales) en lugar del Art. 10 del EU AI Act (gobernanza de
datos). Reproducido en Q3 y Q4.
Source recuperado: lopd_rgpd — LOPDGDD_LO_3_2018_BOE.pdf, distance: 0.2535
Source esperado: eu_ai_act — EU_AI_Act_2024_1689_ES.html, Art. 10

Los informes de cumplimiento generados **omiten Art. 10** (obligación crítica para sistemas de alto
riesgo). Posible causa: el chunk del EU AI Act Art. 10 no está bien indexado o tiene menor
representación semántica que el de LOPD.


**BUG-04 — Retrieval de Art. 11 devuelve chunk incorrecto**

**Severidad:** Media | **Afecta:** Informes de cumplimiento
La query "documentación técnica Artículo 11" devuelve un chunk sobre Art. 18 + Annex IV en
lugar del Art. 11 (documentación técnica). Reproducido en Q3 y Q4.
Source recuperado: aesia — 15-guia-documentacion-tecnica.pdf, chunk sobre Art.18
Distance: 0.2466

Los informes omiten Art. 11. El chunk recuperado menciona "11" en el texto pero apunta a Art. 18 en
metadata.

**BUG-05 — Grader demasiado restrictivo (recall bajo)**

**Severidad:** Media | **Afecta:** Calidad de respuestas RAG
El grader Qwen2.5:3b filtra documentos relevantes que deberían pasar:

```
● Q1: 5 docs in → 1 out. Rechazó Art. 26 (obligaciones del responsable del despliegue), que es
directamente relevante a la query.
● Q4: 5 docs in → 0 out. Devolvió lista vacía y el RAG tool no aportó nada al informe final.
```
Consecuencia: las respuestas RAG son **incompletas** por exceso de filtrado, no por falta de
documentos en el corpus.

**Observación — Clasificación "inaceptable" vs override "alto_riesgo"**

**No es un bug, pero merece revisión antes de la presentación.**
En Q4 (scoring de recidiva para libertad condicional) el modelo ML predijo inaceptable (99.22%) y el
override lo llevó a alto_riesgo [Anexo III cat. 6]. El Art. 5.1 del EU AI Act podría justificar la
clasificación original del modelo. Conviene revisar si el override es correcto para este caso específico.

**Resumen de prioridad:**

```
Bug Fix antes del 12 Dificultad
BUG-02 Latencia Ollama Sí — impacto en demo Media
BUG-03 Art. 10 LOPD Sí — error factual en informe Baja
BUG-04 Art. 11 chunk incorrecto Sí — error factual en informe Baja
BUG-01 Doble clasificador Sí — ya tenía PR Media
BUG-05 Grader recall bajo Nice to have Alta
```

# NormaBot

## Análisis Consolidado del Sistema

_RAGAS · Logs E2E · Trazas Langfuse_

7 de marzo de 2026

## 1. Estado Global del Sistema

La siguiente tabla resume el estado actual de cada aspecto evaluado del sistema NormaBot,
agregando datos de las tres fuentes de observabilidad disponibles.

```
Aspecto Estado
Pipeline E2E funcional ✓
Clasificación correcta ✓ (Annex III override)
Disclaimer en todas las respuestas ✓
RAG recupera info relevante ✓ (context_precision = 1.0)
Respuestas fundamentadas en contexto ✗ (faithfulness = 0.32)
Latencia aceptable para producción ✗ (~60s/query en CPU)
ML classifier standalone fiable ✗ (confianza baja, override
necesario)
Evaluación RAGAS completa ✗ (answer_relevancy NaN por
Nova Lite)
```
**Conclusión ejecutiva:** El pipeline es funcionalmente correcto — produce clasificaciones y
respuestas válidas. Sin embargo, el sistema tiene un problema estructural en la capa de grounding
RAG que hace que las respuestas no estén fundamentadas en el corpus legal recuperado, lo cual
es el defecto más crítico para un sistema de cumplimiento normativo.


###### 2. Evaluación RAGAS

**2.1 Resultados**

```
Métrica Valor Umbral Estado
context_precision 1.0000 0.70 ✓ EXCELENTE
context_recall 0.6071 0.70 ✗ POR DEBAJO
faithfulness 0.3198 0.80 ✗ CRÍTICO
answer_relevancy NaN 0.85 ✗ ROTO
```
**2.2 Diagnóstico por métrica**

**context_precision = 1.0 — Excelente**

El retriever es preciso: cuando recupera documentos, son siempre relevantes. Esto confirma que el
embedding model y el índice vectorial funcionan correctamente. Los fragmentos que llegan al
grader son pertinentes para la query.

**context_recall = 0.61 — Por debajo del umbral**

El retriever no cubre todo el material relevante. **k=5 chunks es insuficiente para queries que
requieren síntesis de múltiples artículos** (ej. "obligaciones de un sistema de alto riesgo"
involucra Arts. 9, 10, 11, 12, 13, 14, 15). El recall se ve además agravado por el filtrado agresivo
del grader (ver §4).

**faithfulness = 0.32 — Crítico**

**El problema más grave del sistema.** Las respuestas del orquestador no están fundamentadas en
los documentos recuperados. Las trazas Langfuse revelan la causa exacta: el grader de Ollama
filtra el 100% de los documentos recuperados en el 42% de las queries, dejando al orquestador sin
contexto y forzándolo a responder desde el knowledge previo de Nova Lite.

**answer_relevancy = NaN — Evaluador roto**

Problema de compatibilidad entre Nova Lite y el framework RAGAS. Nova Lite devuelve el JSON
schema en lugar de rellenarlo, o responde {"noncommittal": 1} sin el campo "text" requerido.
RAGAS agota todos los reintentos y no puede computar la métrica. Esto es una limitación del
evaluador, no del sistema en producción.

**2.3 Errores en los jobs de evaluación**

Dos categorías de fallos en los 64 jobs (16 preguntas × 4 métricas):

- TimeoutError (jobs 24, 26, 29, 32-36, 41-42, 44-46): Bedrock throttling al ejecutar 64 jobs en
    paralelo. Nova Lite se satura con alta concurrencia.
- OutputParserException (jobs 37, 49, 53, 57, 61, 62): Nova Lite no sigue el formato
    estructurado de RAGAS. Relacionado con el NaN de answer_relevancy.



###### 3. Pipeline End-to-End — Análisis de Logs

**3.1 Resultados por query (demo 7 marzo)**

```
# Query Herramienta Clasificación Correc
to
```
```
Disclai
mer
1 Obligaciones alto
riesgo
```
```
RAG — ✓ ✓
```
```
2 Filtrado de currículums Classifier + Checklist ALTO (cat. 4.a) ✓ ✓
3 Scoring crediticio Classifier + Checklist ALTO (cat. 5.b) ✓ ✓
4 Recidiva presos Classifier + Checklist
+ RAG
```
```
ALTO (cat. 6) ✓ ✓
```
Las 4 queries de demo producen respuestas correctas con disclaimer. El pipeline E2E está
operativo.

**3.2 Hallazgos positivos**

- Annex III override funcionando correctamente en los 3 casos de clasificación — y era
    imprescindible: el ML predijo incorrectamente en 2 de 3 casos (inaceptable con 45% en Q2;
    riesgo_minimo con 40% en Q3). Sin el override, 2 de 3 clasificaciones habrían sido
    erróneas.
- Q4 usó correctamente múltiples herramientas (classifier + RAG), visible por las 2 llamadas
    consecutivas a Bedrock al final del log.
- Ollama carga en ~9.6s (cold start), luego warm para el resto de la sesión.
- Bug de versión anterior (ToolMessage missing error) ya corregido en el release c2e53bd4.

**3.3 Problemas identificados**

- **Latencia crítica:** ~64s/query con clasificador, ~32s adicionales para el RAG (embedding +
    grading). La causa principal es la inferencia de Qwen 2.5 3B en CPU en EC2.
- **Confianza ML muy baja en casos borderline:** 44-54% en 4 de los 14 casos clasificados.
    El clasificador ML solo no es fiable — el override determinista por Anexo III es el
    mecanismo de precisión real.
- **Q1 (RAG puro):** la respuesta es correcta pero no cita artículos exactos del EU AI Act, solo
    parafrasea obligaciones. Posible gap de cobertura del corpus o umbral de grading
    demasiado estricto.

###### 4. Trazas Langfuse — Análisis de Observabilidad

**4.1 Cobertura de las trazas**


174 registros totales: 43 trazas LangGraph principales, 43 llamadas rag.retrieve, 43 llamadas
rag.grade, 14 llamadas tool.classify_risk, 1 ragas-eval, 30 tool.search_legal_docs. Las trazas
cubren múltiples runs de evaluación (releases 1c4f1eef y c2e53bd4) y 4 sesiones de demo manual.

**4.2 Causa raíz confirmada: el grader Ollama**

El hallazgo más importante de las trazas. El grader de Ollama realiza 43 llamadas con k=5
documentos de entrada cada una. La tasa de retención media es del 18.4% (0.9 documentos de 5).
En el 42% de los casos (18 de 43 llamadas) retiene 0 documentos.

```
Query Docs
ret.
```
```
Reten
ción
```
```
Diagnóstico
```
```
¿Supervisión humana? 4/5 80% Bueno
¿Obligados a informar? 3/5 60% Aceptable
Prácticas prohibidas 2/5 40% Marginal
Gobernanza datos / LOPD 1/5 20% Crítico
Gestión riesgos / multas / Anexo III /
currículums / scoring / recidiva
```
```
0/5 0% Catastrófico
```
**Patrón clave:** a mayor complejidad semántica de la query, más agresivo filtra el grader. Las
queries que requieren síntesis multi-artículo (precisamente las más importantes para un sistema de
cumplimiento) son las que terminan con contexto vacío. Los chunks son individualmente relevantes
(context_precision=1.0), pero el grader no reconoce como relevante ningún chunk que no responda
la pregunta completa por sí solo.

**4.3 Análisis del clasificador**

```
Caso Resultado ML Confian
za
```
```
Override
Anexo III
```
```
Fiable
```
```
Currículums ALTO_RIESGO 85% Sí (cat. 4.a) ✓
Scoring crediticio ALTO_RIESGO 85% Sí (cat. 5.b) ✓
Recidiva presos ALTO_RIESGO 85% Sí (cat. 6) ✓
Chatbot sin aviso RIESGO_LIMITAD
O
```
```
85% No ✓
```
```
Recog. facial INACEPTABLE 49% No ⚠
Alto riesgo (Q) ALTO_RIESGO 54% No ⚠
Riesgo mínimo (Q) RIESGO_MINIMO 44% No ⚠
```
El clasificador ML es fiable (85% confianza) cuando el Annex III override aplica. En casos
borderline sin override, la confianza cae a 44-54% con resultados inconsistentes entre runs
idénticos. El diseño de "ML como señal + override determinista" es la arquitectura correcta y debe
documentarse así.


**4.4 Errores de versión**

**5 trazas con ValueError de ToolMessage** corresponden en su totalidad al release 1c4f1eef
(versión obsoleta). El release c2e53bd4 no presenta este error. Bug resuelto, sin acción pendiente.


###### 5. Plan de Acción Priorizado

```
Pri
or.
```
```
Problema Causa raíz Acción recomendada
```
```
P0 faithfulness =
0.32
```
```
Grader Ollama elimina el 100% de
docs en 42% de queries →
orquestador responde sin contexto
RAG
```
```
Bajar umbral de relevancia del
grader o añadir fallback: si
n_relevant=0, pasar top-k sin
grading
P1 context_recall =
0.61
```
```
k=5 insuficiente para queries
multi-artículo; grader agrava el
gap filtrando chunks válidos
```
```
Aumentar k a 8-10 para
queries complejas; búsqueda
híbrida (dense + sparse)
P2 answer_relevanc
y = NaN
```
```
Nova Lite incompatible con
formato estructurado de RAGAS;
devuelve JSON schema en lugar
de valores
```
```
Configurar LLM alternativo
solo para evaluación RAGAS
(ej. Claude Haiku)
```
```
P3 Latencia
~60s/query
```
```
Inferencia Qwen 2.5 3B en CPU
(EC2); RAG grading añade ~32s
adicionales
```
```
GPU para Ollama o sustituir
grader LLM por re-ranker
ligero (bge-reranker-v2)
P4 ML classifier
confianza baja
```
```
Modelo clasifica solo en 44-54%
en casos borderline; Annex III
override es el mecanismo real de
precisión
```
```
Documentar como limitación
de diseño; el override
determinista es la arquitectura
correcta
```
**5.1 Detalle P0 — Fix del grader (acción inmediata)**

La solución más directa es añadir un fallback en el pipeline RAG: si rag.grade devuelve
n_relevant=0, pasar igualmente los top-k documentos del retriever sin filtrar. Esto garantiza que el
orquestador siempre tiene contexto y elimina la causa raíz del faithfulness=0.32. El coste es
mínimo en latencia porque el grading ya se ejecutó.

Alternativa más robusta: bajar el umbral de relevancia del grader (instrucción del prompt) para que
sea más permisivo — preferible pasar un chunk marginalmente relevante que pasar contexto vacío.

**5.2 Detalle P1 — Mejora de recall**

Aumentar k de 5 a 8-10 para queries clasificadas como complejas (múltiples herramientas, queries
de tipo "obligaciones" o "requisitos"). La búsqueda híbrida (dense embedding + BM25 sparse)
mejoraría especialmente el recall en queries con terminología legal específica no bien cubierta por
embeddings semánticos.

**5.3 Detalle P2 — Evaluación RAGAS**

Configurar un LLM alternativo solo para el evaluador RAGAS (claude-haiku o gpt-4o-mini). Nova
Lite no es compatible con el formato estructurado requerido. Esta configuración es independiente
del modelo de producción y no afecta al sistema evaluado.


_NormaBot — Análisis generado el 7 de marzo de 2026_


###### Anexo — Queries y Respuestas de la Demo

Transcripción literal de las 4 queries ejecutadas en la demo del 7 de marzo de 2026, con sus
respuestas tal como aparecen en la Chat UI.

**Query 1 — RAG puro**

**Input:**
_¿Qué obligaciones tiene un sistema de IA de alto riesgo según el EU AI Act?_
**Respuesta del sistema:**
Según el EU AI Act, un sistema de IA de alto riesgo está sujeto a varias obligaciones para
garantizar su seguridad y cumplimiento normativo:

- **Evaluación de Riesgos y Mitigación:** Se debe realizar una evaluación de riesgos y definir
    las medidas de mitigación antes de poner en el mercado el sistema de IA.
- **Registro en un Repositorio Público:** El sistema de IA debe ser registrado en un
    repositorio público, que es el registro de la Unión Europea de sistemas de inteligencia
    artificial.
- **Auditoría y Documentación:** La documentación técnica del sistema debe ser auditada y
    mantenida para demostrar su cumplimiento con las normas de seguridad y no
    discriminación.
- **Sistema de Gestión de Riesgos:** Establecer un sistema de gestión de riesgos efectivo que
    esté continuamente monitoreado y actualizado.
- **Seguimiento y Monitoreo Post-comercialización:** Implementar un plan para el
    seguimiento y monitoreo del sistema una vez esté en uso para detectar cualquier incidencia
    o incumplimiento.

```
⚠ Informe preliminar generado por IA. Consulte profesional jurídico.
```
**Query 2 — Classifier + Checklist (currículums)**

**Input:**
_Tengo un sistema que analiza currículums automáticamente para filtrar candidatos en
procesos de selección. ¿En qué nivel de riesgo lo clasificarías?_
**Respuesta del sistema:**
Clasificación: **ALTO RIESGO** — Anexo III cat. 4.a

- Art. 9 — Sistema de gestión de riesgos: Establecer, aplicar, documentar y mantener un
    sistema de gestión de riesgos durante todo el ciclo de vida del sistema de IA.
- Art. 10 — Gobernanza de datos: Los conjuntos de datos de entrenamiento, validación y
    prueba deben cumplir criterios de calidad: representatividad, ausencia de errores,
    completitud.
- Art. 11 — Documentación técnica: Elaborar documentación técnica antes de la
    comercialización o puesta en servicio, manteniéndola actualizada.


- Art. 12 — Registro de actividades: El sistema debe permitir el registro automático de
    eventos (logs) durante su funcionamiento, con trazabilidad adecuada.
- Art. 13 — Transparencia: Diseñar el sistema para que su funcionamiento sea
    suficientemente transparente y permita a los responsables interpretar y usar correctamente
    sus resultados.
- Art. 14 — Supervisión humana: Diseñar el sistema para que pueda ser supervisado
    eficazmente por personas físicas durante su uso, incluyendo la posibilidad de intervenir o
    detenerlo.
- Art. 15 — Precisión, solidez y ciberseguridad: El sistema debe alcanzar niveles adecuados
    de precisión, solidez y ciberseguridad, y funcionar de forma coherente a lo largo de su ciclo
    de vida.
- Art. 43 — Evaluación de conformidad: Someterse a una evaluación de conformidad antes
    de su comercialización o puesta en servicio, según el procedimiento aplicable.

⚠ _Informe preliminar generado por IA. Consulte profesional jurídico._


**Query 3 — Classifier + Checklist (scoring crediticio)**

**Input:**
_Genera un informe de cumplimiento para un sistema de scoring crediticio automático._
**Respuesta del sistema:**
Clasificación: **ALTO RIESGO** — Anexo III cat. 5.b

- Art. 9 — Sistema de gestión de riesgos: Establecer, aplicar, documentar y mantener un
    sistema de gestión de riesgos durante todo el ciclo de vida del sistema de IA.
- Art. 10 — Gobernanza de datos: Los conjuntos de datos de entrenamiento, validación y
    prueba deben cumplir criterios de calidad: representatividad, ausencia de errores,
    completitud.
- Art. 11 — Documentación técnica: Elaborar documentación técnica antes de la
    comercialización o puesta en servicio, manteniéndola actualizada.
- Art. 12 — Registro de actividades: El sistema debe permitir el registro automático de
    eventos (logs) durante su funcionamiento, con trazabilidad adecuada.
- Art. 13 — Transparencia: Diseñar el sistema para que su funcionamiento sea
    suficientemente transparente y permita a los responsables interpretar y usar correctamente
    sus resultados.
- Art. 14 — Supervisión humana: Diseñar el sistema para que pueda ser supervisado
    eficazmente por personas físicas durante su uso, incluyendo la posibilidad de intervenir o
    detenerlo.
- Art. 15 — Precisión, solidez y ciberseguridad: El sistema debe alcanzar niveles adecuados
    de precisión, solidez y ciberseguridad, y funcionar de forma coherente a lo largo de su ciclo
    de vida.
- Art. 43 — Evaluación de conformidad: Someterse a una evaluación de conformidad antes
    de su comercialización o puesta en servicio, según el procedimiento aplicable.

**Recomendación específica:** Implementar auditorías periódicas del sistema para asegurar que se
cumplen todos los requisitos legales y las mejores prácticas de ciberseguridad.

```
⚠ Informe preliminar generado por IA. Consulte profesional jurídico.
```
**Query 4 — Classifier + Checklist + RAG (recidiva presos)**

**Input:**
_Tengo un sistema de IA que evalúa el riesgo de recidiva de presos para recomendar libertad
condicional. Clasifícalo, busca los artículos aplicables y genera un informe de cumplimiento._
**Respuesta del sistema:**
Clasificación: **ALTO RIESGO** — Anexo III cat. 6 (sistemas en ámbitos críticos para la seguridad:
justicia penal)


- Art. 9 — Sistema de gestión de riesgos: Establecer, aplicar, documentar y mantener un
    sistema de gestión de riesgos durante todo el ciclo de vida del sistema de IA.
- Art. 10 — Gobernanza de datos: Los conjuntos de datos de entrenamiento, validación y
    prueba deben cumplir criterios de calidad: representatividad, ausencia de errores,
    completitud.
- Art. 11 — Documentación técnica: Elaborar documentación técnica antes de la
    comercialización o puesta en servicio, manteniéndola actualizada.
- Art. 12 — Registro de actividades: El sistema debe permitir el registro automático de
    eventos (logs) durante su funcionamiento, con trazabilidad adecuada.
- Art. 13 — Transparencia: Diseñar el sistema para que su funcionamiento sea
    suficientemente transparente y permita a los responsables interpretar y usar correctamente
    sus resultados.
- Art. 14 — Supervisión humana: Diseñar el sistema para que pueda ser supervisado
    eficazmente por personas físicas durante su uso, incluyendo la posibilidad de intervenir o
    detenerlo.
- Art. 15 — Precisión, solidez y ciberseguridad: El sistema debe alcanzar niveles adecuados
    de precisión, solidez y ciberseguridad, y funcionar de forma coherente a lo largo de su ciclo
    de vida.
- Art. 43 — Evaluación de conformidad: Someterse a una evaluación de conformidad antes
    de su comercialización o puesta en servicio, según el procedimiento aplicable.

⚠ _Informe preliminar generado por IA. Consulte profesional jurídico. Este es un informe preliminar
basado en IA — es fundamental consultar con un profesional jurídico para asegurar que todas las
obligaciones se cumplan adecuadamente._


