# Variables for Homebrew Bottles Sync System
# This file defines all configurable parameters for the infrastructure

# Project Configuration
variable "project_name" {
  description = "Name of the project, used for resource naming"
  type        = string
  default     = "homebrew-bottles-sync"

  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.project_name))
    error_message = "Project name must contain only lowercase letters, numbers, and hyphens."
  }
}

variable "environment" {
  description = "Environment name (e.g., dev, staging, prod)"
  type        = string
  default     = "prod"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod."
  }
}

variable "aws_region" {
  description = "AWS region for resource deployment"
  type        = string
  default     = "us-east-1"
}

variable "tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}

# Network Configuration
variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "List of availability zones to use"
  type        = list(string)
  default     = [] # Will use first 2 AZs in region if empty
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets"
  type        = list(string)
  default     = ["10.0.10.0/24", "10.0.20.0/24"]
}

variable "enable_nat_gateway" {
  description = "Whether to create NAT Gateways for private subnet internet access"
  type        = bool
  default     = true
}

# S3 Configuration
variable "s3_enable_versioning" {
  description = "Enable versioning on the S3 bucket"
  type        = bool
  default     = true
}

variable "s3_lifecycle_expiration_days" {
  description = "Number of days after which old bottle versions are deleted"
  type        = number
  default     = 90

  validation {
    condition     = var.s3_lifecycle_expiration_days > 0
    error_message = "Lifecycle expiration days must be greater than 0."
  }
}

variable "s3_noncurrent_version_expiration_days" {
  description = "Number of days after which noncurrent versions are deleted"
  type        = number
  default     = 30

  validation {
    condition     = var.s3_noncurrent_version_expiration_days > 0
    error_message = "Noncurrent version expiration days must be greater than 0."
  }
}

variable "s3_enable_access_logging" {
  description = "Enable S3 access logging"
  type        = bool
  default     = false
}

variable "s3_access_log_bucket" {
  description = "S3 bucket for storing access logs (required if s3_enable_access_logging is true)"
  type        = string
  default     = ""
}

variable "s3_kms_key_id" {
  description = "KMS key ID for S3 encryption (optional, uses AES256 if not provided)"
  type        = string
  default     = ""
}

# Lambda Configuration
variable "lambda_layer_zip_path" {
  description = "Path to the Lambda layer ZIP file containing shared dependencies"
  type        = string
  default     = "../lambda/layer.zip"
}

variable "lambda_layer_source_hash" {
  description = "Source code hash for the Lambda layer ZIP file"
  type        = string
  default     = ""
}

variable "lambda_orchestrator_zip_path" {
  description = "Path to the Lambda orchestrator ZIP file"
  type        = string
  default     = "../lambda/orchestrator.zip"
}

variable "lambda_orchestrator_source_hash" {
  description = "Source code hash for the Lambda orchestrator ZIP file"
  type        = string
  default     = ""
}

variable "lambda_sync_zip_path" {
  description = "Path to the Lambda sync worker ZIP file"
  type        = string
  default     = "../lambda/sync.zip"
}

variable "lambda_sync_source_hash" {
  description = "Source code hash for the Lambda sync worker ZIP file"
  type        = string
  default     = ""
}

variable "python_runtime" {
  description = "Python runtime version for Lambda functions"
  type        = string
  default     = "python3.11"
}

variable "lambda_orchestrator_timeout" {
  description = "Timeout in seconds for the orchestrator Lambda function"
  type        = number
  default     = 300 # 5 minutes
}

variable "lambda_orchestrator_memory_size" {
  description = "Memory size in MB for the orchestrator Lambda function"
  type        = number
  default     = 512
}

variable "lambda_sync_timeout" {
  description = "Timeout in seconds for the sync worker Lambda function"
  type        = number
  default     = 900 # 15 minutes (maximum for Lambda)
}

variable "lambda_sync_memory_size" {
  description = "Memory size in MB for the sync worker Lambda function"
  type        = number
  default     = 3008 # Maximum memory for better performance
}

variable "lambda_enable_dlq" {
  description = "Enable Dead Letter Queue for Lambda functions"
  type        = bool
  default     = true
}

variable "lambda_max_retry_attempts" {
  description = "Maximum retry attempts for Lambda function invocations"
  type        = number
  default     = 2
}

# ECS Configuration
variable "ecs_container_image" {
  description = "Docker image for the ECS task (e.g., ECR URI or Docker Hub image)"
  type        = string
  default     = "homebrew-bottles-sync:latest"
}

variable "ecs_enable_container_insights" {
  description = "Enable CloudWatch Container Insights for the ECS cluster"
  type        = bool
  default     = true
}

variable "ecs_fargate_base_capacity" {
  description = "Base capacity for Fargate capacity provider"
  type        = number
  default     = 1
}

variable "ecs_fargate_weight" {
  description = "Weight for Fargate capacity provider"
  type        = number
  default     = 1
}

variable "ecs_enable_fargate_spot" {
  description = "Enable Fargate Spot capacity provider for cost optimization"
  type        = bool
  default     = true
}

variable "ecs_fargate_spot_base_capacity" {
  description = "Base capacity for Fargate Spot capacity provider"
  type        = number
  default     = 0
}

variable "ecs_fargate_spot_weight" {
  description = "Weight for Fargate Spot capacity provider"
  type        = number
  default     = 2
}

variable "ecs_task_cpu" {
  description = "CPU units for the ECS task (256, 512, 1024, 2048, 4096)"
  type        = number
  default     = 2048

  validation {
    condition     = contains([256, 512, 1024, 2048, 4096], var.ecs_task_cpu)
    error_message = "Task CPU must be one of: 256, 512, 1024, 2048, 4096."
  }
}

variable "ecs_task_memory" {
  description = "Memory in MB for the ECS task"
  type        = number
  default     = 8192

  validation {
    condition     = var.ecs_task_memory >= 512 && var.ecs_task_memory <= 30720
    error_message = "Task memory must be between 512 MB and 30720 MB."
  }
}

variable "ecs_ephemeral_storage_size_gb" {
  description = "Ephemeral storage size in GB for the ECS task (20-200)"
  type        = number
  default     = 100

  validation {
    condition     = var.ecs_ephemeral_storage_size_gb >= 20 && var.ecs_ephemeral_storage_size_gb <= 200
    error_message = "Ephemeral storage size must be between 20 GB and 200 GB."
  }
}

variable "ecs_stop_timeout" {
  description = "Stop timeout in seconds for the container"
  type        = number
  default     = 120
}

variable "ecs_enable_efs" {
  description = "Enable EFS file system for temporary storage"
  type        = bool
  default     = true
}

variable "ecs_efs_performance_mode" {
  description = "EFS performance mode (generalPurpose or maxIO)"
  type        = string
  default     = "generalPurpose"

  validation {
    condition     = contains(["generalPurpose", "maxIO"], var.ecs_efs_performance_mode)
    error_message = "EFS performance mode must be either 'generalPurpose' or 'maxIO'."
  }
}

variable "ecs_efs_throughput_mode" {
  description = "EFS throughput mode (bursting or provisioned)"
  type        = string
  default     = "bursting"

  validation {
    condition     = contains(["bursting", "provisioned"], var.ecs_efs_throughput_mode)
    error_message = "EFS throughput mode must be either 'bursting' or 'provisioned'."
  }
}

variable "ecs_efs_provisioned_throughput" {
  description = "Provisioned throughput in MiB/s (only used if throughput_mode is provisioned)"
  type        = number
  default     = 100

  validation {
    condition     = var.ecs_efs_provisioned_throughput >= 1 && var.ecs_efs_provisioned_throughput <= 1024
    error_message = "EFS provisioned throughput must be between 1 and 1024 MiB/s."
  }
}

variable "ecs_efs_transition_to_ia" {
  description = "EFS lifecycle policy for transitioning to Infrequent Access"
  type        = string
  default     = "AFTER_30_DAYS"

  validation {
    condition = contains([
      "AFTER_7_DAYS", "AFTER_14_DAYS", "AFTER_30_DAYS",
      "AFTER_60_DAYS", "AFTER_90_DAYS"
    ], var.ecs_efs_transition_to_ia)
    error_message = "EFS transition to IA must be one of: AFTER_7_DAYS, AFTER_14_DAYS, AFTER_30_DAYS, AFTER_60_DAYS, AFTER_90_DAYS."
  }
}

# Application Configuration
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

# EventBridge Configuration
variable "schedule_expression" {
  description = "Schedule expression for the EventBridge rule (cron or rate)"
  type        = string
  default     = "cron(0 3 ? * SUN *)" # Sunday at 03:00 UTC

  validation {
    condition     = can(regex("^(cron|rate)\\(.*\\)$", var.schedule_expression))
    error_message = "Schedule expression must be a valid cron or rate expression."
  }
}

variable "eventbridge_rule_state" {
  description = "State of the EventBridge rule (ENABLED or DISABLED)"
  type        = string
  default     = "ENABLED"

  validation {
    condition     = contains(["ENABLED", "DISABLED"], var.eventbridge_rule_state)
    error_message = "Rule state must be either ENABLED or DISABLED."
  }
}

variable "eventbridge_max_retry_attempts" {
  description = "Maximum number of retry attempts for failed EventBridge invocations"
  type        = number
  default     = 3

  validation {
    condition     = var.eventbridge_max_retry_attempts >= 0 && var.eventbridge_max_retry_attempts <= 185
    error_message = "Maximum retry attempts must be between 0 and 185."
  }
}

variable "eventbridge_max_event_age_seconds" {
  description = "Maximum age of events in seconds before they are discarded"
  type        = number
  default     = 3600 # 1 hour

  validation {
    condition     = var.eventbridge_max_event_age_seconds >= 60 && var.eventbridge_max_event_age_seconds <= 86400
    error_message = "Maximum event age must be between 60 seconds and 86400 seconds (24 hours)."
  }
}

variable "eventbridge_enable_logging" {
  description = "Enable CloudWatch logging for EventBridge rule"
  type        = bool
  default     = false
}

variable "eventbridge_enable_failure_alarm" {
  description = "Enable CloudWatch alarm for EventBridge rule failures"
  type        = bool
  default     = true
}

variable "eventbridge_enable_missed_schedule_alarm" {
  description = "Enable CloudWatch alarm for missed scheduled executions"
  type        = bool
  default     = true
}

# Notifications Configuration
variable "slack_webhook_url" {
  description = "Slack webhook URL for notifications (optional, can be set later)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "slack_channel" {
  description = "Slack channel for notifications"
  type        = string
  default     = "#homebrew-sync"
}

variable "slack_username" {
  description = "Username for Slack bot notifications"
  type        = string
  default     = "Homebrew Sync Bot"
}

variable "secret_recovery_window_days" {
  description = "Number of days to retain deleted secrets for recovery"
  type        = number
  default     = 7

  validation {
    condition     = var.secret_recovery_window_days >= 7 && var.secret_recovery_window_days <= 30
    error_message = "Secret recovery window must be between 7 and 30 days."
  }
}

variable "enable_secret_rotation" {
  description = "Enable automatic rotation of Slack webhook secret"
  type        = bool
  default     = false
}

variable "secret_rotation_days" {
  description = "Number of days between automatic secret rotations"
  type        = number
  default     = 90

  validation {
    condition     = var.secret_rotation_days >= 30 && var.secret_rotation_days <= 365
    error_message = "Secret rotation days must be between 30 and 365."
  }
}

variable "enable_sns_notifications" {
  description = "Enable SNS topic for additional notifications"
  type        = bool
  default     = false
}

variable "notification_email_addresses" {
  description = "List of email addresses to subscribe to SNS notifications"
  type        = list(string)
  default     = []

  validation {
    condition = alltrue([
      for email in var.notification_email_addresses : can(regex("^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$", email))
    ])
    error_message = "All email addresses must be valid email format."
  }
}

variable "notifications_kms_key_id" {
  description = "KMS key ID for encrypting secrets (optional, uses default AWS managed key if not provided)"
  type        = string
  default     = ""
}

variable "enable_cross_region_backup" {
  description = "Enable cross-region backup for secrets"
  type        = bool
  default     = false
}

variable "backup_region" {
  description = "AWS region for cross-region secret backup"
  type        = string
  default     = ""
}

# Logging and Monitoring Configuration
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
  description = "Log level for Lambda functions and ECS tasks (DEBUG, INFO, WARNING, ERROR)"
  type        = string
  default     = "INFO"

  validation {
    condition     = contains(["DEBUG", "INFO", "WARNING", "ERROR"], var.log_level)
    error_message = "Log level must be one of: DEBUG, INFO, WARNING, ERROR."
  }
}

variable "enable_cloudwatch_alarms" {
  description = "Enable CloudWatch alarms for monitoring"
  type        = bool
  default     = true
}

variable "monitoring_alert_email" {
  description = "Email address for monitoring alarm notifications"
  type        = string
  default     = ""
}

variable "monitoring_ecs_service_name" {
  description = "Name of the ECS service for monitoring"
  type        = string
  default     = "homebrew-sync-service"
}# Exte
rnal Hash File Configuration
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

# Environment Isolation Configuration
variable "github_repository" {
  description = "GitHub repository for OIDC trust relationship (format: org/repo)"
  type        = string
  default     = ""
}

variable "dev_aws_account_id" {
  description = "AWS Account ID for development environment (optional for multi-account setup)"
  type        = string
  default     = ""
}

variable "staging_aws_account_id" {
  description = "AWS Account ID for staging environment (optional for multi-account setup)"
  type        = string
  default     = ""
}

variable "prod_aws_account_id" {
  description = "AWS Account ID for production environment (optional for multi-account setup)"
  type        = string
  default     = ""
}

variable "enable_multi_account_isolation" {
  description = "Enable multi-account isolation features"
  type        = bool
  default     = false
}

variable "enable_cross_environment_isolation" {
  description = "Enable policies that prevent cross-environment access"
  type        = bool
  default     = true
}

variable "enforce_resource_tagging" {
  description = "Enforce consistent resource tagging"
  type        = bool
  default     = true
}