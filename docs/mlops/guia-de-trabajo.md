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

**Prerequisitos**: tienen que estar instaladas las dependencias: `awscli`, `dvc`, `dvc-s3` que deberían estar en `requirements.txt`.

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
dvc add models/vector_db
```
2. Hacer `push` para subirla a S3:
```bash
dvc push
```
3. Para sincronizar con GitHub:
```bash
git add models/vector_db.dvc .gitignore
git commit -m "Actualizar VectorDB version X"
git push origin <tu-rama>
```

#### Gestionar binarios de modelos
El modelo de clasificación generará archivos cada vez que se termine de entrenar que pueden ser versionados.
1. Añadir la ruta con el binario: 
```bash
dvc add models/classifier/classifier_v1.joblib
```
2. Hacer `push` para subirlo a S3:
```bash
dvc push
```
3. Para sincronizar con GitHub:
```bash
git add models/classifier/classifier_v1.joblib.dvc .gitignore
git commit -m "Actualizar modelo de clasificación version X"
git push origin <tu-rama>
```

## Observabilidad y trazabilidad

### Langfuse Cloud
Tenemos una cuenta común para [Langfuse Cloud](https://cloud.langfuse.com/) y una API key para mandar trazas que se puede consultar en la web.

Para más información, consultar la documentación oficial: [Langfuse: get started](https://langfuse.com/docs/observability/get-started)

### MLflow
Tenemos levantado un servidor para MLflow. Para usarlo, después de importar la librería hay que indicar el servidor de la siguiente manera:
```
remote_server_uri = "http://<IP-de-instancia-EC2>:5000" 
mlflow.set_tracking_uri(remote_server_uri)
```
Para más información, consultar la documentación oficial: [Logging to a tracking server](https://mlflow.org/docs/latest/self-hosting/architecture/tracking-server/#logging_to_a_tracking_server)

La UI también está levantada en la misma IP y puerto.

## Infraestructura como Código
Usamos IaC para garantizar entornos reproducibles, escalables y que se desplieguen rápido con control de versiones.

### Terraform
* Estamos usando [Terraform](https://developer.hashicorp.com/terraform) para desplegar los servicios básicos de AWS que usamos: VPC, EC2, S3, IAM (usuarios, grupos, roles, políticas).
* El estado de terraform (tfstate) guarda el estado existente de todos los recursos que se han desplegado con él. Sin el habría que importarlos todos manualmente para que los reconozca. Por eso, para que no se pierda, está guardado en nuestro bucket de S3 en el path `state`.

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

Para desplegar o destruir hay que tener permisos para crear los recursos en AWS, requiere un key pair de EC2.

### Ansible
* Estamos usando [Ansible](https://docs.ansible.com/) para configurar el único servidor que tenemos. Tenemos un playbook que descarga e instala paquetes (`playbook.yaml`) y otro que levanta MLflow con una plantilla de [docker compose](http://docs.docker.com/compose/) (`deploy_mlflow.yaml`).
* El inventario que usa ansible (`inventory.ini`) se genera autómaticamente con terraform o se puede usar esta plantilla:
```bash
[normabot]
<sustituir_IP> ansible_user=ubuntu ansible_ssh_private_key_file=~/.ssh/aws.pem
```

#### Cómo ejecutar
```bash
ansible-playbook -i inventory.ini <nombre-del-playbook>.yaml
```
Aviso: puede que falle en la primera ejecución.