# Usuarios
resource "aws_iam_user" "malvarez" {
  name = "malvarez"
}
resource "aws_iam_user" "docando" {
  name = "docando"
}
resource "aws_iam_user" "rcerezo" {
  name = "rcerezo"
}
resource "aws_iam_user" "ngarea" {
  name = "ngarea"
}

# Grupos
resource "aws_iam_group" "dev_group" {
  name = "NormaBot-Devs"
}

# Políticas de grupos
resource "aws_iam_policy" "dev_s3_policy" {
  name        = "NormaBot-S3-Full-Policy"   
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "AllowS3Actions"
        Effect   = "Allow"
        Action   = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:ListBucket",
          "s3:DeleteObject"
        ]
        Resource = [
          "arn:aws:s3:::normabot",
          "arn:aws:s3:::normabot/*"
        ]
      },
      {
        Sid      = "EnforceSSL"
        Effect   = "Deny"
        Action   = "s3:*"
        Resource = [
          "arn:aws:s3:::normabot",
          "arn:aws:s3:::normabot/*"
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      }
    ]
  })
}

# Asignar usuarios a grupos
resource "aws_iam_group_membership" "dev_team" {
  name = "normabot-dev-membership"
  users = [
    aws_iam_user.malvarez.name,
    aws_iam_user.docando.name,
    aws_iam_user.rcerezo.name,
    aws_iam_user.ngarea.name
  ]
  group = aws_iam_group.dev_group.name
}

# Asignar políticas a grupos
resource "aws_iam_group_policy_attachment" "dev_attach" {
  group      = aws_iam_group.dev_group.name
  policy_arn = aws_iam_policy.dev_s3_policy.arn
}