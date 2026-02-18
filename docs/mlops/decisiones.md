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

### Máquinas virtuales
Inicialmente se plantea:
* Utilizar una sola instancia de EC2 para desplegar, con un Security Group e IP pública.
* Utilizar Docker Compose para mantener varios servicios aislados en la misma instancia.

### Bases de datos
De momento solo hay una para MLflow. Es preferible usar SQLite dentro de la propia instancia de EC2 porque es coste 0€ y evita los gastos y la gestión que supone una RDS (usuarios, redes, copias de seguridad).

### Almacenamiento en bloque
* Enlazada a la instancia de EC2 está configurada para persistir los datos en caso de que se elimine.
* Se usa gp3, porque es más barato que gp2 y rinde mejor.
* El tamaño es 20GB porque entra dentro de los 30GB gratis del free-tier de AWS y es suficiente espacio para imágenes de docker o datos que podamos necesitar.

## Observabilidad y trazabilidad
* Usamos [MLflow](https://mlflow.org/) para el modelo de clasificación (XGBoost): métricas de entrenamiento y registro del modelo.
* Usamos [Langfuse](https://langfuse.com/) para el orquestador (LangGraph) y sus agentes:
    * Podemos auditar el flujo paso a paso y entender su respuesta. Si falla el agente podemos ver si fue en el Retrieve, en el Grade de relevancia o en la generación final del LLM provider (Groq).
    * Permite monitorizar usos en tiempo real del consumo de tokens, latencias y alucinaciones mediante métricas.
    * Gestiona versiones de prompts.