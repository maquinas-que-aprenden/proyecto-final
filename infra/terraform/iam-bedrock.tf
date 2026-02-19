# Política para invocar modelos en Amazon Bedrock
# Usa el inference profile EU (eu.amazon.nova-lite-v1:0) que enruta
# transparentemente a regiones EU (eu-central-1, eu-north-1, eu-west-3).

resource "aws_iam_policy" "bedrock_invoke_policy" {
  name = "NormaBot-Bedrock-Invoke-Policy"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowBedrockInvoke"
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = [
          "arn:aws:bedrock:eu-west-1::foundation-model/amazon.nova-lite-v1:0",
          "arn:aws:bedrock:eu-west-1:*:inference-profile/eu.amazon.nova-lite-v1:0",
          "arn:aws:bedrock:eu-central-1::foundation-model/amazon.nova-lite-v1:0",
          "arn:aws:bedrock:eu-north-1::foundation-model/amazon.nova-lite-v1:0",
          "arn:aws:bedrock:eu-west-3::foundation-model/amazon.nova-lite-v1:0"
        ]
      },
      {
        Sid    = "AllowBedrockGetProfile"
        Effect = "Allow"
        Action = ["bedrock:GetInferenceProfile"]
        Resource = "arn:aws:bedrock:eu-west-1:*:inference-profile/eu.amazon.nova-lite-v1:0"
      }
    ]
  })
}

# Acceso para desarrolladores (grupo NormaBot-Devs)
resource "aws_iam_group_policy_attachment" "dev_bedrock_attach" {
  group      = aws_iam_group.dev_group.name
  policy_arn = aws_iam_policy.bedrock_invoke_policy.arn
}

# Acceso para la instancia EC2 (producción)
resource "aws_iam_role_policy_attachment" "ec2_bedrock_attach" {
  role       = aws_iam_role.ec2_s3_access_role.name
  policy_arn = aws_iam_policy.bedrock_invoke_policy.arn
}
