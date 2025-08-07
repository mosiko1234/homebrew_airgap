# Variables for Production Environment
# This file defines variables specific to the production environment

# Project Configuration
variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "homebrew-bottles-sync"
}

variable "aws_region" {
  description = "AWS region for production environment"
  type        = string
  default     = "us-east-1"
}

# Environment-specific application configuration
variable "size_threshold_gb" {
  description = "Size threshold in GB for routing between Lambda and ECS"
  type        = number
  default     = 20
}

variable "schedule_expression" {
  description = "Schedule expression for the EventBridge rule"
  type        = string
  default     = "cron(0 3 ? * SUN *)"  # Sunday at 3 AM for production
}

variable "enable_fargate_spot" {
  description = "Enable Fargate Spot for cost optimization"
  type        = bool
  default     = false  # Disabled for production reliability
}

# Resource configuration for production - optimized for performance
variable "lambda_orchestrator_memory" {
  description = "Memory size in MB for orchestrator Lambda"
  type        = number
  default     = 512
}

variable "lambda_sync_memory" {
  description = "Memory size in MB for sync Lambda"
  type        = number
  default     = 3008
}

variable "lambda_timeout" {
  description = "Timeout in seconds for Lambda functions"
  type        = number
  default     = 900
}

variable "ecs_task_cpu" {
  description = "CPU units for ECS task"
  type        = number
  default     = 2048
}

variable "ecs_task_memory" {
  description = "Memory in MB for ECS task"
  type        = number
  default     = 8192
}

variable "ecs_ephemeral_storage" {
  description = "Ephemeral storage in GB for ECS task"
  type        = number
  default     = 100
}

# Notification configuration
variable "slack_enabled" {
  description = "Enable Slack notifications"
  type        = bool
  default     = true
}

variable "slack_channel" {
  description = "Slack channel for notifications"
  type        = string
  default     = "#platform-updates"
}

variable "slack_webhook_url" {
  description = "Slack webhook URL"
  type        = string
  default     = ""
  sensitive   = true
}

variable "email_enabled" {
  description = "Enable email notifications"
  type        = bool
  default     = true
}

variable "email_addresses" {
  description = "List of email addresses for notifications"
  type        = list(string)
  default     = ["devops@company.com"]
}

# Cost optimization settings
variable "auto_shutdown" {
  description = "Enable automatic shutdown for cost optimization"
  type        = bool
  default     = false  # Always disabled for production
}

variable "cost_threshold_usd" {
  description = "Cost threshold in USD for alerts"
  type        = number
  default     = 100
}

variable "enable_cost_alerts" {
  description = "Enable cost monitoring alerts"
  type        = bool
  default     = true
}

# Security settings - maximum security for production
variable "enable_vpc_flow_logs" {
  description = "Enable VPC flow logs"
  type        = bool
  default     = true
}

variable "enable_cloudtrail" {
  description = "Enable CloudTrail logging"
  type        = bool
  default     = true
}

variable "encryption_at_rest" {
  description = "Enable encryption at rest"
  type        = bool
  default     = true
}

variable "encryption_in_transit" {
  description = "Enable encryption in transit"
  type        = bool
  default     = true
}

# Environment isolation settings
variable "github_repository" {
  description = "GitHub repository for OIDC trust relationship"
  type        = string
  default     = "your-org/homebrew-bottles-sync"
}

variable "allowed_aws_accounts" {
  description = "List of AWS account IDs allowed to assume roles"
  type        = list(string)
  default     = []
}

variable "cross_account_access_enabled" {
  description = "Enable cross-account access for shared resources"
  type        = bool
  default     = false
}

# Backup configuration
variable "enable_backup" {
  description = "Enable AWS Backup for production resources"
  type        = bool
  default     = true
}

variable "backup_kms_key_arn" {
  description = "KMS key ARN for backup encryption"
  type        = string
  default     = ""
}