output "mlflow_server_ip" {
  description = "IP pública del servidor MLflow"
  value       = aws_instance.mlflow_server.public_ip
}

output "normabot_server_ip" {
  description = "IP pública del servidor NormaBot"
  value       = aws_instance.normabot_server.public_ip
}