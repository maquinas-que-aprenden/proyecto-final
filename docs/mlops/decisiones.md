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

### Permisos
* Se crea un grupo `NormaBot-Devs`.
* Se le asigna al grupo una política con acceso restringido al bucket de S3 que vamos a utilizar.
* Se crea un usuario por compañero y se añade al grupo.

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
A fecha de 20/02 se implementa:
* Separación en dos instancias: una para MLflow y otra para Normabot, cada una con su correspondiente security group.
    * MLflow necesita un t3.small, porque la memoria RAM de t3.micro del free-tier no es suficiente para su ejecución.
    * Vamos a empezar pruebas de despliegue de Normabot, utilizando inicialmente una t3.micro y escalando según sea necesario.
    * En el caso del servidor de normabot es necesario añadir manualmente un .env entrando en la instancia que incluya las variables de entorno que usa:
    ```
    AWS_REGION=eu-west-1
    BEDROCK_MODEL_ID=eu.amazon.nova-lite-v1:0
    LANGFUSE_PUBLIC_KEY=your_public_key
    LANGFUSE_SECRET_KEY=your_secret_key
    LANGFUSE_HOST=https://cloud.langfuse.com
    ```

### Bases de datos
De momento solo hay una para MLflow. Es preferible usar SQLite dentro de la propia instancia de EC2 porque es coste 0€ y evita los gastos y la gestión que supone una RDS (usuarios, redes, copias de seguridad).

### Almacenamiento en bloque (EBS)
* Enlazadas a las instancias de EC2, están configuradas para persistir los datos en caso de que se elimine.
* Se usa gp3, porque es más barato que gp2 y rinde mejor.
* Se usan dos volúmenes separados: 10GB para MLflow y 8GB para NormaBot. En total 18GB, dentro de los 30GB gratuitos del free-tier. Están desacoplados de las instancias para que los datos persistan aunque se elimine el servidor.
* Los volúmenes root de cada instancia tienen `delete_on_termination = true` porque solo contienen el SO y Docker — nada que no se pueda recrear con Ansible. Los datos que importan están en los volúmenes separados.

## Integración y despliegue continuo (CI/CD)
* Se usa GitHub Actions por estar integrado con el repositorio.
* Las imágenes Docker se publican en GitHub Container Registry (ghcr.io) porque es gratuito para repositorios públicos, a diferencia de ECR de AWS que tiene coste por almacenamiento.
* Hay dos workflows separados:
    * `ci-develop.yml`: solo construye y publica la imagen con tag `:develop` en cada push a `develop`, para poder probarla manualmente.
    * `cicd-main.yml`: construye, publica con tag `:latest` y despliega automáticamente en el servidor en cada push a `main`.
* El despliegue se hace vía SSH directamente a la EC2, sin orquestadores adicionales, porque para un MVP es suficiente y evita complejidad innecesaria.

## Observabilidad y trazabilidad
* Usamos [MLflow](https://mlflow.org/) para los modelos de clasificación: métricas de entrenamiento y registro del modelo.
* Usamos [Langfuse](https://langfuse.com/) para el orquestador (LangGraph) y sus agentes:
    * Podemos auditar el flujo paso a paso y entender su respuesta. Si falla el agente podemos ver si fue en el Retrieve, en el Grade de relevancia o en la generación final del LLM provider (Amazon Nova Lite vía Bedrock).
    * Permite monitorizar usos en tiempo real del consumo de tokens, latencias y alucinaciones mediante métricas.
    * Gestiona versiones de prompts.