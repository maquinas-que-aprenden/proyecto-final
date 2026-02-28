# MLOps + Observabilidad

## Setup
* Repositorio público en GitHub:
    * GitFlow asegurado con rulesets.
    * Templates para crear issues y PRs.
    * Automatización de avisos de PRs.
* 1 cuenta free-tier por 6 meses en AWS
    * Utilizamos la región eu-west-1 (Irlanda) porque tenemos garantizado que hay más servicios que funcionan en el free-tier que, por ejemplo, en eu-south-2 (España). Está dentro de la UE por lo que cumple con la legislación que nos interesa y la latencia es baja.
* [Langfuse](https://langfuse.com/) Cloud en la región de datos EU.
    * Es más conveniente y rápido que hacer un despliegue en AWS, permitiéndonos empezar a trabajar con ello de forma inmediata. El free tier cumple con nuestras necesidades y el que sea gestionado nos evita preocuparnos por mantener una base de datos.

## Gestión de accesos a AWS
* Se crea el usuario y se le asigna un rol con los permisos estrictamente necesarios para hacer su trabajo (_Principio del Mínimo Privilegio_).
* Se comparte un fichero `usuario_accessKeys.csv` con cada miembro del proyecto que contiene sus credenciales.
* Cada compañero descarga AWS CLI y lo configura localmente como se explica en la [guía de trabajo](guia-de-trabajo.md).

### Permisos de desarrolladores
* Se crea un grupo `NormaBot-Devs`.
* Se le asigna al grupo una política con acceso restringido al bucket de S3 que vamos a utilizar, y permiso de `bedrock:InvokeModel` restringido al inference profile EU `eu.amazon.nova-lite-v1:0`.
* Se crea un usuario por compañero y se añade al grupo.

### Roles para las instancias EC2
* Las instancias EC2 acceden a AWS a través de IAM roles asignados como instance profiles, sin necesitar credenciales en el `.env` (_Principio del Mínimo Privilegio_ aplicado también a los servidores).
* `NormaBot_EC2_S3_Role` — asignado a la instancia MLflow. Permite solo S3 (`GetObject`, `ListBucket`, `PutObject`) sobre el bucket `normabot`.
* `NormaBot_Agent_EC2_Role` — asignado a la instancia NormaBot. Añade permiso de `bedrock:InvokeModel` y `bedrock:InvokeModelWithResponseStream` restringido al inference profile EU `eu.amazon.nova-lite-v1:0`, que enruta transparentemente a regiones EU sin exponer credenciales de larga duración.

## Datos y versiones
* En vez de utilizar GitHub, Google Drive o HF Datasets para almacenar el corpus como se propone en los specs originales, para tener un punto que sea la fuente única de verdad y una mayor trazabilidad, vamos a usar el bucket de S3 `normabot` en `eu-west-1` con [DVC](https://dvc.org/).

## Infraestructura en AWS

### IaC
* Se persiste la infraestructura en Terraform para poder desplegarla y destruirla con rapidez.
* La configuración del servidor en la instancia EC2 se hace a través de playbooks de Ansible.
* Tanto Terraform como Ansible se ejecutan en local, no hay planes de automatizar el despliegue de momento.

### Máquinas virtuales (EC2)
Inicialmente se plantea:
* Utilizar una sola instancia de EC2 para desplegar, con un Security Group e IP pública.
* Utilizar Docker Compose para mantener varios servicios aislados en la misma instancia.
* Para proteger MLflow y no exponer directamente su puerto, usamos un reverse proxy de NGINX y autenticación básica (usuario y contraseña).
A fecha de 20/02 se decide la separación en dos instancias: una para MLflow y otra para Normabot, cada una con su correspondiente security group.
Actualmente:
    * MLflow necesita un t3.small, porque la memoria RAM de t3.micro del free-tier no es suficiente para su ejecución.
    * NormaBot está desplegado en una t3.large (8GB RAM). Se necesita t3.large porque Ollama/Qwen 2.5 3B requiere ~1.9GB de RAM y el t3.medium (4GB) no dejaba margen suficiente tras el arranque de la app.
    * Ambas instancias tienen IMDSv2 forzado (`http_tokens = "required"`) para impedir ataques SSRF que podrían robar credenciales del instance profile.
    * En el caso del servidor de normabot es necesario añadir manualmente un .env entrando en la instancia que incluya las variables de entorno que usa:
    ```
    AWS_REGION=eu-west-1
    BEDROCK_MODEL_ID=eu.amazon.nova-lite-v1:0
    LANGFUSE_PUBLIC_KEY=your_public_key
    LANGFUSE_SECRET_KEY=your_secret_key
    LANGFUSE_HOST=https://cloud.langfuse.com
    APP_VERSION=vX.X.X
    MLFLOW_TRACKING_URI=https://<ip-mlflow>/mlflow/
    MLFLOW_PASSWORD=your_password
    MLFLOW_TRACKING_INSECURE_TLS=true
    GHCR_READ_TOKEN=your_token
    GHCR_READ_USER=your_user
    ```

### Bases de datos
De momento solo hay una para MLflow. Es preferible usar SQLite dentro de la propia instancia de EC2 porque es coste 0€ y evita los gastos y la gestión que supone una RDS (usuarios, redes, copias de seguridad).

### Almacenamiento en bloque (EBS)
* Enlazadas a las instancias de EC2, tienen `prevent_destroy = true` en Terraform: ni siquiera un `terraform destroy` puede eliminarlas. Hay que borrarlas manualmente desde la consola de AWS si fuera necesario.
* Se usa gp3, porque es más barato que gp2 y rinde mejor.
* Se usan dos volúmenes separados: 10GB para MLflow y 30GB para NormaBot. El volumen de NormaBot se amplió de 20GB a 30GB porque la imagen Docker (~12GB comprimida) más los snapshots de containerd superaban el espacio disponible en 20GB. Están desacoplados de las instancias para que los datos persistan aunque se elimine el servidor. La infraestructura actual está fuera del free-tier de AWS.
* Los volúmenes root de cada instancia tienen `delete_on_termination = true` porque solo contienen el SO y Docker — nada que no se pueda recrear con Ansible. Los datos que importan están en los volúmenes separados.

## Integración y despliegue continuo (CI/CD)
* Se usa GitHub Actions por estar integrado con el repositorio.
* Las imágenes Docker se publican en GitHub Container Registry (ghcr.io) porque es gratuito para repositorios públicos, a diferencia de ECR de AWS que tiene coste por almacenamiento.
* Hay cuatro workflows separados:
    * `pr_lint.yml`: lint con ruff solo sobre los ficheros `.py`/`.ipynb` modificados, en cada PR a `main` o `develop`.
    * `ci-develop.yml`: lint completo + construye y publica la imagen con tag `:develop` en cada push a `develop`, para poder probarla manualmente.
    * `cicd-main.yml`: lint + construye, publica con tag `:latest` y despliega automáticamente en el servidor en cada push a `main`.
    * `eval.yml`: ejecuta la evaluación RAGAS en EC2 contra la imagen `:latest` desplegada. Se lanza manualmente (`workflow_dispatch`).
* El despliegue se hace vía SSH a la EC2. El script de deploy hace login en GHCR, `dvc pull` del vectorstore y levanta el contenedor con `docker compose up -d --pull always --force-recreate`. Pendiente: valorar si simplificar a `docker run` directo.
* Los tests del clasificador se ejecutan con `pytest` (definidos en `tests/`, dependencias en `requirements/dev.txt`).

## Observabilidad y trazabilidad
* Usamos [MLflow](https://mlflow.org/) para los modelos de clasificación: métricas de entrenamiento y registro del modelo.
* Usamos [Langfuse](https://langfuse.com/) v3 para el orquestador (LangGraph) y sus agentes:
    * Podemos auditar el flujo paso a paso y entender su respuesta. Si falla el agente podemos ver si fue en el Retrieve, en el Grade de relevancia o en la generación final del LLM provider (Amazon Nova Lite vía Bedrock).
    * Permite monitorizar usos en tiempo real del consumo de tokens, latencias y alucinaciones mediante métricas.
    * Gestiona versiones de prompts.
    * Cobertura de instrumentación por módulo con `@observe` de Langfuse v3:
        * `rag/main.py` — retrieve, grade, generate: con `level=ERROR` si ChromaDB no está disponible, y `level=WARNING` si Ollama o Bedrock caen al fallback.
        * `classifier/main.py` — predict_risk: registra nivel de riesgo, confianza y distribución de probabilidades; `score_current_trace` guarda la confianza del modelo como métrica numérica.
        * `report/main.py` — generate_report: registra si el informe lo generó Bedrock o el template estático (`grounded`), con `level=WARNING` en el caso de fallback.
        * `retriever.py` — search y search_tool: registra distancias min/max, número de resultados, fuentes únicas y si el contexto fue truncado.
        * `orchestrator/main.py` — las 3 herramientas del agente (search_legal_docs, classify_risk, generate_report) con `@observe`; el agente ReAct completo se captura con el CallbackHandler de LangChain.
    * Feedback de usuario (👍/👎) registrado como score en Langfuse directamente desde la UI de Streamlit.
    * En tests, Langfuse se desactiva con `LANGFUSE_ENABLED=false` en `tests/conftest.py` para evitar dependencias de credenciales en CI.