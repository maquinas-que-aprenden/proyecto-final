# Política para invocar modelos en Amazon Bedrock
# Usa el inference profile EU (eu.amazon.nova-lite-v1:0) que enruta
# transparentemente a regiones EU (eu-central-1, eu-north-1, eu-west-3).

data "aws_caller_identity" "current" {}

resource "aws_iam_policy" "bedrock_invoke_policy" {

  name = "NormaBot-Bedrock-Invoke-Policy"
  policy = jsonencode({
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "ConverseNovaLiteViaInferenceProfile",
            "Effect": "Allow",
            "Action": [
                "bedrock:InvokeModel",
                "bedrock:InvokeModelWithResponseStream"
            ],
            "Resource": "arn:aws:bedrock:*:643260088669:inference-profile/eu.amazon.nova-lite-v1:0"
        },
        {
            "Sid": "AllowNovaLiteOnly",
            "Effect": "Allow",
            "Action": [
                "bedrock:InvokeModel",
                "bedrock:InvokeModelWithResponseStream"
            ],
            "Resource": [
                "arn:aws:bedrock:*::foundation-model/amazon.nova-lite-v1:0",
                "arn:aws:bedrock:*:643260088669:inference-profile/eu.amazon.nova-lite-v1:0"
            ]
        }
    ]
  })
}

# Acceso para desarrolladores (grupo NormaBot-Devs)
resource "aws_iam_group_policy_attachment" "dev_bedrock_attach" {
  group      = aws_iam_group.dev_group.name
  policy_arn = aws_iam_policy.bedrock_invoke_policy.arn
}
