resource "aws_instance" "normabot_server" {
  ami           = var.ami_id
  instance_type = var.instance_type
  key_name      = var.key_name
  
  security_groups      = [aws_security_group.normabot_sg.name]
  iam_instance_profile = aws_iam_instance_profile.ec2_profile.name

  # EBS 
  root_block_device {
    volume_size           = 20
    volume_type           = "gp3"
    delete_on_termination = false # para no perder datos
    
    tags = {
      Name = "NormaBot-Disk"
    }
  }
}