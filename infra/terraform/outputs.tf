output "instance_public_ip" {
  description = "IP pública del servidor de NormaBot"
  value       = aws_instance.normabot_server.public_ip
}