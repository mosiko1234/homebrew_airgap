# Variables for Notifications Module

variable "project_name" {
  description = "Name of the project (used for resource naming)"
  type        = string
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

variable "lambda_role_arns" {
  description = "List of Lambda execution role ARNs that need access to secrets and SNS"
  type        = list(string)
  default     = []
}

variable "ecs_role_arns" {
  description = "List of ECS task role ARNs that need access to secrets and SNS"
  type        = list(string)
  default     = []
}

variable "log_retention_days" {
  description = "Number of days to retain CloudWatch logs"
  type        = number
  default     = 30
  validation {
    condition     = contains([1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653], var.log_retention_days)
    error_message = "Log retention days must be a valid CloudWatch log retention value."
  }
}

variable "tags" {
  description = "Additional tags to apply to resources"
  type        = map(string)
  default     = {}
}

variable "kms_key_id" {
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