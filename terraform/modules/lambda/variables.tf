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

# Lambda Layer Configuration
variable "lambda_layer_zip_path" {
  description = "Path to the Lambda layer ZIP file containing shared dependencies"
  type        = string
}

variable "lambda_layer_source_hash" {
  description = "Source code hash for the Lambda layer ZIP file"
  type        = string
}

# Lambda Function ZIP Files
variable "lambda_orchestrator_zip_path" {
  description = "Path to the Lambda orchestrator ZIP file"
  type        = string
}

variable "lambda_orchestrator_source_hash" {
  description = "Source code hash for the Lambda orchestrator ZIP file"
  type        = string
}

variable "lambda_sync_zip_path" {
  description = "Path to the Lambda sync worker ZIP file"
  type        = string
}

variable "lambda_sync_source_hash" {
  description = "Source code hash for the Lambda sync worker ZIP file"
  type        = string
}

# IAM Roles
variable "lambda_orchestrator_role_arn" {
  description = "ARN of the IAM role for the Lambda orchestrator function"
  type        = string
}

variable "lambda_sync_role_arn" {
  description = "ARN of the IAM role for the Lambda sync worker function"
  type        = string
}

# Runtime Configuration
variable "python_runtime" {
  description = "Python runtime version for Lambda functions"
  type        = string
  default     = "python3.11"
}

# Lambda Function Configuration
variable "orchestrator_timeout" {
  description = "Timeout in seconds for the orchestrator Lambda function"
  type        = number
  default     = 300 # 5 minutes
}

variable "orchestrator_memory_size" {
  description = "Memory size in MB for the orchestrator Lambda function"
  type        = number
  default     = 512
}

variable "sync_timeout" {
  description = "Timeout in seconds for the sync worker Lambda function"
  type        = number
  default     = 900 # 15 minutes (maximum for Lambda)
}

variable "sync_memory_size" {
  description = "Memory size in MB for the sync worker Lambda function"
  type        = number
  default     = 3008 # Maximum memory for better performance
}

# Environment Configuration
variable "s3_bucket_name" {
  description = "Name of the S3 bucket for storing Homebrew bottles"
  type        = string
}

variable "slack_webhook_secret_name" {
  description = "Name of the Secrets Manager secret containing Slack webhook URL"
  type        = string
}

variable "size_threshold_gb" {
  description = "Size threshold in GB for routing between Lambda and ECS"
  type        = number
  default     = 20
}

variable "ecs_cluster_name" {
  description = "Name of the ECS cluster for large downloads"
  type        = string
}

variable "ecs_task_definition_name" {
  description = "Name of the ECS task definition for sync worker"
  type        = string
}

variable "ecs_subnets" {
  description = "List of subnet IDs for ECS tasks"
  type        = list(string)
}

variable "ecs_security_groups" {
  description = "List of security group IDs for ECS tasks"
  type        = list(string)
}

variable "eventbridge_rule_arn" {
  description = "ARN of the EventBridge rule that triggers the orchestrator"
  type        = string
}

# CloudWatch Configuration
variable "log_retention_days" {
  description = "Number of days to retain CloudWatch logs"
  type        = number
  default     = 14
}

variable "log_level" {
  description = "Log level for Lambda functions (DEBUG, INFO, WARNING, ERROR)"
  type        = string
  default     = "INFO"

  validation {
    condition     = contains(["DEBUG", "INFO", "WARNING", "ERROR"], var.log_level)
    error_message = "Log level must be one of: DEBUG, INFO, WARNING, ERROR."
  }
}

# Dead Letter Queue Configuration
variable "enable_dlq" {
  description = "Enable Dead Letter Queue for Lambda functions"
  type        = bool
  default     = true
}

variable "lambda_max_retry_attempts" {
  description = "Maximum retry attempts for Lambda function invocations"
  type        = number
  default     = 2
}

# Tags
variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}# Ex
ternal Hash File Configuration
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