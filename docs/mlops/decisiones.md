# MLOps + Observabilidad

## Setup
* Repositorio público en GitHub:
    * GitFlow asegurado con rulesets.
    * Templates para crear issues y PRs.
    * Automatización de avisos de PRs.
* 1 cuenta free-tier por 6 meses en AWS
    * Utilizamos la región eu-west-1 (Irlanda) porque tenemos garantizado que hay más servicios que funcionan en el free-tier que, por ejemplo, en eu-south-2 (España). Está dentro de la UE por lo que cumple con la legislación que nos interesa y la latencia es baja.
* [Langfuse](https://langfuse.com/) Cloud en la región de datos EU.

## Gestión de accesos a AWS
* Se crea el usuario y se le asigna un rol con los permisos estrictamente necesarios para hacer su trabajo (_Principio del Mínimo Privilegio_).
* Se comparte un fichero `usuario_accessKeys.csv` con cada miembro del proyecto que contiene sus credenciales.
* Cada compañero descarga AWS CLI y lo configura localmente como se explica en la [guía de trabajo](guia-de-trabajo.md).

### Permisos
* Se crea un grupo `NormaBot-Devs`.
* Se le asigna al grupo una política con acceso restringido al bucket de S3 que vamos a utilizar.
* Se crea un usuario por compañero y se añade al grupo.

## Datos y versiones
* En vez de utilizar GitHub, Google Drive o HF Datasets para almacenar el corpus como se propone en los specs originales, para tener un punto que sea la fuente única de verdad y una mayor trazabilidad vamos usar el bucket de S3 `normabot` en `eu-west-1` con [DVC](https://dvc.org/).

## Observabilidad y trazabilidad
* Usamos [Langfuse](https://langfuse.com/) Cloud, porque es más conveniente y rápido que hacer un despliegue en AWS, permitiéndonos empezar a trabajar con ello de forma inmediata. El free tier cumple con nuestras necesidades y el que sea gestionado nos evita preocuparnos por mantener una base de datos.
    * Registra cada paso de la cadena de pensamiento del agente para entender su respuesta.
    * Permite monitorizar usos en tiempo real del consumo de tokens.
    * Monitorizar latencias.
    * Evaluar alucinaciones.
    * Gestionar versiones de prompts.