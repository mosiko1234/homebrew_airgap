# Outputs for Development Environment
# These outputs provide information specific to the development environment

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

# Development-specific outputs
output "auto_shutdown_enabled" {
  description = "Whether auto-shutdown is enabled"
  value       = var.auto_shutdown
}

output "auto_shutdown_function_name" {
  description = "Name of the auto-shutdown Lambda function"
  value       = var.auto_shutdown ? aws_lambda_function.auto_shutdown[0].function_name : null
}

output "cost_monitoring_enabled" {
  description = "Whether cost monitoring is enabled"
  value       = var.enable_cost_alerts
}

output "environment_config" {
  description = "Development environment configuration summary"
  value = {
    environment           = "dev"
    aws_region           = var.aws_region
    size_threshold_gb    = var.size_threshold_gb
    schedule_expression  = var.schedule_expression
    auto_shutdown        = var.auto_shutdown
    cost_threshold_usd   = var.cost_threshold_usd
    fargate_spot_enabled = var.enable_fargate_spot
  }
}

# Resource optimization summary
output "resource_optimization" {
  description = "Resource optimization settings for development"
  value = {
    lambda_orchestrator_memory = var.lambda_orchestrator_memory
    lambda_sync_memory        = var.lambda_sync_memory
    ecs_task_cpu             = var.ecs_task_cpu
    ecs_task_memory          = var.ecs_task_memory
    ecs_ephemeral_storage    = var.ecs_ephemeral_storage
    fargate_spot_enabled     = var.enable_fargate_spot
    log_retention_days       = 7
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