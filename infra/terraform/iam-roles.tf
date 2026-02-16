# Rol para que la instancia EC2 pueda acceder a S3
resource "aws_iam_role" "ec2_s3_access_role" {
  name = "NormaBot_EC2_S3_Role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })
}

# Política inline del rol
resource "aws_iam_role_policy" "s3_access_policy" {
  name = "NormaBot_S3_Policy"
  role = aws_iam_role.ec2_s3_access_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action   = ["s3:GetObject", "s3:ListBucket", "s3:PutObject"]
        Effect   = "Allow"
        Resource = [
          "arn:aws:s3:::normabot",
          "arn:aws:s3:::normabot/*"
        ]
      }
    ]
  })
}

# Instance profile para asociar el rol a EC2
resource "aws_iam_instance_profile" "ec2_profile" {
  name = "NormaBot_EC2_Profile"
  role = aws_iam_role.ec2_s3_access_role.name
}
