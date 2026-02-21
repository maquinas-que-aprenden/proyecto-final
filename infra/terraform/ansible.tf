resource "local_file" "ansible_inventory" {
  content  = <<-EOT
    [mlflow]
    ${aws_instance.mlflow_server.public_ip} ansible_user=ubuntu ansible_ssh_private_key_file=~/.ssh/aws.pem

    [normabot]
    ${aws_instance.normabot_server.public_ip} ansible_user=ubuntu ansible_ssh_private_key_file=~/.ssh/aws.pem
  EOT
  filename = "../ansible/inventory.ini"
}