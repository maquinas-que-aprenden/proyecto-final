resource "aws_instance" "normabot_server" {
  ami                         = var.ami_id
  instance_type               = "t3.medium"
  key_name                    = var.key_name
  associate_public_ip_address = true

  subnet_id              = aws_subnet.public_subnet.id
  vpc_security_group_ids = [aws_security_group.normabot_sg.id]
  iam_instance_profile = aws_iam_instance_profile.normabot_agent_profile.name

  root_block_device {
    volume_size           = 8
    volume_type           = "gp3"
    delete_on_termination = true
  }

  tags = {
    Name = "NormaBot-Server"
  }

  metadata_options {
    http_tokens = "required"
  }
}

resource "aws_ebs_volume" "normabot_data" {
  availability_zone = "eu-west-1a"
  size              = 20
  type              = "gp3"

  lifecycle {
    prevent_destroy = true
  }

  tags = {
    Name = "NormaBot-Disk"
  }
}

resource "aws_volume_attachment" "normabot_data_attach" {
  device_name  = "/dev/sdf"
  volume_id    = aws_ebs_volume.normabot_data.id
  instance_id  = aws_instance.normabot_server.id
  force_detach = true
  skip_destroy = true
}

resource "aws_instance" "mlflow_server" {
  ami           = var.ami_id
  instance_type = var.instance_type
  key_name      = var.key_name

  subnet_id              = aws_subnet.public_subnet.id
  vpc_security_group_ids = [aws_security_group.mlflow_sg.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2_profile.name

  root_block_device {
    volume_size           = 8
    volume_type           = "gp3"
    delete_on_termination = true
  }

  metadata_options {
    http_tokens = "required"
  }
}

resource "aws_ebs_volume" "mlflow_data" {
  availability_zone = "eu-west-1a"
  size              = 10
  type              = "gp3"

  lifecycle {
    prevent_destroy = true
  }

  tags = {
    Name = "MLflow-Disk"
  }
}

resource "aws_volume_attachment" "mlflow_data_attach" {
  device_name  = "/dev/sdf"
  volume_id    = aws_ebs_volume.mlflow_data.id
  instance_id  = aws_instance.mlflow_server.id

  # Al destruir la instancia, desconecta el volumen en lugar de destruirlo
  force_detach = true
  skip_destroy = true
}