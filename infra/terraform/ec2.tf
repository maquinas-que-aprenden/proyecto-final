resource "aws_instance" "normabot_server" {
  ami           = var.ami_id
  instance_type = var.instance_type
  key_name      = var.key_name
  
  subnet_id              = aws_subnet.public_subnet.id
  vpc_security_group_ids = [aws_security_group.normabot_sg.id]
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