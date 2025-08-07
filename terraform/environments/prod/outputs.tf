# Outputs for Production Environment
# These outputs provide information specific to the production environment

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

# Production-specific outputs
output "dashboard_url" {
  description = "URL of the CloudWatch dashboard"
  value       = "https://${var.aws_region}.console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${aws_cloudwatch_dashboard.prod_dashboard.dashboard_name}"
}

output "error_alarm_name" {
  description = "Name of the error rate alarm"
  value       = aws_cloudwatch_metric_alarm.prod_error_rate.alarm_name
}

output "duration_alarm_name" {
  description = "Name of the duration alarm"
  value       = aws_cloudwatch_metric_alarm.prod_duration.alarm_name
}

output "availability_alarm_name" {
  description = "Name of the availability alarm"
  value       = aws_cloudwatch_metric_alarm.prod_availability.alarm_name
}

output "backup_vault_name" {
  description = "Name of the backup vault"
  value       = var.enable_backup ? aws_backup_vault.prod_backup[0].name : null
}

output "backup_plan_name" {
  description = "Name of the backup plan"
  value       = var.enable_backup ? aws_backup_plan.prod_backup[0].name : null
}

output "environment_config" {
  description = "Production environment configuration summary"
  value = {
    environment           = "prod"
    aws_region           = var.aws_region
    size_threshold_gb    = var.size_threshold_gb
    schedule_expression  = var.schedule_expression
    auto_shutdown        = var.auto_shutdown
    cost_threshold_usd   = var.cost_threshold_usd
    fargate_spot_enabled = var.enable_fargate_spot
    backup_enabled       = var.enable_backup
  }
}

# Resource configuration summary
output "resource_configuration" {
  description = "Resource configuration settings for production"
  value = {
    lambda_orchestrator_memory = var.lambda_orchestrator_memory
    lambda_sync_memory        = var.lambda_sync_memory
    ecs_task_cpu             = var.ecs_task_cpu
    ecs_task_memory          = var.ecs_task_memory
    ecs_ephemeral_storage    = var.ecs_ephemeral_storage
    fargate_spot_enabled     = var.enable_fargate_spot
    log_retention_days       = 30
  }
}

# Monitoring configuration
output "monitoring_config" {
  description = "Monitoring configuration for production"
  value = {
    dashboard_name         = aws_cloudwatch_dashboard.prod_dashboard.dashboard_name
    error_alarm_enabled    = true
    duration_alarm_enabled = true
    availability_alarm_enabled = true
    cost_alerts_enabled    = var.enable_cost_alerts
    backup_enabled         = var.enable_backup
  }
}

# Security configuration
output "security_config" {
  description = "Security configuration for production"
  value = {
    vpc_flow_logs_enabled     = var.enable_vpc_flow_logs
    cloudtrail_enabled        = var.enable_cloudtrail
    encryption_at_rest        = var.encryption_at_rest
    encryption_in_transit     = var.encryption_in_transit
    fargate_spot_disabled     = !var.enable_fargate_spot
    auto_shutdown_disabled    = !var.auto_shutdown
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