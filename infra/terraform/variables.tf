variable "instance_type" {
  default = "t3.micro"
}

variable "ami_id" {
  # Ubuntu Server 24.04 LTS (HVM), SSD Volume Type
  default = "ami-03446a3af42c5e74e" 
}

variable "key_name" {
  description = "Nombre del Key Pair en AWS"
  type        = string
}

variable "ruta_pem" {
  type        = string
  description = "Ruta local al archivo .pem"
}