# Notifications Module

This Terraform module creates notification infrastructure for the Homebrew Bottles Sync system, including Secrets Manager secrets for Slack webhooks, IAM policies for Lambda and ECS access, and optional SNS topics for additional notifications.

## Features

- **Secrets Manager Integration**: Secure storage of Slack webhook URLs with optional rotation
- **IAM Policies**: Least-privilege access policies for Lambda functions and ECS tasks
- **Optional SNS Topic**: Additional notification channel with email subscriptions
- **Secret Rotation**: Automated secret rotation with Lambda function (optional)
- **CloudWatch Logging**: Centralized logging for notification debugging

## Usage

```hcl
module "notifications" {
  source = "./modules/notifications"

  project_name        = "homebrew-bottles-sync"
  environment         = "prod"
  slack_webhook_url   = "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
  slack_channel       = "#homebrew-sync"
  slack_username      = "Homebrew Sync Bot"

  # Optional SNS notifications
  enable_sns_notifications     = true
  notification_email_addresses = ["admin@example.com", "devops@example.com"]

  # Optional secret rotation
  enable_secret_rotation = false
  secret_rotation_days   = 90

  # IAM role ARNs that need access to secrets
  lambda_role_arns = [
    "arn:aws:iam::123456789012:role/homebrew-lambda-orchestrator-role",
    "arn:aws:iam::123456789012:role/homebrew-lambda-sync-role"
  ]
  ecs_role_arns = [
    "arn:aws:iam::123456789012:role/homebrew-ecs-task-role"
  ]

  tags = {
    Environment = "prod"
    Project     = "homebrew-bottles-sync"
  }
}
```

## Requirements

| Name | Version |
|------|---------|
| terraform | >= 1.0 |
| aws | ~> 5.0 |

## Providers

| Name | Version |
|------|---------|
| aws | ~> 5.0 |
| archive | latest |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| project_name | Name of the project (used for resource naming) | `string` | n/a | yes |
| environment | Environment name (e.g., dev, staging, prod) | `string` | `"prod"` | no |
| slack_webhook_url | Slack webhook URL for notifications (sensitive) | `string` | `""` | no |
| slack_channel | Slack channel for notifications | `string` | `"#homebrew-sync"` | no |
| slack_username | Username for Slack bot notifications | `string` | `"Homebrew Sync Bot"` | no |
| secret_recovery_window_days | Number of days to retain deleted secrets for recovery | `number` | `7` | no |
| enable_secret_rotation | Enable automatic rotation of Slack webhook secret | `bool` | `false` | no |
| secret_rotation_days | Number of days between automatic secret rotations | `number` | `90` | no |
| enable_sns_notifications | Enable SNS topic for additional notifications | `bool` | `false` | no |
| notification_email_addresses | List of email addresses to subscribe to SNS notifications | `list(string)` | `[]` | no |
| lambda_role_arns | List of Lambda execution role ARNs that need access to secrets | `list(string)` | `[]` | no |
| ecs_role_arns | List of ECS task role ARNs that need access to secrets | `list(string)` | `[]` | no |
| log_retention_days | Number of days to retain CloudWatch logs | `number` | `30` | no |
| tags | Additional tags to apply to resources | `map(string)` | `{}` | no |
| kms_key_id | KMS key ID for encrypting secrets (optional) | `string` | `""` | no |
| enable_cross_region_backup | Enable cross-region backup for secrets | `bool` | `false` | no |
| backup_region | AWS region for cross-region secret backup | `string` | `""` | no |

## Outputs

| Name | Description |
|------|-------------|
| slack_webhook_secret_arn | ARN of the Slack webhook secret in Secrets Manager |
| slack_webhook_secret_name | Name of the Slack webhook secret in Secrets Manager |
| slack_webhook_secret_id | ID of the Slack webhook secret in Secrets Manager |
| lambda_secrets_access_policy_arn | ARN of the IAM policy for Lambda functions to access secrets |
| lambda_secrets_access_policy_name | Name of the IAM policy for Lambda functions to access secrets |
| ecs_secrets_access_policy_arn | ARN of the IAM policy for ECS tasks to access secrets |
| ecs_secrets_access_policy_name | Name of the IAM policy for ECS tasks to access secrets |
| sns_topic_arn | ARN of the SNS topic for notifications (if enabled) |
| sns_topic_name | Name of the SNS topic for notifications (if enabled) |
| sns_publish_policy_arn | ARN of the IAM policy for publishing to SNS topic (if enabled) |
| sns_publish_policy_name | Name of the IAM policy for publishing to SNS topic (if enabled) |
| secret_rotation_lambda_arn | ARN of the secret rotation Lambda function (if enabled) |
| secret_rotation_lambda_name | Name of the secret rotation Lambda function (if enabled) |
| cloudwatch_log_group_name | Name of the CloudWatch log group for notifications |
| cloudwatch_log_group_arn | ARN of the CloudWatch log group for notifications |

## Security Considerations

- **Secrets Management**: Slack webhook URLs are stored securely in AWS Secrets Manager with encryption at rest
- **Least Privilege**: IAM policies grant only the minimum required permissions for each service
- **Secret Rotation**: Optional automatic rotation helps maintain security hygiene
- **Encryption**: All secrets are encrypted using AWS managed keys or customer-provided KMS keys
- **Access Logging**: CloudWatch logs provide audit trails for secret access

## Secret Rotation

When `enable_secret_rotation` is set to `true`, the module creates a Lambda function that handles automatic rotation of the Slack webhook secret. The rotation function is a placeholder implementation that should be customized based on your specific requirements.

To implement custom rotation logic:

1. Modify the Lambda function code in the `data.archive_file.secret_rotation_zip` resource
2. Implement your specific rotation logic (e.g., generating new webhook URLs, validating endpoints)
3. Update the IAM policies if additional permissions are required

## SNS Integration

The optional SNS topic provides an additional notification channel that can be used for:

- Email notifications to administrators
- Integration with other AWS services (Lambda, SQS, etc.)
- Cross-account notifications
- Mobile push notifications (via SNS mobile endpoints)

## Examples

### Basic Configuration

```hcl
module "notifications" {
  source = "./modules/notifications"

  project_name      = "homebrew-bottles-sync"
  slack_webhook_url = var.slack_webhook_url
  lambda_role_arns  = [module.iam.lambda_orchestrator_role_arn]
  ecs_role_arns     = [module.iam.ecs_task_role_arn]
}
```

### Full Configuration with SNS and Rotation

```hcl
module "notifications" {
  source = "./modules/notifications"

  project_name        = "homebrew-bottles-sync"
  environment         = "prod"
  slack_webhook_url   = var.slack_webhook_url
  slack_channel       = "#homebrew-alerts"
  slack_username      = "Homebrew Bot"

  # Enable SNS notifications
  enable_sns_notifications     = true
  notification_email_addresses = ["admin@company.com"]

  # Enable secret rotation
  enable_secret_rotation = true
  secret_rotation_days   = 60

  # IAM role access
  lambda_role_arns = [
    module.iam.lambda_orchestrator_role_arn,
    module.iam.lambda_sync_role_arn
  ]
  ecs_role_arns = [module.iam.ecs_task_role_arn]

  # Custom KMS key for encryption
  kms_key_id = aws_kms_key.secrets.id

  tags = {
    Environment = "prod"
    Team        = "devops"
    CostCenter  = "engineering"
  }
}
```