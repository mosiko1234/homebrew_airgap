# Outputs for ECS Module

# ECS Cluster Outputs
output "cluster_name" {
  description = "Name of the ECS cluster"
  value       = aws_ecs_cluster.homebrew_sync.name
}

output "cluster_arn" {
  description = "ARN of the ECS cluster"
  value       = aws_ecs_cluster.homebrew_sync.arn
}

output "cluster_id" {
  description = "ID of the ECS cluster"
  value       = aws_ecs_cluster.homebrew_sync.id
}

# Task Definition Outputs
output "task_definition_arn" {
  description = "ARN of the ECS task definition"
  value       = aws_ecs_task_definition.sync_worker.arn
}

output "task_definition_family" {
  description = "Family name of the ECS task definition"
  value       = aws_ecs_task_definition.sync_worker.family
}

output "task_definition_revision" {
  description = "Revision of the ECS task definition"
  value       = aws_ecs_task_definition.sync_worker.revision
}

# Security Group Outputs
output "ecs_security_group_id" {
  description = "ID of the security group for ECS tasks"
  value       = aws_security_group.ecs_tasks.id
}

output "ecs_security_group_arn" {
  description = "ARN of the security group for ECS tasks"
  value       = aws_security_group.ecs_tasks.arn
}

output "efs_security_group_id" {
  description = "ID of the security group for EFS (if enabled)"
  value       = var.enable_efs ? aws_security_group.efs[0].id : null
}

output "efs_security_group_arn" {
  description = "ARN of the security group for EFS (if enabled)"
  value       = var.enable_efs ? aws_security_group.efs[0].arn : null
}

# EFS Outputs
output "efs_file_system_id" {
  description = "ID of the EFS file system (if enabled)"
  value       = var.enable_efs ? aws_efs_file_system.homebrew_sync[0].id : null
}

output "efs_file_system_arn" {
  description = "ARN of the EFS file system (if enabled)"
  value       = var.enable_efs ? aws_efs_file_system.homebrew_sync[0].arn : null
}

output "efs_file_system_dns_name" {
  description = "DNS name of the EFS file system (if enabled)"
  value       = var.enable_efs ? aws_efs_file_system.homebrew_sync[0].dns_name : null
}

output "efs_access_point_id" {
  description = "ID of the EFS access point (if enabled)"
  value       = var.enable_efs ? aws_efs_access_point.homebrew_sync[0].id : null
}

output "efs_access_point_arn" {
  description = "ARN of the EFS access point (if enabled)"
  value       = var.enable_efs ? aws_efs_access_point.homebrew_sync[0].arn : null
}

# CloudWatch Outputs
output "log_group_name" {
  description = "Name of the CloudWatch log group for ECS tasks"
  value       = aws_cloudwatch_log_group.ecs_sync_logs.name
}

output "log_group_arn" {
  description = "ARN of the CloudWatch log group for ECS tasks"
  value       = aws_cloudwatch_log_group.ecs_sync_logs.arn
}

# CloudWatch Alarms Outputs
output "cpu_alarm_name" {
  description = "Name of the CPU utilization alarm (if enabled)"
  value       = var.enable_cloudwatch_alarms ? aws_cloudwatch_metric_alarm.task_cpu_high[0].alarm_name : null
}

output "cpu_alarm_arn" {
  description = "ARN of the CPU utilization alarm (if enabled)"
  value       = var.enable_cloudwatch_alarms ? aws_cloudwatch_metric_alarm.task_cpu_high[0].arn : null
}

output "memory_alarm_name" {
  description = "Name of the memory utilization alarm (if enabled)"
  value       = var.enable_cloudwatch_alarms ? aws_cloudwatch_metric_alarm.task_memory_high[0].alarm_name : null
}

output "memory_alarm_arn" {
  description = "ARN of the memory utilization alarm (if enabled)"
  value       = var.enable_cloudwatch_alarms ? aws_cloudwatch_metric_alarm.task_memory_high[0].arn : null
}

# Task Configuration Outputs (for reference by other modules)
output "task_cpu" {
  description = "CPU units allocated to the ECS task"
  value       = var.task_cpu
}

output "task_memory" {
  description = "Memory in MB allocated to the ECS task"
  value       = var.task_memory
}

output "ephemeral_storage_size_gb" {
  description = "Ephemeral storage size in GB for the ECS task"
  value       = var.ephemeral_storage_size_gb
}

# Network Configuration Outputs
output "private_subnet_ids" {
  description = "List of private subnet IDs used by ECS tasks"
  value       = var.private_subnet_ids
}

output "vpc_id" {
  description = "VPC ID where ECS tasks run"
  value       = var.vpc_id
}

# Application Configuration Outputs
output "target_platforms" {
  description = "List of target macOS platforms"
  value       = var.target_platforms
}

output "max_concurrent_downloads" {
  description = "Maximum number of concurrent downloads"
  value       = var.max_concurrent_downloads
}

output "size_threshold_gb" {
  description = "Size threshold in GB for routing between Lambda and ECS"
  value       = var.size_threshold_gb
}