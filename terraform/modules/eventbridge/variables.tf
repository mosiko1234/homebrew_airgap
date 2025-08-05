variable "project_name" {
  description = "Name of the project, used for resource naming"
  type        = string
}

# EventBridge Rule Configuration
variable "schedule_expression" {
  description = "Schedule expression for the EventBridge rule (cron or rate)"
  type        = string
  default     = "cron(0 3 ? * SUN *)" # Sunday at 03:00 UTC

  validation {
    condition     = can(regex("^(cron|rate)\\(.*\\)$", var.schedule_expression))
    error_message = "Schedule expression must be a valid cron or rate expression."
  }
}

variable "rule_state" {
  description = "State of the EventBridge rule (ENABLED or DISABLED)"
  type        = string
  default     = "ENABLED"

  validation {
    condition     = contains(["ENABLED", "DISABLED"], var.rule_state)
    error_message = "Rule state must be either ENABLED or DISABLED."
  }
}

# Lambda Target Configuration
variable "lambda_orchestrator_arn" {
  description = "ARN of the Lambda orchestrator function to target"
  type        = string
}

# Retry and Error Handling Configuration
variable "max_retry_attempts" {
  description = "Maximum number of retry attempts for failed invocations"
  type        = number
  default     = 3

  validation {
    condition     = var.max_retry_attempts >= 0 && var.max_retry_attempts <= 185
    error_message = "Maximum retry attempts must be between 0 and 185."
  }
}

variable "max_event_age_seconds" {
  description = "Maximum age of events in seconds before they are discarded"
  type        = number
  default     = 3600 # 1 hour

  validation {
    condition     = var.max_event_age_seconds >= 60 && var.max_event_age_seconds <= 86400
    error_message = "Maximum event age must be between 60 seconds and 86400 seconds (24 hours)."
  }
}

variable "dlq_arn" {
  description = "ARN of the Dead Letter Queue for failed events (optional)"
  type        = string
  default     = null
}

# Logging Configuration
variable "enable_logging" {
  description = "Enable CloudWatch logging for EventBridge rule"
  type        = bool
  default     = false
}

variable "log_retention_days" {
  description = "Number of days to retain CloudWatch logs"
  type        = number
  default     = 14

  validation {
    condition = contains([
      1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653
    ], var.log_retention_days)
    error_message = "Log retention days must be a valid CloudWatch Logs retention period."
  }
}

variable "eventbridge_log_role_arn" {
  description = "ARN of the IAM role for EventBridge logging (required if enable_logging is true)"
  type        = string
  default     = null
}

# Monitoring and Alerting Configuration
variable "enable_failure_alarm" {
  description = "Enable CloudWatch alarm for EventBridge rule failures"
  type        = bool
  default     = true
}

variable "enable_missed_schedule_alarm" {
  description = "Enable CloudWatch alarm for missed scheduled executions"
  type        = bool
  default     = true
}

variable "alarm_actions" {
  description = "List of ARNs to notify when alarms trigger (e.g., SNS topic ARNs)"
  type        = list(string)
  default     = []
}

# Tags
variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}