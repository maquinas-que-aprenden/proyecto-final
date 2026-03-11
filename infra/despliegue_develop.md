# Acceso a los servidores EC2 de NormaBot

## Requisitos previos

- Cuenta AWS con acceso a la consola
- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) instalado y configurado (`aws configure`)
- Región configurada: `eu-west-1`

---

## 1. Crear tu clave SSH y enviarme la pública

### macOS / Linux

```bash
ssh-keygen -t ed25519 -C "tu-nombre-normabot" -f ~/.ssh/normabot
```

Esto genera dos ficheros:
- `~/.ssh/normabot` — clave privada (no la compartas con nadie)
- `~/.ssh/normabot.pub` — clave pública (esta es la que me tienes que pasar)

Para ver la clave pública:

```bash
cat ~/.ssh/normabot.pub
```

### Windows (PowerShell)

```powershell
ssh-keygen -t ed25519 -C "tu-nombre-normabot" -f "$env:USERPROFILE\.ssh\normabot"
```

Clave pública:

```powershell
cat "$env:USERPROFILE\.ssh\normabot.pub"
```

**Pásame el contenido de la clave pública por el canal privado de Discord o por DM — nunca la privada.**

Una vez que me la mandes, yo la añado al servidor y te confirmo que ya puedes entrar.

---

## 2. Gestión de las instancias con AWS CLI

> Usa esto solo cuando sea necesario. El reboot está pensado para cuando la instancia se queda colgada y no responde.

### Obtener el estado e IP actual

```bash
# NormaBot (app principal)
aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=NormaBot-Server" \
  --query "Reservations[0].Instances[0].{Estado:State.Name,IP:PublicIpAddress,ID:InstanceId}" \
  --output table \
  --region eu-west-1

# MLflow
aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=MLflow-Server" \
  --query "Reservations[0].Instances[0].{Estado:State.Name,IP:PublicIpAddress,ID:InstanceId}" \
  --output table \
  --region eu-west-1
```

### Start

```bash
# NormaBot
aws ec2 start-instances \
  --instance-ids $(aws ec2 describe-instances \
    --filters "Name=tag:Name,Values=NormaBot-Server" \
    --query "Reservations[0].Instances[0].InstanceId" \
    --output text --region eu-west-1) \
  --region eu-west-1

# MLflow
aws ec2 start-instances \
  --instance-ids $(aws ec2 describe-instances \
    --filters "Name=tag:Name,Values=MLflow-Server" \
    --query "Reservations[0].Instances[0].InstanceId" \
    --output text --region eu-west-1) \
  --region eu-west-1
```

### Stop

```bash
# NormaBot
aws ec2 stop-instances \
  --instance-ids $(aws ec2 describe-instances \
    --filters "Name=tag:Name,Values=NormaBot-Server" \
    --query "Reservations[0].Instances[0].InstanceId" \
    --output text --region eu-west-1) \
  --region eu-west-1

# MLflow
aws ec2 stop-instances \
  --instance-ids $(aws ec2 describe-instances \
    --filters "Name=tag:Name,Values=MLflow-Server" \
    --query "Reservations[0].Instances[0].InstanceId" \
    --output text --region eu-west-1) \
  --region eu-west-1
```

### Reboot

> Solo si la instancia no responde. El reboot **no cambia la IP pública**.

```bash
# NormaBot
aws ec2 reboot-instances \
  --instance-ids $(aws ec2 describe-instances \
    --filters "Name=tag:Name,Values=NormaBot-Server" \
    --query "Reservations[0].Instances[0].InstanceId" \
    --output text --region eu-west-1) \
  --region eu-west-1

# MLflow
aws ec2 reboot-instances \
  --instance-ids $(aws ec2 describe-instances \
    --filters "Name=tag:Name,Values=MLflow-Server" \
    --query "Reservations[0].Instances[0].InstanceId" \
    --output text --region eu-west-1) \
  --region eu-west-1
```

> **Aviso:** hacer un stop + start **cambia la IP pública** de la instancia. Después de arrancarla, consulta la IP actual con el comando `describe-instances` de arriba.

---

## 3. Conectarse por SSH

> **La IP pública cambia cada vez que la instancia se para y se vuelve a arrancar.** Antes de conectarte, consulta la IP actual con el comando de abajo — no uses una IP guardada de una sesión anterior.

### Obtener la IP actual

```bash
aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=NormaBot-Server" \
  --query "Reservations[0].Instances[0].PublicIpAddress" \
  --output text \
  --region eu-west-1
```

### Conectarse

```bash
ssh -i ~/.ssh/normabot ubuntu@<IP>
```

Ejemplo:

```bash
ssh -i ~/.ssh/normabot ubuntu@34.244.146.100
```

---

## 4. Despliegue manual

Conéctate primero por SSH al servidor (sección anterior) y ejecuta los pasos en orden.

### Limpiar

```bash
# 1. Para contenedores en marcha (si los hay)
docker stop normabot && docker rm normabot

# 2. Borra imágenes, contenedores parados y build cache
docker system prune -a -f

# 3. Borra volúmenes nombrados (NO incluidos en el paso anterior)
docker volume rm ollama_models

# 4. Verifica que hay espacio suficiente antes de continuar (lo habrá, no te preocupes)
docker system df
df -h /home/ubuntu/normabot
```

### Desplegar

```bash
# 1. Exportar variables del .env
export $(grep -v '^#' /home/ubuntu/normabot/.env | xargs)

# 2. Login al container registry con las credenciales del .env
echo "$GHCR_READ_TOKEN" | docker login ghcr.io -u "$GHCR_READ_USER" --password-stdin

# 3. Pull de la imagen más reciente
docker pull ghcr.io/maquinas-que-aprenden/proyecto-final:develop

# 4. Arrancar con el .env
cd /home/ubuntu/normabot
docker run -d --name normabot \
  --user root \
  -e HOME=/home/appuser \
  -p 8080:8080 --env-file .env \
  -v $(pwd)/data/processed/vectorstore:/app/data/processed/vectorstore \
  -v $(pwd)/eval:/app/eval \
  -v ollama_models:/home/appuser/.ollama \
  -v normabot_memory:/app/data/memory \
  --entrypoint sh \
  ghcr.io/maquinas-que-aprenden/proyecto-final:develop \
  -c "/ollama-entrypoint.sh"

# 5. Logout (buena práctica)
docker logout ghcr.io
```

### Verificar que arrancó

```bash
docker ps
```

### Ver los logs mientras se ejecuta
```bash
docker logs -f normabot
```

> `docker logs -f` se queda siguiendo los logs en tiempo real. Pulsa **Ctrl+C** para salir — esto solo cierra la vista de logs, no para el contenedor.

---

## 5. Ejecutar la evaluación RAGAS manualmente

La forma recomendada es lanzar el workflow desde GitHub Actions (_Actions → NormaBot RAGAS Eval → Run workflow_). Si quieres ejecutarlo a mano desde el servidor:

```bash
# Conéctate al servidor
ssh -i ~/.ssh/normabot ubuntu@<IP>

# Actualiza los ficheros de eval desde git (el contenedor los ve vía bind mount)
cd /home/ubuntu/normabot
git pull

# Lanza la evaluación en el contenedor en marcha
docker exec \
  -e PYTHONPATH=/app:/app/eval \
  normabot \
  python eval/run_ragas.py --ci
```

El script tarda varios minutos (llama a Bedrock por cada pregunta del dataset). Los resultados se registran en MLflow (experimento `ragas_eval`) y en Langfuse etiquetados con el SHA del commit actual.