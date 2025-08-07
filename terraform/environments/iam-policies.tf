# IAM Policies for Environment Isolation
# This file defines IAM policies that enforce environment isolation

# Data source for current AWS account
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# Environment-specific IAM policy for GitHub Actions
resource "aws_iam_policy" "github_actions_policy" {
  name        = "${var.project_name}-${var.environment}-github-actions-policy"
  description = "IAM policy for GitHub Actions in ${var.environment} environment"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # S3 permissions - restricted to environment-specific bucket
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket",
          "s3:GetBucketLocation",
          "s3:GetBucketVersioning"
        ]
        Resource = [
          "arn:aws:s3:::${var.project_name}-${var.environment}-*",
          "arn:aws:s3:::${var.project_name}-${var.environment}-*/*"
        ]
      },
      # Lambda permissions - restricted to environment-specific functions
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction",
          "lambda:GetFunction",
          "lambda:UpdateFunctionCode",
          "lambda:UpdateFunctionConfiguration",
          "lambda:PublishVersion",
          "lambda:CreateAlias",
          "lambda:UpdateAlias"
        ]
        Resource = [
          "arn:aws:lambda:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:function:${var.project_name}-${var.environment}-*"
        ]
      },
      # ECS permissions - restricted to environment-specific cluster
      {
        Effect = "Allow"
        Action = [
          "ecs:RunTask",
          "ecs:StopTask",
          "ecs:DescribeTasks",
          "ecs:DescribeServices",
          "ecs:UpdateService",
          "ecs:DescribeClusters"
        ]
        Resource = [
          "arn:aws:ecs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:cluster/${var.project_name}-${var.environment}-*",
          "arn:aws:ecs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:service/${var.project_name}-${var.environment}-*/*",
          "arn:aws:ecs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:task/${var.project_name}-${var.environment}-*/*"
        ]
      },
      # CloudWatch permissions - restricted to environment-specific resources
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams"
        ]
        Resource = [
          "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/${var.project_name}-${var.environment}-*",
          "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:/ecs/${var.project_name}-${var.environment}-*"
        ]
      },
      # Secrets Manager permissions - restricted to environment-specific secrets
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = [
          "arn:aws:secretsmanager:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:secret:${var.project_name}-${var.environment}-*"
        ]
      },
      # EventBridge permissions - restricted to environment-specific rules
      {
        Effect = "Allow"
        Action = [
          "events:PutEvents",
          "events:DescribeRule",
          "events:ListTargetsByRule"
        ]
        Resource = [
          "arn:aws:events:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:rule/${var.project_name}-${var.environment}-*"
        ]
      },
      # SNS permissions - restricted to environment-specific topics
      {
        Effect = "Allow"
        Action = [
          "sns:Publish"
        ]
        Resource = [
          "arn:aws:sns:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:${var.project_name}-${var.environment}-*"
        ]
      },
      # SSM permissions for deployment tracking
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:PutParameter",
          "ssm:GetParameters"
        ]
        Resource = [
          "arn:aws:ssm:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:parameter/${var.project_name}/deployments/${var.environment}/*"
        ]
      }
    ]
  })

  tags = {
    Environment = var.environment
    Project     = var.project_name
    Purpose     = "environment-isolation"
  }
}

# GitHub Actions OIDC role for environment isolation
resource "aws_iam_role" "github_actions_role" {
  name = "${var.project_name}-${var.environment}-github-actions-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:oidc-provider/token.actions.githubusercontent.com"
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          }
          StringLike = {
            "token.actions.githubusercontent.com:sub" = [
              "repo:${var.github_repository}:environment:${var.environment}",
              "repo:${var.github_repository}:ref:refs/heads/${var.environment == "prod" ? "main" : var.environment == "staging" ? "main" : "develop"}"
            ]
          }
        }
      }
    ]
  })

  tags = {
    Environment = var.environment
    Project     = var.project_name
    Purpose     = "github-actions-oidc"
  }
}

# Attach policy to GitHub Actions role
resource "aws_iam_role_policy_attachment" "github_actions_policy_attachment" {
  role       = aws_iam_role.github_actions_role.name
  policy_arn = aws_iam_policy.github_actions_policy.arn
}

# Cross-environment access prevention policy
resource "aws_iam_policy" "deny_cross_environment_access" {
  name        = "${var.project_name}-${var.environment}-deny-cross-env-policy"
  description = "Deny access to other environment resources"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Deny"
        Action = "*"
        Resource = [
          # Deny access to other environment S3 buckets
          "arn:aws:s3:::${var.project_name}-dev-*",
          "arn:aws:s3:::${var.project_name}-staging-*",
          "arn:aws:s3:::${var.project_name}-prod-*"
        ]
        Condition = {
          StringNotEquals = {
            "aws:RequestedRegion" = data.aws_region.current.name
          }
        }
      },
      {
        Effect = "Deny"
        Action = "*"
        Resource = [
          # Deny access to other environment Lambda functions
          "arn:aws:lambda:*:${data.aws_caller_identity.current.account_id}:function:${var.project_name}-*"
        ]
        Condition = {
          StringNotLike = {
            "aws:userid" = "*:${var.project_name}-${var.environment}-*"
          }
        }
      }
    ]
  })

  tags = {
    Environment = var.environment
    Project     = var.project_name
    Purpose     = "cross-environment-isolation"
  }
}

# Environment-specific resource tagging policy
resource "aws_iam_policy" "resource_tagging_policy" {
  name        = "${var.project_name}-${var.environment}-tagging-policy"
  description = "Enforce consistent resource tagging for ${var.environment}"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Deny"
        Action = [
          "ec2:RunInstances",
          "s3:CreateBucket",
          "lambda:CreateFunction",
          "ecs:CreateCluster",
          "ecs:CreateService"
        ]
        Resource = "*"
        Condition = {
          "Null" = {
            "aws:RequestTag/Environment" = "true"
          }
        }
      },
      {
        Effect = "Deny"
        Action = [
          "ec2:RunInstances",
          "s3:CreateBucket",
          "lambda:CreateFunction",
          "ecs:CreateCluster",
          "ecs:CreateService"
        ]
        Resource = "*"
        Condition = {
          StringNotEquals = {
            "aws:RequestTag/Environment" = var.environment
          }
        }
      }
    ]
  })

  tags = {
    Environment = var.environment
    Project     = var.project_name
    Purpose     = "resource-tagging-enforcement"
  }
}