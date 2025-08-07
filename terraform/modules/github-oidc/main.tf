# GitHub OIDC Provider and IAM Roles for CI/CD
# This module creates the OIDC identity provider and environment-specific IAM roles

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# Data sources
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# GitHub OIDC Identity Provider
resource "aws_iam_openid_connect_provider" "github" {
  count = var.create_oidc_provider ? 1 : 0

  url = "https://token.actions.githubusercontent.com"

  client_id_list = [
    "sts.amazonaws.com",
  ]

  thumbprint_list = [
    "6938fd4d98bab03faadb97b34396831e3780aea1",
    "1c58a3a8518e8759bf075b76b750d4f2df264fcd"
  ]

  tags = {
    Name        = "github-actions-oidc-provider"
    Purpose     = "github-actions-authentication"
    ManagedBy   = var.project_name
    Environment = "shared"
  }
}

# Environment-specific GitHub Actions IAM Role
resource "aws_iam_role" "github_actions" {
  for_each = var.environments

  name = "${var.project_name}-${each.key}-github-actions-role"
  path = "/github-actions/"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = var.create_oidc_provider ? aws_iam_openid_connect_provider.github[0].arn : var.existing_oidc_provider_arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          }
          StringLike = {
            "token.actions.githubusercontent.com:sub" = [
              "repo:${var.github_repository}:environment:${each.key}",
              "repo:${var.github_repository}:ref:refs/heads/${each.value.branch_pattern}",
              "repo:${var.github_repository}:ref:refs/tags/*"
            ]
          }
        }
      }
    ]
  })

  max_session_duration = var.max_session_duration

  tags = {
    Name        = "${var.project_name}-${each.key}-github-actions-role"
    Environment = each.key
    Project     = var.project_name
    Purpose     = "github-actions-deployment"
  }
}

# Environment-specific deployment policy
resource "aws_iam_policy" "github_actions_deployment" {
  for_each = var.environments

  name        = "${var.project_name}-${each.key}-deployment-policy"
  description = "Deployment permissions for ${each.key} environment"
  path        = "/github-actions/"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat([
      # Terraform state management
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::${var.terraform_state_bucket}",
          "arn:aws:s3:::${var.terraform_state_bucket}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:DeleteItem"
        ]
        Resource = "arn:aws:dynamodb:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:table/${var.terraform_lock_table}"
      },
      # Environment-specific resource management
      {
        Effect = "Allow"
        Action = [
          "lambda:*",
          "ecs:*",
          "s3:*",
          "iam:*",
          "logs:*",
          "events:*",
          "sns:*",
          "secretsmanager:*",
          "ssm:*",
          "ec2:*",
          "ecr:*",
          "application-autoscaling:*"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "aws:RequestedRegion" = each.value.aws_region
          }
          StringLike = {
            "aws:RequestTag/Environment" = each.key
          }
        }
      },
      # CloudFormation permissions for Terraform
      {
        Effect = "Allow"
        Action = [
          "cloudformation:*"
        ]
        Resource = "*"
        Condition = {
          StringLike = {
            "cloudformation:StackName" = "${var.project_name}-${each.key}-*"
          }
        }
      }
    ], each.value.additional_permissions)
  })

  tags = {
    Environment = each.key
    Project     = var.project_name
    Purpose     = "deployment-permissions"
  }
}

# Attach deployment policy to role
resource "aws_iam_role_policy_attachment" "github_actions_deployment" {
  for_each = var.environments

  role       = aws_iam_role.github_actions[each.key].name
  policy_arn = aws_iam_policy.github_actions_deployment[each.key].arn
}

# Environment isolation policy - prevents cross-environment access
resource "aws_iam_policy" "environment_isolation" {
  for_each = var.environments

  name        = "${var.project_name}-${each.key}-isolation-policy"
  description = "Prevent access to other environment resources"
  path        = "/github-actions/"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # Deny access to other environment resources
      {
        Effect = "Deny"
        Action = "*"
        Resource = "*"
        Condition = {
          StringLike = {
            "aws:RequestTag/Environment" = [
              for env_name in keys(var.environments) : env_name if env_name != each.key
            ]
          }
        }
      },
      # Deny modification of resources tagged with other environments
      {
        Effect = "Deny"
        Action = [
          "lambda:*",
          "ecs:*",
          "s3:*",
          "logs:*",
          "events:*",
          "sns:*"
        ]
        Resource = "*"
        Condition = {
          StringNotEquals = {
            "aws:ResourceTag/Environment" = each.key
          }
          "Null" = {
            "aws:ResourceTag/Environment" = "false"
          }
        }
      }
    ]
  })

  tags = {
    Environment = each.key
    Project     = var.project_name
    Purpose     = "environment-isolation"
  }
}

# Attach isolation policy to role
resource "aws_iam_role_policy_attachment" "environment_isolation" {
  for_each = var.environments

  role       = aws_iam_role.github_actions[each.key].name
  policy_arn = aws_iam_policy.environment_isolation[each.key].arn
}

# Permission boundary for additional security
resource "aws_iam_policy" "permission_boundary" {
  name        = "${var.project_name}-github-actions-boundary"
  description = "Permission boundary for GitHub Actions roles"
  path        = "/github-actions/"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # Allow all actions within the project scope
      {
        Effect = "Allow"
        Action = "*"
        Resource = "*"
        Condition = {
          StringLike = {
            "aws:RequestTag/Project" = var.project_name
          }
        }
      },
      # Allow reading existing resources
      {
        Effect = "Allow"
        Action = [
          "sts:GetCallerIdentity",
          "sts:AssumeRole",
          "iam:GetRole",
          "iam:GetPolicy",
          "iam:ListRoles",
          "iam:ListPolicies",
          "s3:ListAllMyBuckets",
          "ec2:DescribeRegions",
          "ec2:DescribeAvailabilityZones"
        ]
        Resource = "*"
      },
      # Deny dangerous actions
      {
        Effect = "Deny"
        Action = [
          "iam:CreateUser",
          "iam:DeleteUser",
          "iam:CreateAccessKey",
          "iam:DeleteAccessKey",
          "iam:AttachUserPolicy",
          "iam:DetachUserPolicy",
          "organizations:*",
          "account:*"
        ]
        Resource = "*"
      }
    ]
  })

  tags = {
    Project   = var.project_name
    Purpose   = "permission-boundary"
    ManagedBy = "terraform"
  }
}

# Apply permission boundary to all GitHub Actions roles
resource "aws_iam_role_policy_attachment" "permission_boundary" {
  for_each = var.environments

  role       = aws_iam_role.github_actions[each.key].name
  policy_arn = aws_iam_policy.permission_boundary.arn
}

# Set permission boundary on roles
resource "aws_iam_role" "github_actions_with_boundary" {
  for_each = var.environments

  name                 = aws_iam_role.github_actions[each.key].name
  permissions_boundary = aws_iam_policy.permission_boundary.arn

  # This is a workaround to update the existing role with permission boundary
  lifecycle {
    ignore_changes = [
      assume_role_policy,
      description,
      force_detach_policies,
      max_session_duration,
      name,
      path,
      tags
    ]
  }

  depends_on = [aws_iam_role.github_actions]
}