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