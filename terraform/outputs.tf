# Outputs for Homebrew Bottles Sync System
# These outputs provide important information about the deployed infrastructure

# S3 Storage Outputs
output "s3_bucket_name" {
  description = "Name of the S3 bucket storing Homebrew bottles"
  value       = module.s3.bucket_name
}

output "s3_bucket_arn" {
  description = "ARN of the S3 bucket storing Homebrew bottles"
  value       = module.s3.bucket_arn
}

output "s3_bucket_domain_name" {
  description = "Domain name of the S3 bucket"
  value       = module.s3.bucket_domain_name
}

# Lambda Function Outputs
output "lambda_orchestrator_function_name" {
  description = "Name of the Lambda orchestrator function"
  value       = module.lambda.lambda_orchestrator_function_name
}

output "lambda_orchestrator_function_arn" {
  description = "ARN of the Lambda orchestrator function"
  value       = module.lambda.lambda_orchestrator_function_arn
}

output "lambda_sync_function_name" {
  description = "Name of the Lambda sync worker function"
  value       = module.lambda.lambda_sync_function_name
}

output "lambda_sync_function_arn" {
  description = "ARN of the Lambda sync worker function"
  value       = module.lambda.lambda_sync_function_arn
}

# ECS Cluster Outputs
output "ecs_cluster_name" {
  description = "Name of the ECS cluster"
  value       = module.ecs.cluster_name
}

output "ecs_cluster_arn" {
  description = "ARN of the ECS cluster"
  value       = module.ecs.cluster_arn
}

output "ecs_task_definition_arn" {
  description = "ARN of the ECS task definition"
  value       = module.ecs.task_definition_arn
}

output "ecs_task_definition_family" {
  description = "Family name of the ECS task definition"
  value       = module.ecs.task_definition_family
}

# Network Outputs
output "vpc_id" {
  description = "ID of the VPC"
  value       = module.network.vpc_id
}

output "vpc_cidr_block" {
  description = "CIDR block of the VPC"
  value       = module.network.vpc_cidr_block
}

output "public_subnet_ids" {
  description = "IDs of the public subnets"
  value       = module.network.public_subnet_ids
}

output "private_subnet_ids" {
  description = "IDs of the private subnets"
  value       = module.network.private_subnet_ids
}

# EventBridge Outputs
output "eventbridge_rule_name" {
  description = "Name of the EventBridge rule"
  value       = module.eventbridge.eventbridge_rule_name
}

output "eventbridge_rule_arn" {
  description = "ARN of the EventBridge rule"
  value       = module.eventbridge.eventbridge_rule_arn
}

output "schedule_expression" {
  description = "Schedule expression used by the EventBridge rule"
  value       = module.eventbridge.schedule_expression
}

# Notifications Outputs
output "slack_webhook_secret_name" {
  description = "Name of the Slack webhook secret in Secrets Manager"
  value       = module.notifications.slack_webhook_secret_name
}

output "slack_webhook_secret_arn" {
  description = "ARN of the Slack webhook secret in Secrets Manager"
  value       = module.notifications.slack_webhook_secret_arn
}

output "sns_topic_arn" {
  description = "ARN of the SNS topic for notifications (if enabled)"
  value       = module.notifications.sns_topic_arn
}

# IAM Role Outputs
output "lambda_orchestrator_role_arn" {
  description = "ARN of the Lambda orchestrator IAM role"
  value       = module.iam.lambda_orchestrator_role_arn
}

output "lambda_sync_role_arn" {
  description = "ARN of the Lambda sync worker IAM role"
  value       = module.iam.lambda_sync_role_arn
}

output "ecs_task_execution_role_arn" {
  description = "ARN of the ECS task execution IAM role"
  value       = module.iam.ecs_task_execution_role_arn
}

output "ecs_task_role_arn" {
  description = "ARN of the ECS task IAM role"
  value       = module.iam.ecs_task_role_arn
}

# Monitoring Outputs
output "monitoring_dashboard_url" {
  description = "URL of the CloudWatch dashboard"
  value       = module.monitoring.dashboard_url
}

output "monitoring_sns_topic_arn" {
  description = "ARN of the SNS topic for monitoring alerts"
  value       = module.monitoring.sns_topic_arn
}

# EFS Outputs (if enabled)
output "efs_file_system_id" {
  description = "ID of the EFS file system (if enabled)"
  value       = module.ecs.efs_file_system_id
}

output "efs_file_system_dns_name" {
  description = "DNS name of the EFS file system (if enabled)"
  value       = module.ecs.efs_file_system_dns_name
}

# CloudWatch Log Groups
output "log_groups" {
  description = "CloudWatch log group information"
  value = {
    orchestrator  = module.lambda.orchestrator_log_group_name
    sync_worker   = module.lambda.sync_log_group_name
    ecs_sync      = module.ecs.log_group_name
    eventbridge   = module.eventbridge.log_group_name
    notifications = module.notifications.cloudwatch_log_group_name
  }
}

# Application Configuration Outputs
output "application_config" {
  description = "Application configuration summary"
  value = {
    target_platforms         = var.target_platforms
    size_threshold_gb        = var.size_threshold_gb
    max_concurrent_downloads = var.max_concurrent_downloads
    schedule_expression      = var.schedule_expression
    environment              = var.environment
    aws_region               = var.aws_region
  }
}

# Deployment Information
output "deployment_info" {
  description = "Information about the deployment"
  value = {
    project_name   = var.project_name
    environment    = var.environment
    aws_region     = var.aws_region
    aws_account_id = local.aws_account_id
    deployed_at    = timestamp()
  }
}