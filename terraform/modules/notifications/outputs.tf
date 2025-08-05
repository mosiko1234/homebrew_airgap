# Outputs for Notifications Module

output "slack_webhook_secret_arn" {
  description = "ARN of the Slack webhook secret in Secrets Manager"
  value       = aws_secretsmanager_secret.slack_webhook.arn
}

output "slack_webhook_secret_name" {
  description = "Name of the Slack webhook secret in Secrets Manager"
  value       = aws_secretsmanager_secret.slack_webhook.name
}

output "slack_webhook_secret_id" {
  description = "ID of the Slack webhook secret in Secrets Manager"
  value       = aws_secretsmanager_secret.slack_webhook.id
}

output "lambda_secrets_access_policy_arn" {
  description = "ARN of the IAM policy for Lambda functions to access secrets"
  value       = aws_iam_policy.lambda_secrets_access.arn
}

output "lambda_secrets_access_policy_name" {
  description = "Name of the IAM policy for Lambda functions to access secrets"
  value       = aws_iam_policy.lambda_secrets_access.name
}

output "ecs_secrets_access_policy_arn" {
  description = "ARN of the IAM policy for ECS tasks to access secrets"
  value       = aws_iam_policy.ecs_secrets_access.arn
}

output "ecs_secrets_access_policy_name" {
  description = "Name of the IAM policy for ECS tasks to access secrets"
  value       = aws_iam_policy.ecs_secrets_access.name
}

output "sns_topic_arn" {
  description = "ARN of the SNS topic for notifications (if enabled)"
  value       = var.enable_sns_notifications ? aws_sns_topic.notifications[0].arn : null
}

output "sns_topic_name" {
  description = "Name of the SNS topic for notifications (if enabled)"
  value       = var.enable_sns_notifications ? aws_sns_topic.notifications[0].name : null
}

output "sns_publish_policy_arn" {
  description = "ARN of the IAM policy for publishing to SNS topic (if enabled)"
  value       = var.enable_sns_notifications ? aws_iam_policy.sns_publish_policy[0].arn : null
}

output "sns_publish_policy_name" {
  description = "Name of the IAM policy for publishing to SNS topic (if enabled)"
  value       = var.enable_sns_notifications ? aws_iam_policy.sns_publish_policy[0].name : null
}

output "secret_rotation_lambda_arn" {
  description = "ARN of the secret rotation Lambda function (if enabled)"
  value       = var.enable_secret_rotation ? aws_lambda_function.secret_rotation[0].arn : null
}

output "secret_rotation_lambda_name" {
  description = "Name of the secret rotation Lambda function (if enabled)"
  value       = var.enable_secret_rotation ? aws_lambda_function.secret_rotation[0].function_name : null
}

output "secret_rotation_role_arn" {
  description = "ARN of the secret rotation Lambda execution role (if enabled)"
  value       = var.enable_secret_rotation ? aws_iam_role.secret_rotation_role[0].arn : null
}

output "secret_rotation_role_name" {
  description = "Name of the secret rotation Lambda execution role (if enabled)"
  value       = var.enable_secret_rotation ? aws_iam_role.secret_rotation_role[0].name : null
}

output "cloudwatch_log_group_name" {
  description = "Name of the CloudWatch log group for notifications"
  value       = aws_cloudwatch_log_group.notifications.name
}

output "cloudwatch_log_group_arn" {
  description = "ARN of the CloudWatch log group for notifications"
  value       = aws_cloudwatch_log_group.notifications.arn
}

output "secret_version_id" {
  description = "Version ID of the Slack webhook secret (if secret value was provided)"
  value       = var.slack_webhook_url != "" ? aws_secretsmanager_secret_version.slack_webhook[0].version_id : null
  sensitive   = true
}

output "email_subscription_arns" {
  description = "ARNs of email subscriptions to SNS topic (if enabled and email addresses provided)"
  value       = var.enable_sns_notifications && length(var.notification_email_addresses) > 0 ? aws_sns_topic_subscription.email_notifications[*].arn : []
}