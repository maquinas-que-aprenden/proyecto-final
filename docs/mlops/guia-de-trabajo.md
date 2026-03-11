# Guía de trabajo MLOps + Observabilidad

## Acceso mediante CLI a AWS
* [Descargar AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html#getting-started-install-instructions)
* Ejecutar:
```bash
aws configure set aws_access_key_id TU_ACCESS_KEY
aws configure set aws_secret_access_key TU_SECRET_KEY
aws configure set region eu-west-1
aws configure set output json
```
* Utilizar las credenciales están en `usuario_accessKeys.csv` con cada miembro del proyecto. _**Nota**: las accessKeys son privadas, no se pueden subir a ninguna parte. Si se suben tenemos que generar unas nuevas._
* Esto se almacena automáticamente en `~/.aws/credentials`
* Verificar que funciona:
```bash
aws s3 ls s3://normabot
```

## Almacenamiento en S3

### Datos
Esta sección explica cómo manejar archivos pesados (PDFs, JSONs de datos) para que se guarden en S3 y no saturen GitHub. Vamos a usar [DVC](https://dvc.org/) que funciona muy parecido a git.

**Prerequisitos**: AWS CLI (instalación manual, ver sección anterior) y DVC con soporte S3:
```bash
pipx install 'dvc[s3]'
```

#### Configuración de DVC (hecha ya)
Esto **se hace solo una vez y ya está hecho**.

```bash
# Inicializar DVC
dvc init

# Añadir almacen de S3
dvc remote add -d storage s3://normabot/dvc

# Guardar en git
git add .dvc/config .dvc/.gitignore .dvcignore
git commit -m "Configurar S3 como almacenamiento remoto de DVC"
git push origin tu-rama
```
#### Gestionar corpus con DVC

##### Subir archivos
1. Si se añade, por ejemplo, el BOE en `data/raw`, primero hay que añadir la ruta donde hay ficheros nuevos:
```bash
dvc add data/raw
```
2. Para subirla al bucket de S3 solo hay que hacer `push`:
```bash
dvc push
```
3. Para sincronizar con GitHub:
```bash
git add data/raw.dvc .gitignore
git commit -m "Actualizar PDFs del BOE"
git push origin <tu-rama>
```

##### Descargar archivos
Para trabajar con los archivos que haya subido un compañero es necesario hacer:
```bash
git pull
dvc pull
```

#### Gestionar índice de vectores con DVC
Como con el corpus, para hacer versionado de los embeddings hay que:
1. Añadir la ruta con el índice:
```bash
dvc add data/processed/vectorstore/
```
2. Hacer `push` para subirla a S3:
```bash
dvc push
```
3. Para sincronizar con GitHub:
```bash
git add data/processed/vectorstore.dvc .gitignore
git commit -m "Actualizar VectorDB version X"
git push origin <tu-rama>
```

#### Gestionar binarios de modelos
Los modelos del clasificador (archivos `.joblib`) **no están gestionados con DVC** — se versionan directamente en git bajo `src/classifier/classifier_dataset_fusionado/model/`. Esto es así porque su tamaño es manejable y tenerlos en git facilita el despliegue sin pasos adicionales de `dvc pull`.

## Infraestructura como Código
Usamos IaC para garantizar entornos reproducibles, escalables y que se desplieguen rápido con control de versiones.

### Terraform
* Estamos usando [Terraform](https://developer.hashicorp.com/terraform) para desplegar los servicios de AWS que usamos: VPC, EC2, S3, IAM (usuarios, grupos, roles, políticas), Bedrock.
* El estado de terraform (tfstate) guarda el estado existente de todos los recursos que se han desplegado con él. Sin él habría que importarlos todos manualmente para que los reconozca. Por eso, para que no se pierda, está guardado en nuestro bucket de S3 en el path `state`.

#### Cómo ejecutar
Para desplegar con terraform o hacer modificaciones:
```bash
terraform init # IMPORTANTE: decir 'yes' cuando pregunte si se desea incorporar el tfstate al backend
terraform plan # nos muestra antes de ejecutar qué recursos van a cambiar o eliminarse
terraform apply # aplica los cambios.
```

Para eliminar toda la infraestructura:
```bash
terraform destroy
```
**Nota**: los volúmenes EBS tienen `prevent_destroy = true` y Terraform se negará a eliminarlos. Si se quieren eliminar definitivamente (con la consiguiente pérdida de datos), hay que borrarlos manualmente desde la consola de AWS después.

Para desplegar o destruir hay que tener permisos para crear los recursos en AWS, requiere un key pair de EC2.

### Ansible
* Estamos usando [Ansible](https://docs.ansible.com/) para configurar los tres servidores que tenemos: normabot (GPU), la t3.large de desarrollo (detenida) y mlflow.
* Estos son los ficheros actuales:
```
.
├── inventory.ini               # inventario de servidores, generado automáticamente por terraform (no se sube a github)
├── mlflow_deploy.yaml          # configuración de mlflow
├── mlflow_ebs.yaml             # configuración de ebs de mlflow
├── normabot_ebs.yaml           # monta el EBS por UUID, configura docker-data y containerd en el EBS
├── normabot_data.yaml          # instala DVC, clona el repo (main) y descarga el vectorstore desde S3
├── normabot_gpu.yaml           # instala drivers NVIDIA 535 + nvidia-container-toolkit (g4dn.xlarge / Tesla T4)
├── normabot_gpu_ebs.yaml       # igual que normabot_ebs.yaml pero con auto-detección del dispositivo EBS
├── normabot_gpu_data.yaml      # igual que normabot_data.yaml pero apunta a hosts: normabot_gpu
├── playbook.yaml               # configuración base de todos los servidores (docker, git, aws cli)
└── templates
    ├── docker-compose.yml.j2   # necesario para despliegue de mlflow
    └── nginx.conf.j2           # necesario para securizar acceso a mlflow
```
* El inventario que usa ansible (`inventory.ini`) se genera automáticamente con terraform o se puede usar esta plantilla:
```
[mlflow]
<IP> ansible_user=ubuntu ansible_ssh_private_key_file=~/.ssh/aws.pem

[normabot]
<IP> ansible_user=ubuntu ansible_ssh_private_key_file=~/.ssh/aws.pem

[normabot_gpu]
<IP> ansible_user=ubuntu ansible_ssh_private_key_file=~/.ssh/aws.pem

```

#### Cómo ejecutar
Existe un orden para ejecutarlos.
```bash
# Para configurar ambos servidores desde cero:
ansible-playbook -i inventory.ini playbook.yaml

# Para mlflow (solo la primera vez o si se recrea desde cero la instancia):
ansible-playbook -i inventory.ini mlflow_ebs.yaml
ansible-playbook -i inventory.ini mlflow_deploy.yaml -e "mlflow_password=<password>"

# Para normabot CPU (solo la primera vez o si se recrea desde cero la instancia):
ansible-playbook -i inventory.ini normabot_ebs.yaml
ansible-playbook -i inventory.ini normabot_data.yaml

# Para normabot GPU (g4dn.xlarge — solo la primera vez o si se recrea desde cero):
ansible-playbook -i inventory.ini playbook.yaml          # base: docker, git, aws cli
ansible-playbook -i inventory.ini normabot_gpu.yaml      # nvidia drivers + container toolkit (hace reboot si instala drivers nuevos)
ansible-playbook -i inventory.ini normabot_gpu_ebs.yaml  # monta EBS por UUID, configura docker-data y containerd
ansible-playbook -i inventory.ini normabot_gpu_data.yaml # clona repo (main), instala dvc, hace pull del vectorstore
# Para clonar develop en lugar de main:
ansible-playbook -i inventory.ini normabot_gpu_data.yaml -e "git_branch=develop"
```
En el caso de `mlflow_deploy` es necesario pasar la contraseña para que nginx impida acceder a cualquiera. La contraseña está en nuestro gestor de contraseñas compartido.

## Integración y despliegue continuo (CI/CD)

### Workflows disponibles

| Workflow | Disparador | Qué hace |
|---|---|---|
| `pr_lint.yml` | PR a `main` o `develop` | Lint (ruff) solo sobre los ficheros `.py`/`.ipynb` modificados en la PR |
| `ci-develop.yml` | Push a `develop` | Lint completo + smoke tests (pytest) + build y publicación de imagen `:develop` |
| `cicd-main.yml` | Push a `main` o PR a `main` | Lint completo + smoke tests (pytest) + build imagen `:latest` + despliegue automático en EC2 |
| `eval.yml` | Manual (`workflow_dispatch`) | Evaluación RAGAS sobre la imagen desplegada en EC2 |

El `pr_lint.yml` usa `tj-actions/changed-files` para obtener solo los archivos modificados en la PR y pasarlos a `ruff check`, en vez de escanear el repositorio entero. Esto hace el check más rápido y evita fallos por ficheros que no se han tocado.

### Secretos en GitHub

Para que los workflows funcionen hay que configurar los siguientes secretos en _Settings → Secrets and variables → Actions_ del repositorio:

| Secreto | Dónde se usa | Descripción |
|---|---|---|
| `EC2_HOST` | `cicd-main.yml`, `eval.yml` | IP pública del servidor NormaBot |
| `EC2_USER` | `cicd-main.yml`, `eval.yml` | Usuario SSH (ubuntu) |
| `EC2_SSH_KEY` | `cicd-main.yml`, `eval.yml` | Clave privada SSH (contenido del `.pem`) |
| `GHCR_READ_TOKEN` | `cicd-main.yml` | Token con permiso `read:packages` para hacer login en GHCR desde EC2 |
| `GHCR_READ_USER` | `cicd-main.yml` | Usuario de GitHub asociado al token anterior |

### Probar una imagen de develop
Para probar manualmente una imagen publicada desde la rama `develop`:
```bash
ssh -i ~/.ssh/aws.pem ubuntu@<ip-normabot>
docker pull ghcr.io/maquinas-que-aprenden/proyecto-final:develop
docker run -p 8080:8080 --env-file /home/ubuntu/normabot/.env ghcr.io/maquinas-que-aprenden/proyecto-final:develop
```
La app estará disponible en `http://<ip-normabot>:8080`.

## Observabilidad y trazabilidad

### Langfuse Cloud
Tenemos una cuenta común para [Langfuse Cloud](https://cloud.langfuse.com/) y una API key para mandar trazas que se puede consultar en la web.

Usamos Langfuse SDK v2 (`langfuse>=2.7.3,<3.0.0`) con `@observe` como mecanismo principal de instrumentación:
* **`@observe` (decoradores de función)**: captura llamadas individuales a las funciones del pipeline (retrieve, grade, predict_risk, search y las herramientas search_legal_docs y classify_risk del orquestador) con sus inputs, outputs y metadatos específicos de cada paso.
* **CallbackHandler de LangChain**: instanciado en `src/observability/main.py` e inyectado en el agente ReAct. **Limitación conocida**: `langfuse.callback` v2 requiere `langchain.callbacks.base`, eliminado en langchain 0.3, por lo que la traza raíz del agente no llega a Langfuse. Las trazas individuales de cada herramienta sí funcionan vía `@observe`.

#### Qué se puede ver en Langfuse
Para cada petición al sistema:
* Span `rag.retrieve`: cuántos documentos recuperó ChromaDB y con qué distancias de similitud.
* Span `rag.grade`: cuántos documentos superaron el filtro de relevancia, y si Ollama estuvo disponible o se usó el fallback por score (se distingue con `level=WARNING`).
* Span `classifier.predict_risk`: nivel de riesgo predicho, confianza, y distribución de probabilidades por clase.
* Span `retriever.search`: distancias min/max, número de resultados, fuentes únicas y si el contexto fue truncado.
* Spans `tool.search_legal_docs` y `tool.classify_risk`: inputs y outputs de las herramientas del agente.
* Los spans con `level=ERROR` (ChromaDB caído) o `level=WARNING` (Ollama en fallback) se distinguen visualmente para detectar degradaciones rápidamente.
* **Feedback de usuario (👍/👎): no disponible** — dependía del `trace_id` del CallbackHandler raíz, que no está accesible por la incompatibilidad descrita arriba.

#### Tests
En pytest, Langfuse se desactiva automáticamente mediante `LANGFUSE_ENABLED=false` en `tests/conftest.py`. No es necesario configurar credenciales para ejecutar los tests localmente ni en CI.

Para más información, consultar la documentación oficial: [Langfuse: get started](https://langfuse.com/docs/observability/get-started)

### Evaluación RAGAS

El workflow `eval.yml` ejecuta una evaluación RAGAS sobre NormaBot. Se lanza manualmente desde _Actions → NormaBot RAGAS Eval → Run workflow_.

Lo que hace: se conecta por SSH al servidor EC2, hace `git pull` para tener los últimos ficheros de `eval/`, y ejecuta `docker exec` sobre el contenedor `normabot` ya en marcha. El script `eval/run_ragas.py --ci`:

1. Carga el dataset de evaluación (`eval/dataset.json`, 14 ejemplos).
2. **Phase A — Retriever**: recupera contextos reales del vectorstore para cada pregunta (sin invocar el agente) y calcula ContextPrecision y ContextRecall.
3. **Phase B — E2E**: obtiene respuestas reales del agente reutilizando los contextos de Phase A, y calcula Faithfulness. Usar los mismos contextos garantiza que ambas fases son comparables.
4. Registra los resultados en MLflow (experimento `normabot-ragas-eval`) y anota scores en Langfuse.
5. Si alguna métrica no supera el umbral, sale con código 1 (en local solo avisa, no bloquea).

Los umbrales actuales son:
- `context_precision` ≥ 0.70 (Phase A)
- `context_recall` ≥ 0.70 (Phase A)
- `faithfulness` ≥ 0.80 (Phase B)
- `answer_relevancy` excluida: Nova Lite produce NaN sistemáticamente en esta métrica.

**Limitación importante**: los scores finales son `nanmean` (media ignorando NaN). Nova Lite no sigue los prompts JSON de RAGAS de forma consistente, lo que produce NaN en muchos ejemplos — especialmente en Faithfulness. El número final puede estar calculado sobre una fracción pequeña del dataset. Consultar [`docs/mlops/analisis-ragas.md`](analisis-ragas.md) para el análisis detallado de los runs realizados.

El directorio `eval/` está montado en el contenedor como bind mount (`./eval:/app/eval` en `docker-compose.yml`), por lo que el `git pull` en EC2 basta para que el contenedor vea los ficheros actualizados sin necesitar un redeploy.

Para ver los resultados, consultar el experimento en MLflow o las trazas en Langfuse etiquetadas con el SHA del commit.

### MLflow
Tenemos levantado un servidor para MLflow.

Para usarlo es necesario añadir código que tome del entorno la contraseña de autenticación:
```python
import os
import mlflow

# Autenticación básica con NGINX
try:
    from google.colab import userdata
    password = userdata.get("MLFLOW_PASSWORD")
except ImportError:
    # Entorno local: lee la variable de entorno del sistema
    password = os.getenv("MLFLOW_PASSWORD")

os.environ["MLFLOW_TRACKING_INSECURE_TLS"] = "true"
os.environ["MLFLOW_TRACKING_USERNAME"] = "tracker"
os.environ["MLFLOW_TRACKING_PASSWORD"] = password
mlflow.set_tracking_uri("https://<ip-mlflow>/mlflow/")
```
No tiene por qué ser este concretamente.

La contraseña se puede añadir al entorno de la siguiente forma:
* En Google Colab hay un panel de secretos (icono de llave en el menú lateral). Se puede añadir MLFLOW_PASSWORD con el valor de la contraseña.
* En local:
```bash
echo 'export MLFLOW_PASSWORD="contraseña"' >> ~/.bashrc  # si usas bash
echo 'export MLFLOW_PASSWORD="contraseña"' >> ~/.zshrc   # si usas zsh
source ~/.bashrc  # o source ~/.zshrc para aplicarlo sin reiniciar
```

La UI también está levantada en: https://<ip-mlflow>/mlflow/.

Para más información, consultar la documentación oficial: [Logging to a tracking server](https://mlflow.org/docs/latest/self-hosting/architecture/tracking-server/#logging_to_a_tracking_server)

## Desarrollo local

### Ollama (RAG grading)
NormaBot usa Ollama con el modelo `qwen2.5:3b` para el grading de documentos en el pipeline RAG. Sin Ollama corriendo, el grading cae silenciosamente al fallback por score de similitud (visible en Langfuse como `level=WARNING`).

```bash
# Instalar (macOS)
brew install ollama

# Descargar el modelo
ollama pull qwen2.5:3b

# Arrancar el servidor
brew services start ollama
```

Verificar que funciona:
```bash
ollama list  # debe aparecer qwen2.5:3b
```

### Pipeline de datos
Si se necesita regenerar el vectorstore desde cero (por ejemplo, tras añadir documentos nuevos al corpus):
```bash
# 1. Descargar datos crudos de S3
dvc pull data/raw/

# 2. Convertir documentos a chunks JSONL
python data/ingest.py

# 3. Generar embeddings y cargar en ChromaDB
python data/index.py

# 4. Versionar el nuevo vectorstore
dvc add data/processed/vectorstore/
dvc push
git add data/processed/vectorstore.dvc
git commit -m "Actualizar vectorstore con nuevos documentos"
```

### Tests
```bash
# Instalar dependencias de desarrollo
pip install -r requirements/dev.txt

# Ejecutar todos los tests
pytest tests/ -v

# Con output de logs (útil para ver la carga del modelo)
pytest tests/ -v -s
```

Hay seis suites de smoke tests (133 tests en total):
- `test_classifier.py` — 35 tests: estructura de `predict_risk()`, robustez, explicabilidad SHAP, validación de entrada, coherencia de campos tras el override del Anexo III (`TestAnnex3Override`).
- `test_checklist.py` — 27 tests: obligaciones por nivel de riesgo, recomendaciones SHAP, construcción del checklist de cumplimiento y detección de casos borderline.
- `test_constants.py` — 14 tests: integridad de `src/classifier/_constants.py` — claves y tipos de `RISK_LABELS`, `KEYWORDS_DOMINIO`, `LEAKAGE_COLUMNS` y `STOPWORDS_ES`. Evita regresiones silenciosas al editar las constantes compartidas.
- `test_memory.py` — 5 tests: hook `pre_model_hook` de truncación del historial de conversación para no exceder la ventana de contexto del LLM.
- `test_orchestrator.py` — 38 tests: SYSTEM_PROMPT con requisitos legales (incluida instrucción anti-doble-clasificación), nombres y descripciones de las 4 tools, validación de entrada, comportamiento de `classify_risk`, `search_legal_docs` y `generate_report`, ausencia de doble llamada al clasificador (`TestNoDobleClasificacion`), side-channel de metadatos, contrato de `run()`, y memoria conversacional.
- `test_retrain.py` — 14 tests: limpieza de texto, carga de JSONL, features manuales e integración de `main()` con `monkeypatch` de rutas y stub `_FakeXGB` (sin entrenamiento real).

La rama `fine-tuning` (no mergeada en `main`) incluye adicionalmente `test_finetuning.py` — 45 tests sobre `src/finetuning/functions.py` y `src/finetuning/grader.py`: constantes, carga y split del dataset de grading, construcción de mensajes de entrenamiento, parseo de respuestas del grader QLoRA, disponibilidad del adaptador y manejo de errores de carga del modelo.

Los tests de orchestrator y RAG mockean `langchain_aws` (Bedrock), `langchain_core` y `langchain_ollama` (Ollama) a nivel de módulo para no depender de servicios externos. Langfuse se desactiva automáticamente durante la ejecución de pytest.
