# Variables for GitHub OIDC module

variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "homebrew-bottles-sync"
}

variable "github_repository" {
  description = "GitHub repository in format 'owner/repo'"
  type        = string
  validation {
    condition     = can(regex("^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$", var.github_repository))
    error_message = "GitHub repository must be in format 'owner/repo'."
  }
}

variable "create_oidc_provider" {
  description = "Whether to create the OIDC provider (set to false if it already exists)"
  type        = bool
  default     = true
}

variable "existing_oidc_provider_arn" {
  description = "ARN of existing OIDC provider (required if create_oidc_provider is false)"
  type        = string
  default     = ""
}

variable "environments" {
  description = "Configuration for each environment"
  type = map(object({
    aws_region             = string
    branch_pattern         = string
    additional_permissions = list(object({
      Effect    = string
      Action    = list(string)
      Resource  = list(string)
      Condition = optional(map(any))
    }))
  }))
  default = {
    dev = {
      aws_region     = "us-west-2"
      branch_pattern = "develop"
      additional_permissions = []
    }
    staging = {
      aws_region     = "us-east-1"
      branch_pattern = "main"
      additional_permissions = []
    }
    prod = {
      aws_region     = "us-east-1"
      branch_pattern = "main"
      additional_permissions = []
    }
  }
}

variable "terraform_state_bucket" {
  description = "S3 bucket for Terraform state"
  type        = string
}

variable "terraform_lock_table" {
  description = "DynamoDB table for Terraform state locking"
  type        = string
}

variable "max_session_duration" {
  description = "Maximum session duration for the IAM role (in seconds)"
  type        = number
  default     = 3600
  validation {
    condition     = var.max_session_duration >= 3600 && var.max_session_duration <= 43200
    error_message = "Max session duration must be between 3600 (1 hour) and 43200 (12 hours) seconds."
  }
}

variable "enable_permission_boundary" {
  description = "Whether to apply permission boundary to GitHub Actions roles"
  type        = bool
  default     = true
}

variable "additional_trusted_repos" {
  description = "Additional GitHub repositories that can assume these roles"
  type        = list(string)
  default     = []
}

variable "enable_cross_account_access" {
  description = "Whether to enable cross-account access for the roles"
  type        = bool
  default     = false
}

variable "trusted_aws_accounts" {
  description = "List of AWS account IDs that can assume these roles (if cross-account access is enabled)"
  type        = list(string)
  default     = []
}