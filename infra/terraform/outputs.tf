output "mlflow_server_ip" {
  description = "IP pública del servidor MLflow"
  value       = aws_instance.mlflow_server.public_ip
}

output "normabot_server_ip" {
  description = "IP pública del servidor NormaBot (t3.large, detenida)"
  value       = aws_instance.normabot_server.public_ip
}

output "normabot_gpu_server_ip" {
  description = "IP pública del servidor NormaBot GPU"
  value       = aws_instance.normabot_gpu_server.public_ip
}