# Variables for ECS Module

variable "project_name" {
  description = "Name of the project, used for resource naming"
  type        = string
}

variable "aws_region" {
  description = "AWS region where resources are deployed"
  type        = string
}

variable "aws_account_id" {
  description = "AWS account ID"
  type        = string
}

# ECS Cluster Configuration
variable "cluster_name" {
  description = "Name of the ECS cluster"
  type        = string
}

variable "enable_container_insights" {
  description = "Enable CloudWatch Container Insights for the ECS cluster"
  type        = bool
  default     = true
}

# Fargate Configuration
variable "fargate_base_capacity" {
  description = "Base capacity for Fargate capacity provider"
  type        = number
  default     = 1
}

variable "fargate_weight" {
  description = "Weight for Fargate capacity provider"
  type        = number
  default     = 1
}

variable "enable_fargate_spot" {
  description = "Enable Fargate Spot capacity provider for cost optimization"
  type        = bool
  default     = true
}

variable "fargate_spot_base_capacity" {
  description = "Base capacity for Fargate Spot capacity provider"
  type        = number
  default     = 0
}

variable "fargate_spot_weight" {
  description = "Weight for Fargate Spot capacity provider"
  type        = number
  default     = 2
}

# Task Definition Configuration
variable "container_image" {
  description = "Docker image for the ECS task (e.g., ECR URI or Docker Hub image)"
  type        = string
}

variable "task_cpu" {
  description = "CPU units for the ECS task (256, 512, 1024, 2048, 4096)"
  type        = number
  default     = 2048

  validation {
    condition     = contains([256, 512, 1024, 2048, 4096], var.task_cpu)
    error_message = "Task CPU must be one of: 256, 512, 1024, 2048, 4096."
  }
}

variable "task_memory" {
  description = "Memory in MB for the ECS task"
  type        = number
  default     = 8192

  validation {
    condition     = var.task_memory >= 512 && var.task_memory <= 30720
    error_message = "Task memory must be between 512 MB and 30720 MB."
  }
}

variable "ephemeral_storage_size_gb" {
  description = "Ephemeral storage size in GB for the ECS task (20-200)"
  type        = number
  default     = 100

  validation {
    condition     = var.ephemeral_storage_size_gb >= 20 && var.ephemeral_storage_size_gb <= 200
    error_message = "Ephemeral storage size must be between 20 GB and 200 GB."
  }
}

variable "stop_timeout" {
  description = "Stop timeout in seconds for the container"
  type        = number
  default     = 120
}

# IAM Roles
variable "task_execution_role_arn" {
  description = "ARN of the IAM role for ECS task execution"
  type        = string
}

variable "task_role_arn" {
  description = "ARN of the IAM role for the ECS task (application permissions)"
  type        = string
}

# Network Configuration
variable "vpc_id" {
  description = "VPC ID where ECS tasks will run"
  type        = string
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs for ECS tasks"
  type        = list(string)
}

# Application Configuration
variable "s3_bucket_name" {
  description = "Name of the S3 bucket for storing Homebrew bottles"
  type        = string
}

variable "slack_webhook_secret_arn" {
  description = "ARN of the Secrets Manager secret containing Slack webhook URL"
  type        = string
}

variable "target_platforms" {
  description = "List of target macOS platforms for bottle downloads"
  type        = list(string)
  default     = ["arm64_sonoma", "arm64_ventura", "monterey"]
}

variable "size_threshold_gb" {
  description = "Size threshold in GB for routing between Lambda and ECS"
  type        = number
  default     = 20
}

variable "max_concurrent_downloads" {
  description = "Maximum number of concurrent downloads"
  type        = number
  default     = 10

  validation {
    condition     = var.max_concurrent_downloads >= 1 && var.max_concurrent_downloads <= 50
    error_message = "Max concurrent downloads must be between 1 and 50."
  }
}

variable "retry_attempts" {
  description = "Number of retry attempts for failed downloads"
  type        = number
  default     = 3

  validation {
    condition     = var.retry_attempts >= 0 && var.retry_attempts <= 10
    error_message = "Retry attempts must be between 0 and 10."
  }
}

variable "progress_report_interval" {
  description = "Progress report interval in seconds"
  type        = number
  default     = 300

  validation {
    condition     = var.progress_report_interval >= 60 && var.progress_report_interval <= 3600
    error_message = "Progress report interval must be between 60 and 3600 seconds."
  }
}

# EFS Configuration
variable "enable_efs" {
  description = "Enable EFS file system for temporary storage"
  type        = bool
  default     = true
}

variable "efs_performance_mode" {
  description = "EFS performance mode (generalPurpose or maxIO)"
  type        = string
  default     = "generalPurpose"

  validation {
    condition     = contains(["generalPurpose", "maxIO"], var.efs_performance_mode)
    error_message = "EFS performance mode must be either 'generalPurpose' or 'maxIO'."
  }
}

variable "efs_throughput_mode" {
  description = "EFS throughput mode (bursting or provisioned)"
  type        = string
  default     = "bursting"

  validation {
    condition     = contains(["bursting", "provisioned"], var.efs_throughput_mode)
    error_message = "EFS throughput mode must be either 'bursting' or 'provisioned'."
  }
}

variable "efs_provisioned_throughput" {
  description = "Provisioned throughput in MiB/s (only used if throughput_mode is provisioned)"
  type        = number
  default     = 100

  validation {
    condition     = var.efs_provisioned_throughput >= 1 && var.efs_provisioned_throughput <= 1024
    error_message = "EFS provisioned throughput must be between 1 and 1024 MiB/s."
  }
}

variable "efs_transition_to_ia" {
  description = "EFS lifecycle policy for transitioning to Infrequent Access"
  type        = string
  default     = "AFTER_30_DAYS"

  validation {
    condition = contains([
      "AFTER_7_DAYS", "AFTER_14_DAYS", "AFTER_30_DAYS",
      "AFTER_60_DAYS", "AFTER_90_DAYS"
    ], var.efs_transition_to_ia)
    error_message = "EFS transition to IA must be one of: AFTER_7_DAYS, AFTER_14_DAYS, AFTER_30_DAYS, AFTER_60_DAYS, AFTER_90_DAYS."
  }
}

# CloudWatch Configuration
variable "log_retention_days" {
  description = "Number of days to retain CloudWatch logs"
  type        = number
  default     = 14

  validation {
    condition = contains([
      1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653
    ], var.log_retention_days)
    error_message = "Log retention days must be a valid CloudWatch log retention period."
  }
}

variable "log_level" {
  description = "Log level for the ECS task (DEBUG, INFO, WARNING, ERROR)"
  type        = string
  default     = "INFO"

  validation {
    condition     = contains(["DEBUG", "INFO", "WARNING", "ERROR"], var.log_level)
    error_message = "Log level must be one of: DEBUG, INFO, WARNING, ERROR."
  }
}

# Monitoring and Alarms
variable "enable_cloudwatch_alarms" {
  description = "Enable CloudWatch alarms for ECS tasks"
  type        = bool
  default     = true
}

variable "alarm_sns_topic_arn" {
  description = "SNS topic ARN for CloudWatch alarm notifications"
  type        = string
  default     = ""
}

# Tags
variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}# 
External Hash File Configuration
variable "external_hash_file_s3_key" {
  description = "S3 key for external hash file to load on startup (optional)"
  type        = string
  default     = null
}

variable "external_hash_file_s3_bucket" {
  description = "S3 bucket name for external hash file (optional, defaults to main bucket)"
  type        = string
  default     = null
}

variable "external_hash_file_url" {
  description = "HTTPS URL for external hash file to load on startup (optional)"
  type        = string
  default     = null

  validation {
    condition = var.external_hash_file_url == null || can(regex("^https://", var.external_hash_file_url))
    error_message = "External hash file URL must be HTTPS."
  }
}