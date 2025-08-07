# Variables for Environment Isolation Module

variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod."
  }
}

variable "github_repository" {
  description = "GitHub repository for OIDC trust relationship (format: org/repo)"
  type        = string
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

variable "allowed_aws_accounts" {
  description = "List of AWS account IDs allowed to assume roles"
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
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

variable "allowed_regions" {
  description = "List of AWS regions allowed for this environment"
  type        = list(string)
  default     = []
}