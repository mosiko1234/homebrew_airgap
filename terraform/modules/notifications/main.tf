# Notifications Module for Homebrew Bottles Sync
# Creates Secrets Manager secrets, IAM policies, and optional SNS topics

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# Secrets Manager Secret for Slack Webhook URL
resource "aws_secretsmanager_secret" "slack_webhook" {
  name                    = "${var.project_name}-slack-webhook"
  description             = "Slack webhook URL for Homebrew bottles sync notifications"
  recovery_window_in_days = var.secret_recovery_window_days

  # Note: Rotation rules are configured separately via aws_secretsmanager_secret_rotation

  tags = merge(var.tags, {
    Name       = "${var.project_name}-slack-webhook"
    Purpose    = "homebrew-bottles-sync"
    ManagedBy  = "terraform"
    SecretType = "slack-webhook"
  })
}

# Secrets Manager Secret Version for Slack Webhook URL
resource "aws_secretsmanager_secret_version" "slack_webhook" {
  count     = var.slack_webhook_url != "" ? 1 : 0
  secret_id = aws_secretsmanager_secret.slack_webhook.id
  secret_string = jsonencode({
    webhook_url = var.slack_webhook_url
    channel     = var.slack_channel
    username    = var.slack_username
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# Lambda Function for Secret Rotation (if enabled)
resource "aws_lambda_function" "secret_rotation" {
  count            = var.enable_secret_rotation ? 1 : 0
  filename         = "secret_rotation.zip"
  function_name    = "${var.project_name}-secret-rotation"
  role             = aws_iam_role.secret_rotation_role[0].arn
  handler          = "lambda_function.lambda_handler"
  source_code_hash = data.archive_file.secret_rotation_zip[0].output_base64sha256
  runtime          = "python3.11"
  timeout          = 60

  environment {
    variables = {
      SECRETS_MANAGER_ENDPOINT = "https://secretsmanager.${data.aws_region.current.name}.amazonaws.com"
    }
  }

  tags = merge(var.tags, {
    Name      = "${var.project_name}-secret-rotation"
    Purpose   = "homebrew-bottles-sync"
    ManagedBy = "terraform"
  })
}

# Archive file for secret rotation Lambda
data "archive_file" "secret_rotation_zip" {
  count       = var.enable_secret_rotation ? 1 : 0
  type        = "zip"
  output_path = "secret_rotation.zip"
  source {
    content  = <<EOF
import json
import boto3
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    Lambda function to handle secret rotation for Slack webhook URLs.
    This is a placeholder implementation - actual rotation logic would
    depend on your specific requirements.
    """
    logger.info("Secret rotation triggered")
    
    # In a real implementation, you would:
    # 1. Generate a new webhook URL or validate the existing one
    # 2. Test the new webhook URL
    # 3. Update the secret with the new value
    # 4. Update any dependent services
    
    return {
        'statusCode': 200,
        'body': json.dumps('Secret rotation completed successfully')
    }
EOF
    filename = "lambda_function.py"
  }
}

# IAM Role for Secret Rotation Lambda
resource "aws_iam_role" "secret_rotation_role" {
  count = var.enable_secret_rotation ? 1 : 0
  name  = "${var.project_name}-secret-rotation-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = merge(var.tags, {
    Name      = "${var.project_name}-secret-rotation-role"
    Purpose   = "homebrew-bottles-sync"
    ManagedBy = "terraform"
  })
}

# IAM Policy for Secret Rotation Lambda
resource "aws_iam_policy" "secret_rotation_policy" {
  count       = var.enable_secret_rotation ? 1 : 0
  name        = "${var.project_name}-secret-rotation-policy"
  description = "Policy for secret rotation Lambda function"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:DescribeSecret",
          "secretsmanager:GetSecretValue",
          "secretsmanager:PutSecretValue",
          "secretsmanager:UpdateSecretVersionStage"
        ]
        Resource = aws_secretsmanager_secret.slack_webhook.arn
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/${var.project_name}-secret-rotation*"
      }
    ]
  })

  tags = merge(var.tags, {
    Name      = "${var.project_name}-secret-rotation-policy"
    Purpose   = "homebrew-bottles-sync"
    ManagedBy = "terraform"
  })
}

# Attach policy to secret rotation role
resource "aws_iam_role_policy_attachment" "secret_rotation_policy_attachment" {
  count      = var.enable_secret_rotation ? 1 : 0
  role       = aws_iam_role.secret_rotation_role[0].name
  policy_arn = aws_iam_policy.secret_rotation_policy[0].arn
}

# Attach basic execution role to secret rotation role
resource "aws_iam_role_policy_attachment" "secret_rotation_basic_execution" {
  count      = var.enable_secret_rotation ? 1 : 0
  role       = aws_iam_role.secret_rotation_role[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Configure secret rotation
resource "aws_secretsmanager_secret_rotation" "slack_webhook" {
  count               = var.enable_secret_rotation ? 1 : 0
  secret_id           = aws_secretsmanager_secret.slack_webhook.id
  rotation_lambda_arn = aws_lambda_function.secret_rotation[0].arn

  rotation_rules {
    automatically_after_days = var.secret_rotation_days
  }

  depends_on = [aws_lambda_function.secret_rotation]
}

# Permission for Secrets Manager to invoke rotation Lambda
resource "aws_lambda_permission" "allow_secret_manager_call_Lambda" {
  count         = var.enable_secret_rotation ? 1 : 0
  function_name = aws_lambda_function.secret_rotation[0].function_name
  statement_id  = "AllowExecutionFromSecretsManager"
  action        = "lambda:InvokeFunction"
  principal     = "secretsmanager.amazonaws.com"
}

# IAM Policy for Lambda Functions to Access Secrets
resource "aws_iam_policy" "lambda_secrets_access" {
  name        = "${var.project_name}-lambda-secrets-access"
  description = "Policy for Lambda functions to access Slack webhook secret"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = aws_secretsmanager_secret.slack_webhook.arn
      }
    ]
  })

  tags = merge(var.tags, {
    Name      = "${var.project_name}-lambda-secrets-access"
    Purpose   = "homebrew-bottles-sync"
    ManagedBy = "terraform"
  })
}

# IAM Policy for ECS Tasks to Access Secrets
resource "aws_iam_policy" "ecs_secrets_access" {
  name        = "${var.project_name}-ecs-secrets-access"
  description = "Policy for ECS tasks to access Slack webhook secret"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = aws_secretsmanager_secret.slack_webhook.arn
      }
    ]
  })

  tags = merge(var.tags, {
    Name      = "${var.project_name}-ecs-secrets-access"
    Purpose   = "homebrew-bottles-sync"
    ManagedBy = "terraform"
  })
}

# Optional SNS Topic for Additional Notifications
resource "aws_sns_topic" "notifications" {
  count = var.enable_sns_notifications ? 1 : 0
  name  = "${var.project_name}-notifications"

  tags = merge(var.tags, {
    Name      = "${var.project_name}-notifications"
    Purpose   = "homebrew-bottles-sync"
    ManagedBy = "terraform"
  })
}

# SNS Topic Policy
resource "aws_sns_topic_policy" "notifications" {
  count  = var.enable_sns_notifications ? 1 : 0
  arn    = aws_sns_topic.notifications[0].arn
  policy = data.aws_iam_policy_document.sns_topic_policy[0].json
}

# SNS Topic Policy Document
data "aws_iam_policy_document" "sns_topic_policy" {
  count = var.enable_sns_notifications ? 1 : 0

  statement {
    effect = "Allow"
    principals {
      type        = "AWS"
      identifiers = var.lambda_role_arns
    }
    actions = [
      "sns:Publish"
    ]
    resources = [aws_sns_topic.notifications[0].arn]
  }

  statement {
    effect = "Allow"
    principals {
      type        = "AWS"
      identifiers = var.ecs_role_arns
    }
    actions = [
      "sns:Publish"
    ]
    resources = [aws_sns_topic.notifications[0].arn]
  }
}

# IAM Policy for SNS Publishing
resource "aws_iam_policy" "sns_publish_policy" {
  count       = var.enable_sns_notifications ? 1 : 0
  name        = "${var.project_name}-sns-publish-policy"
  description = "Policy for publishing to SNS notifications topic"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sns:Publish"
        ]
        Resource = aws_sns_topic.notifications[0].arn
      }
    ]
  })

  tags = merge(var.tags, {
    Name      = "${var.project_name}-sns-publish-policy"
    Purpose   = "homebrew-bottles-sync"
    ManagedBy = "terraform"
  })
}

# Email subscription to SNS topic (if email addresses provided)
resource "aws_sns_topic_subscription" "email_notifications" {
  count     = var.enable_sns_notifications && length(var.notification_email_addresses) > 0 ? length(var.notification_email_addresses) : 0
  topic_arn = aws_sns_topic.notifications[0].arn
  protocol  = "email"
  endpoint  = var.notification_email_addresses[count.index]
}

# CloudWatch Log Group for notification debugging
resource "aws_cloudwatch_log_group" "notifications" {
  name              = "/aws/notifications/${var.project_name}"
  retention_in_days = var.log_retention_days

  tags = merge(var.tags, {
    Name      = "${var.project_name}-notifications-logs"
    Purpose   = "homebrew-bottles-sync"
    ManagedBy = "terraform"
  })
}

# Data sources
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}