# Variables for the monitoring module

variable "project_name" {
  description = "Name of the project for resource naming"
  type        = string
  default     = "homebrew-sync"
}

variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-east-1"
}

variable "orchestrator_function_name" {
  description = "Name of the Lambda orchestrator function"
  type        = string
}

variable "sync_worker_function_name" {
  description = "Name of the Lambda sync worker function"
  type        = string
}

variable "ecs_cluster_name" {
  description = "Name of the ECS cluster"
  type        = string
}

variable "ecs_service_name" {
  description = "Name of the ECS service"
  type        = string
  default     = "homebrew-sync-service"
}

variable "log_retention_days" {
  description = "Number of days to retain CloudWatch logs"
  type        = number
  default     = 30
}

variable "alert_email" {
  description = "Email address for alarm notifications"
  type        = string
  default     = ""
}

variable "slack_webhook_url" {
  description = "Slack webhook URL for alarm notifications"
  type        = string
  default     = ""
  sensitive   = true
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default = {
    Project     = "homebrew-sync"
    Environment = "production"
    ManagedBy   = "terraform"
  }
}