# Outputs for Staging Environment
# These outputs provide information specific to the staging environment

# Main module outputs
output "s3_bucket_name" {
  description = "Name of the S3 bucket"
  value       = module.homebrew_sync.s3_bucket_name
}

output "lambda_orchestrator_function_name" {
  description = "Name of the orchestrator Lambda function"
  value       = module.homebrew_sync.lambda_orchestrator_function_name
}

output "lambda_sync_function_name" {
  description = "Name of the sync Lambda function"
  value       = module.homebrew_sync.lambda_sync_function_name
}

output "ecs_cluster_name" {
  description = "Name of the ECS cluster"
  value       = module.homebrew_sync.ecs_cluster_name
}

output "vpc_id" {
  description = "ID of the VPC"
  value       = module.homebrew_sync.vpc_id
}

# Staging-specific outputs
output "dashboard_url" {
  description = "URL of the CloudWatch dashboard"
  value       = "https://${var.aws_region}.console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${aws_cloudwatch_dashboard.staging_dashboard.dashboard_name}"
}

output "error_alarm_name" {
  description = "Name of the error rate alarm"
  value       = aws_cloudwatch_metric_alarm.staging_error_rate.alarm_name
}

output "duration_alarm_name" {
  description = "Name of the duration alarm"
  value       = aws_cloudwatch_metric_alarm.staging_duration.alarm_name
}

output "cost_monitoring_enabled" {
  description = "Whether cost monitoring is enabled"
  value       = var.enable_cost_alerts
}

output "environment_config" {
  description = "Staging environment configuration summary"
  value = {
    environment           = "staging"
    aws_region           = var.aws_region
    size_threshold_gb    = var.size_threshold_gb
    schedule_expression  = var.schedule_expression
    auto_shutdown        = var.auto_shutdown
    cost_threshold_usd   = var.cost_threshold_usd
    fargate_spot_enabled = var.enable_fargate_spot
  }
}

# Resource configuration summary
output "resource_configuration" {
  description = "Resource configuration settings for staging"
  value = {
    lambda_orchestrator_memory = var.lambda_orchestrator_memory
    lambda_sync_memory        = var.lambda_sync_memory
    ecs_task_cpu             = var.ecs_task_cpu
    ecs_task_memory          = var.ecs_task_memory
    ecs_ephemeral_storage    = var.ecs_ephemeral_storage
    fargate_spot_enabled     = var.enable_fargate_spot
    log_retention_days       = 14
  }
}

# Monitoring configuration
output "monitoring_config" {
  description = "Monitoring configuration for staging"
  value = {
    dashboard_name       = aws_cloudwatch_dashboard.staging_dashboard.dashboard_name
    error_alarm_enabled  = true
    duration_alarm_enabled = true
    cost_alerts_enabled  = var.enable_cost_alerts
  }
}

# Environment isolation outputs
output "github_actions_role_arn" {
  description = "ARN of the GitHub Actions IAM role for this environment"
  value       = module.environment_isolation.github_actions_role_arn
}

output "environment_isolation_config" {
  description = "Environment isolation configuration"
  value       = module.environment_isolation.environment_isolation_config
}