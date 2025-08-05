# Variables for S3 Module

variable "bucket_name" {
  description = "Name of the S3 bucket for storing Homebrew bottles"
  type        = string
  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]*[a-z0-9]$", var.bucket_name))
    error_message = "Bucket name must be lowercase, contain only letters, numbers, and hyphens, and not start or end with a hyphen."
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

variable "lambda_role_arns" {
  description = "List of Lambda execution role ARNs that need access to the bucket"
  type        = list(string)
  default     = []
}

variable "ecs_role_arns" {
  description = "List of ECS task role ARNs that need access to the bucket"
  type        = list(string)
  default     = []
}

variable "enable_versioning" {
  description = "Enable versioning on the S3 bucket"
  type        = bool
  default     = true
}

variable "lifecycle_expiration_days" {
  description = "Number of days after which old bottle versions are deleted"
  type        = number
  default     = 90
  validation {
    condition     = var.lifecycle_expiration_days > 0
    error_message = "Lifecycle expiration days must be greater than 0."
  }
}

variable "noncurrent_version_expiration_days" {
  description = "Number of days after which noncurrent versions are deleted"
  type        = number
  default     = 30
  validation {
    condition     = var.noncurrent_version_expiration_days > 0
    error_message = "Noncurrent version expiration days must be greater than 0."
  }
}

variable "enable_access_logging" {
  description = "Enable S3 access logging"
  type        = bool
  default     = false
}

variable "access_log_bucket" {
  description = "S3 bucket for storing access logs (required if enable_access_logging is true)"
  type        = string
  default     = ""
}

variable "kms_key_id" {
  description = "KMS key ID for S3 encryption (optional, uses AES256 if not provided)"
  type        = string
  default     = ""
}

variable "tags" {
  description = "Additional tags to apply to resources"
  type        = map(string)
  default     = {}
}