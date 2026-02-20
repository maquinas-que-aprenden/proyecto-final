# Rol para MLflow (solo S3)
resource "aws_iam_role" "ec2_s3_access_role" {
  name = "NormaBot_EC2_S3_Role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "s3_access_policy" {
  name = "NormaBot_S3_Policy"
  role = aws_iam_role.ec2_s3_access_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action   = ["s3:GetObject", "s3:ListBucket", "s3:PutObject"]
      Effect   = "Allow"
      Resource = [
        "arn:aws:s3:::normabot",
        "arn:aws:s3:::normabot/*"
      ]
    }]
  })
}

resource "aws_iam_instance_profile" "ec2_profile" {
  name = "NormaBot_EC2_Profile"
  role = aws_iam_role.ec2_s3_access_role.name
}

# Rol para NormaBot Agent (S3 + Bedrock)
resource "aws_iam_role" "normabot_agent_role" {
  name = "NormaBot_Agent_EC2_Role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "normabot_agent_s3_policy" {
  name = "NormaBot_Agent_S3_Policy"
  role = aws_iam_role.normabot_agent_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action   = ["s3:GetObject", "s3:ListBucket", "s3:PutObject"]
      Effect   = "Allow"
      Resource = [
        "arn:aws:s3:::normabot",
        "arn:aws:s3:::normabot/*"
      ]
    }]
  })
}

resource "aws_iam_role_policy_attachment" "normabot_agent_bedrock_attach" {
  role       = aws_iam_role.normabot_agent_role.name
  policy_arn = aws_iam_policy.bedrock_invoke_policy.arn
}

resource "aws_iam_instance_profile" "normabot_agent_profile" {
  name = "NormaBot_Agent_EC2_Profile"
  role = aws_iam_role.normabot_agent_role.name
}