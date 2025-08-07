# Environment Isolation Module
# Provides IAM policies and roles for environment isolation

# Data sources
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# Multi-account support configuration
locals {
  # Environment-specific AWS account mapping
  # This allows deployment to separate AWS accounts for enhanced isolation
  environment_accounts = {
    dev     = var.dev_aws_account_id != "" ? var.dev_aws_account_id : data.aws_caller_identity.current.account_id
    staging = var.staging_aws_account_id != "" ? var.staging_aws_account_id : data.aws_caller_identity.current.account_id
    prod    = var.prod_aws_account_id != "" ? var.prod_aws_account_id : data.aws_caller_identity.current.account_id
  }
  
  # Environment-specific region mapping for geographic isolation
  environment_regions = {
    dev     = var.environment == "dev" ? data.aws_region.current.name : "us-west-2"
    staging = var.environment == "staging" ? data.aws_region.current.name : "us-east-1"
    prod    = var.environment == "prod" ? data.aws_region.current.name : "us-east-1"
  }
  
  # Environment-specific naming conventions
  resource_prefix = "${var.project_name}-${var.environment}"
  
  # Current environment's target account
  target_account_id = local.environment_accounts[var.environment]
  
  # Environment-specific tags that will be applied to all resources
  environment_tags = merge(var.tags, {
    Environment     = var.environment
    Project         = var.project_name
    ManagedBy       = "terraform"
    AccountId       = local.target_account_id
    Region          = data.aws_region.current.name
    ResourcePrefix  = local.resource_prefix
    IsolationLevel  = var.enable_cross_environment_isolation ? "strict" : "standard"
    CreatedBy       = "environment-isolation-module"
    LastUpdated     = timestamp()
  })
}

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
          "arn:aws:s3:::${local.resource_prefix}-*",
          "arn:aws:s3:::${local.resource_prefix}-*/*"
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
          "arn:aws:lambda:${data.aws_region.current.name}:${local.target_account_id}:function:${local.resource_prefix}-*"
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
          "arn:aws:ecs:${data.aws_region.current.name}:${local.target_account_id}:cluster/${local.resource_prefix}-*",
          "arn:aws:ecs:${data.aws_region.current.name}:${local.target_account_id}:service/${local.resource_prefix}-*/*",
          "arn:aws:ecs:${data.aws_region.current.name}:${local.target_account_id}:task/${local.resource_prefix}-*/*"
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
          "arn:aws:logs:${data.aws_region.current.name}:${local.target_account_id}:log-group:/aws/lambda/${local.resource_prefix}-*",
          "arn:aws:logs:${data.aws_region.current.name}:${local.target_account_id}:log-group:/ecs/${local.resource_prefix}-*"
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
          "arn:aws:secretsmanager:${data.aws_region.current.name}:${local.target_account_id}:secret:${local.resource_prefix}-*"
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
          "arn:aws:events:${data.aws_region.current.name}:${local.target_account_id}:rule/${local.resource_prefix}-*"
        ]
      },
      # SNS permissions - restricted to environment-specific topics
      {
        Effect = "Allow"
        Action = [
          "sns:Publish"
        ]
        Resource = [
          "arn:aws:sns:${data.aws_region.current.name}:${local.target_account_id}:${local.resource_prefix}-*"
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
          "arn:aws:ssm:${data.aws_region.current.name}:${local.target_account_id}:parameter/${var.project_name}/deployments/${var.environment}/*"
        ]
      }
    ]
  })

  tags = var.tags
}

# GitHub Actions OIDC role for environment isolation
resource "aws_iam_role" "github_actions_role" {
  name = "${local.resource_prefix}-github-actions-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = "arn:aws:iam::${local.target_account_id}:oidc-provider/token.actions.githubusercontent.com"
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

  tags = var.tags
}

# Attach policy to GitHub Actions role
resource "aws_iam_role_policy_attachment" "github_actions_policy_attachment" {
  role       = aws_iam_role.github_actions_role.name
  policy_arn = aws_iam_policy.github_actions_policy.arn
}

# Attach cross-environment isolation policy to GitHub Actions role
resource "aws_iam_role_policy_attachment" "github_actions_cross_env_isolation" {
  count = var.enable_cross_environment_isolation ? 1 : 0
  
  role       = aws_iam_role.github_actions_role.name
  policy_arn = aws_iam_policy.deny_cross_environment_access[0].arn
}

# Attach resource tagging policy to GitHub Actions role
resource "aws_iam_role_policy_attachment" "github_actions_tagging_policy" {
  count = var.enforce_resource_tagging ? 1 : 0
  
  role       = aws_iam_role.github_actions_role.name
  policy_arn = aws_iam_policy.resource_tagging_policy[0].arn
}

# Additional security policy for environment isolation
resource "aws_iam_policy" "environment_security_policy" {
  name        = "${local.resource_prefix}-security-policy"
  description = "Additional security controls for ${var.environment} environment"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # Prevent modification of IAM roles/policies outside of this environment
      {
        Effect = "Deny"
        Action = [
          "iam:CreateRole",
          "iam:DeleteRole",
          "iam:AttachRolePolicy",
          "iam:DetachRolePolicy",
          "iam:PutRolePolicy",
          "iam:DeleteRolePolicy"
        ]
        Resource = "*"
        Condition = {
          StringNotLike = {
            "aws:RequestTag/Environment" = var.environment
          }
        }
      },
      # Prevent access to other environment's KMS keys
      {
        Effect = "Deny"
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey",
          "kms:Encrypt",
          "kms:GenerateDataKey*",
          "kms:ReEncrypt*"
        ]
        Resource = "*"
        Condition = {
          StringNotLike = {
            "kms:ViaService" = [
              "s3.${data.aws_region.current.name}.amazonaws.com",
              "lambda.${data.aws_region.current.name}.amazonaws.com",
              "logs.${data.aws_region.current.name}.amazonaws.com"
            ]
          }
          StringNotEquals = {
            "aws:RequestedRegion" = data.aws_region.current.name
          }
        }
      },
      # Restrict VPC operations to environment-specific resources
      {
        Effect = "Deny"
        Action = [
          "ec2:CreateVpc",
          "ec2:DeleteVpc",
          "ec2:ModifyVpcAttribute",
          "ec2:CreateSubnet",
          "ec2:DeleteSubnet"
        ]
        Resource = "*"
        Condition = {
          StringNotLike = {
            "aws:RequestTag/Environment" = var.environment
          }
        }
      }
    ]
  })

  tags = local.environment_tags
}

# Attach security policy to GitHub Actions role
resource "aws_iam_role_policy_attachment" "github_actions_security_policy" {
  role       = aws_iam_role.github_actions_role.name
  policy_arn = aws_iam_policy.environment_security_policy.arn
}

# Cross-environment access prevention policy
resource "aws_iam_policy" "deny_cross_environment_access" {
  count = var.enable_cross_environment_isolation ? 1 : 0

  name        = "${local.resource_prefix}-deny-cross-env-policy"
  description = "Deny access to other environment resources"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # Deny access to other environment S3 buckets
      {
        Effect = "Deny"
        Action = "*"
        Resource = flatten([
          for env in ["dev", "staging", "prod"] : [
            "arn:aws:s3:::${var.project_name}-${env}-*",
            "arn:aws:s3:::${var.project_name}-${env}-*/*"
          ] if env != var.environment
        ])
      },
      # Deny access to other environment Lambda functions
      {
        Effect = "Deny"
        Action = "*"
        Resource = flatten([
          for env in ["dev", "staging", "prod"] : [
            "arn:aws:lambda:*:*:function:${var.project_name}-${env}-*"
          ] if env != var.environment
        ])
      },
      # Deny access to other environment ECS resources
      {
        Effect = "Deny"
        Action = "*"
        Resource = flatten([
          for env in ["dev", "staging", "prod"] : [
            "arn:aws:ecs:*:*:cluster/${var.project_name}-${env}-*",
            "arn:aws:ecs:*:*:service/${var.project_name}-${env}-*/*",
            "arn:aws:ecs:*:*:task/${var.project_name}-${env}-*/*"
          ] if env != var.environment
        ])
      },
      # Deny access to other environment secrets
      {
        Effect = "Deny"
        Action = "*"
        Resource = flatten([
          for env in ["dev", "staging", "prod"] : [
            "arn:aws:secretsmanager:*:*:secret:${var.project_name}-${env}-*"
          ] if env != var.environment
        ])
      },
      # Deny access to other environment SNS topics
      {
        Effect = "Deny"
        Action = "*"
        Resource = flatten([
          for env in ["dev", "staging", "prod"] : [
            "arn:aws:sns:*:*:${var.project_name}-${env}-*"
          ] if env != var.environment
        ])
      },
      # Deny cross-account access if multi-account setup is used
      {
        Effect = "Deny"
        Action = "*"
        Resource = "*"
        Condition = {
          StringNotEquals = {
            "aws:RequestedRegion" = data.aws_region.current.name
          }
          StringNotLike = {
            "aws:userid" = "*:${local.resource_prefix}-*"
          }
        }
      }
    ]
  })

  tags = local.environment_tags
}

# Environment-specific resource tagging policy
resource "aws_iam_policy" "resource_tagging_policy" {
  count = var.enforce_resource_tagging ? 1 : 0

  name        = "${local.resource_prefix}-tagging-policy"
  description = "Enforce consistent resource tagging for ${var.environment}"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # Require Environment tag on resource creation
      {
        Effect = "Deny"
        Action = [
          "ec2:RunInstances",
          "s3:CreateBucket",
          "lambda:CreateFunction",
          "ecs:CreateCluster",
          "ecs:CreateService",
          "rds:CreateDBInstance",
          "elasticache:CreateCacheCluster",
          "sns:CreateTopic",
          "sqs:CreateQueue"
        ]
        Resource = "*"
        Condition = {
          "Null" = {
            "aws:RequestTag/Environment" = "true"
          }
        }
      },
      # Ensure Environment tag matches current environment
      {
        Effect = "Deny"
        Action = [
          "ec2:RunInstances",
          "s3:CreateBucket",
          "lambda:CreateFunction",
          "ecs:CreateCluster",
          "ecs:CreateService",
          "rds:CreateDBInstance",
          "elasticache:CreateCacheCluster",
          "sns:CreateTopic",
          "sqs:CreateQueue"
        ]
        Resource = "*"
        Condition = {
          StringNotEquals = {
            "aws:RequestTag/Environment" = var.environment
          }
        }
      },
      # Require Project tag
      {
        Effect = "Deny"
        Action = [
          "ec2:RunInstances",
          "s3:CreateBucket",
          "lambda:CreateFunction",
          "ecs:CreateCluster",
          "ecs:CreateService",
          "rds:CreateDBInstance",
          "elasticache:CreateCacheCluster",
          "sns:CreateTopic",
          "sqs:CreateQueue"
        ]
        Resource = "*"
        Condition = {
          "Null" = {
            "aws:RequestTag/Project" = "true"
          }
        }
      },
      # Ensure Project tag matches current project
      {
        Effect = "Deny"
        Action = [
          "ec2:RunInstances",
          "s3:CreateBucket",
          "lambda:CreateFunction",
          "ecs:CreateCluster",
          "ecs:CreateService",
          "rds:CreateDBInstance",
          "elasticache:CreateCacheCluster",
          "sns:CreateTopic",
          "sqs:CreateQueue"
        ]
        Resource = "*"
        Condition = {
          StringNotEquals = {
            "aws:RequestTag/Project" = var.project_name
          }
        }
      }
    ]
  })

  tags = local.environment_tags
}