# Staging Environment Configuration
# This configuration deploys the Homebrew Bottles Sync System to the staging environment
# with production-like settings for testing and validation

terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.0"
    }
  }

  # Backend configuration for state management
  backend "s3" {
    # These values should be set via backend config file or CLI
    # bucket = "your-terraform-state-bucket-staging"
    # key    = "homebrew-bottles-sync/staging/terraform.tfstate"
    # region = "us-east-1"
    # encrypt = true
    # dynamodb_table = "terraform-state-lock-staging"
  }
}

# Configure the AWS Provider
provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = "staging"
      ManagedBy   = "terraform"
      Repository  = "homebrew-bottles-sync"
      CostCenter  = "staging"
      Purpose     = "pre-production-testing"
    }
  }
}

# Use the main module with staging-specific configuration
module "homebrew_sync" {
  source = "../../"

  # Project configuration
  project_name = var.project_name
  environment  = "staging"
  aws_region   = var.aws_region

  # Staging resource configuration - balanced between cost and performance
  lambda_orchestrator_memory_size = var.lambda_orchestrator_memory
  lambda_sync_memory_size         = var.lambda_sync_memory
  lambda_orchestrator_timeout     = var.lambda_timeout
  lambda_sync_timeout             = var.lambda_timeout

  # ECS configuration for staging
  ecs_task_cpu                   = var.ecs_task_cpu
  ecs_task_memory                = var.ecs_task_memory
  ecs_ephemeral_storage_size_gb  = var.ecs_ephemeral_storage
  enable_fargate_spot            = var.enable_fargate_spot
  ecs_fargate_spot_weight        = 2  # Balanced spot/on-demand for staging
  ecs_fargate_weight             = 1

  # Application configuration
  size_threshold_gb        = var.size_threshold_gb
  schedule_expression      = var.schedule_expression
  max_concurrent_downloads = 8   # Moderate concurrency for staging
  retry_attempts          = 3    # Standard retry attempts

  # Network configuration - production-like subnets
  vpc_cidr                = "10.2.0.0/16"
  public_subnet_cidrs     = ["10.2.1.0/24", "10.2.2.0/24"]
  private_subnet_cidrs    = ["10.2.10.0/24", "10.2.20.0/24"]

  # Notifications configuration
  slack_webhook_url               = var.slack_webhook_url
  slack_channel                   = var.slack_channel
  enable_sns_notifications        = var.email_enabled
  notification_email_addresses   = var.email_addresses

  # Monitoring and logging - moderate retention
  log_retention_days              = 14  # Standard retention for staging
  enable_cloudwatch_alarms        = true
  monitoring_alert_email          = length(var.email_addresses) > 0 ? var.email_addresses[0] : ""

  # Lifecycle management - moderate retention
  s3_lifecycle_expiration_days           = 60  # Moderate lifecycle for staging
  s3_noncurrent_version_expiration_days  = 14  # Clean up old versions

  # Security settings - production-like security
  enable_vpc_flow_logs    = var.enable_vpc_flow_logs
  enable_cloudtrail       = var.enable_cloudtrail
  encryption_at_rest      = var.encryption_at_rest
  encryption_in_transit   = var.encryption_in_transit

  # Staging-specific tags
  tags = {
    Environment     = "staging"
    Purpose        = "pre-production-testing"
    Owner          = "platform-team"
    TestingPhase   = "integration"
  }
}

# Environment isolation module
module "environment_isolation" {
  source = "../../modules/environment-isolation"
  
  project_name      = var.project_name
  environment       = "staging"
  github_repository = var.github_repository
  
  # Multi-account configuration (optional)
  dev_aws_account_id     = var.dev_aws_account_id
  staging_aws_account_id = var.staging_aws_account_id
  prod_aws_account_id    = var.prod_aws_account_id
  
  enable_cross_environment_isolation = true
  enforce_resource_tagging          = true
  enable_multi_account_isolation    = var.enable_multi_account_isolation
  
  # Allowed regions for staging
  allowed_regions = ["us-east-1", "us-west-2"]
  
  tags = {
    Environment = "staging"
    Project     = var.project_name
    ManagedBy   = "terraform"
    Purpose     = "environment-isolation"
    CostCenter  = "staging"
  }
}

# Staging-specific monitoring and alerting
resource "aws_cloudwatch_metric_alarm" "staging_error_rate" {
  alarm_name          = "${var.project_name}-staging-error-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Sum"
  threshold           = "5"
  alarm_description   = "This metric monitors Lambda error rate in staging"
  alarm_actions       = var.email_enabled ? [module.homebrew_sync.sns_topic_arn] : []

  dimensions = {
    FunctionName = module.homebrew_sync.lambda_orchestrator_function_name
  }

  tags = {
    Environment = "staging"
    Purpose     = "error-monitoring"
  }
}

# Staging deployment validation
resource "aws_cloudwatch_metric_alarm" "staging_duration" {
  alarm_name          = "${var.project_name}-staging-duration"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Average"
  threshold           = "240000"  # 4 minutes
  alarm_description   = "This metric monitors Lambda duration in staging"
  alarm_actions       = var.email_enabled ? [module.homebrew_sync.sns_topic_arn] : []

  dimensions = {
    FunctionName = module.homebrew_sync.lambda_orchestrator_function_name
  }

  tags = {
    Environment = "staging"
    Purpose     = "performance-monitoring"
  }
}

# Cost monitoring for staging
resource "aws_cloudwatch_metric_alarm" "staging_cost_threshold" {
  count = var.enable_cost_alerts ? 1 : 0

  alarm_name          = "${var.project_name}-staging-cost-threshold"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "EstimatedCharges"
  namespace           = "AWS/Billing"
  period              = "86400"  # 24 hours
  statistic           = "Maximum"
  threshold           = var.cost_threshold_usd
  alarm_description   = "This metric monitors estimated charges for staging environment"
  alarm_actions       = var.email_enabled ? [module.homebrew_sync.sns_topic_arn] : []

  dimensions = {
    Currency = "USD"
  }

  tags = {
    Environment = "staging"
    Purpose     = "cost-monitoring"
  }
}

# Staging-specific CloudWatch dashboard
resource "aws_cloudwatch_dashboard" "staging_dashboard" {
  dashboard_name = "${var.project_name}-staging-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/Lambda", "Invocations", "FunctionName", module.homebrew_sync.lambda_orchestrator_function_name],
            [".", "Errors", ".", "."],
            [".", "Duration", ".", "."]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "Lambda Orchestrator Metrics"
          period  = 300
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/ECS", "CPUUtilization", "ServiceName", "homebrew-sync-service", "ClusterName", module.homebrew_sync.ecs_cluster_name],
            [".", "MemoryUtilization", ".", ".", ".", "."]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "ECS Cluster Metrics"
          period  = 300
        }
      }
    ]
  })

  tags = {
    Environment = "staging"
    Purpose     = "monitoring"
  }
}

# Output environment isolation information
output "environment_isolation_summary" {
  description = "Summary of environment isolation configuration"
  value       = module.environment_isolation.environment_isolation_config
}

output "github_actions_role_arn" {
  description = "ARN of the GitHub Actions IAM role for this environment"
  value       = module.environment_isolation.github_actions_role_arn
}

output "environment_tags" {
  description = "Standard tags applied to all resources in this environment"
  value       = module.environment_isolation.environment_tags
}

output "resource_naming_convention" {
  description = "Resource naming convention for this environment"
  value       = module.environment_isolation.resource_naming_convention
}