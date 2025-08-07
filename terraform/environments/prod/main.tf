# Production Environment Configuration
# This configuration deploys the Homebrew Bottles Sync System to the production environment
# with high availability, security, and performance optimizations

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
    # bucket = "your-terraform-state-bucket-prod"
    # key    = "homebrew-bottles-sync/prod/terraform.tfstate"
    # region = "us-east-1"
    # encrypt = true
    # dynamodb_table = "terraform-state-lock-prod"
  }
}

# Configure the AWS Provider
provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = "prod"
      ManagedBy   = "terraform"
      Repository  = "homebrew-bottles-sync"
      CostCenter  = "production"
      Purpose     = "production-workload"
      Criticality = "high"
    }
  }
}

# Use the main module with production-specific configuration
module "homebrew_sync" {
  source = "../../"

  # Project configuration
  project_name = var.project_name
  environment  = "prod"
  aws_region   = var.aws_region

  # Production resource configuration - optimized for performance and reliability
  lambda_orchestrator_memory_size = var.lambda_orchestrator_memory
  lambda_sync_memory_size         = var.lambda_sync_memory
  lambda_orchestrator_timeout     = var.lambda_timeout
  lambda_sync_timeout             = var.lambda_timeout

  # ECS configuration for production - no spot instances for reliability
  ecs_task_cpu                   = var.ecs_task_cpu
  ecs_task_memory                = var.ecs_task_memory
  ecs_ephemeral_storage_size_gb  = var.ecs_ephemeral_storage
  enable_fargate_spot            = var.enable_fargate_spot
  ecs_fargate_spot_weight        = 0  # No spot instances in production
  ecs_fargate_weight             = 1  # Only on-demand instances

  # Application configuration
  size_threshold_gb        = var.size_threshold_gb
  schedule_expression      = var.schedule_expression
  max_concurrent_downloads = 10  # Higher concurrency for production
  retry_attempts          = 3    # Standard retry attempts

  # Network configuration - production subnets
  vpc_cidr                = "10.0.0.0/16"
  public_subnet_cidrs     = ["10.0.1.0/24", "10.0.2.0/24"]
  private_subnet_cidrs    = ["10.0.10.0/24", "10.0.20.0/24"]

  # Notifications configuration
  slack_webhook_url               = var.slack_webhook_url
  slack_channel                   = var.slack_channel
  enable_sns_notifications        = var.email_enabled
  notification_email_addresses   = var.email_addresses

  # Monitoring and logging - extended retention for production
  log_retention_days              = 30  # Extended retention for production
  enable_cloudwatch_alarms        = true
  monitoring_alert_email          = length(var.email_addresses) > 0 ? var.email_addresses[0] : ""

  # Lifecycle management - longer retention for production
  s3_lifecycle_expiration_days           = 90  # Longer lifecycle for production
  s3_noncurrent_version_expiration_days  = 30  # Keep old versions longer

  # Security settings - maximum security for production
  enable_vpc_flow_logs    = var.enable_vpc_flow_logs
  enable_cloudtrail       = var.enable_cloudtrail
  encryption_at_rest      = var.encryption_at_rest
  encryption_in_transit   = var.encryption_in_transit

  # Production-specific tags
  tags = {
    Environment     = "prod"
    Purpose        = "production-workload"
    Owner          = "platform-team"
    Criticality    = "high"
    BackupRequired = "true"
    MonitoringLevel = "enhanced"
  }
}

# Production-specific monitoring and alerting
resource "aws_cloudwatch_metric_alarm" "prod_error_rate" {
  alarm_name          = "${var.project_name}-prod-error-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Sum"
  threshold           = "3"  # Lower threshold for production
  alarm_description   = "This metric monitors Lambda error rate in production"
  alarm_actions       = var.email_enabled ? [module.homebrew_sync.sns_topic_arn] : []
  ok_actions          = var.email_enabled ? [module.homebrew_sync.sns_topic_arn] : []

  dimensions = {
    FunctionName = module.homebrew_sync.lambda_orchestrator_function_name
  }

  tags = {
    Environment = "prod"
    Purpose     = "error-monitoring"
    Criticality = "high"
  }
}

# Production duration monitoring
resource "aws_cloudwatch_metric_alarm" "prod_duration" {
  alarm_name          = "${var.project_name}-prod-duration"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Average"
  threshold           = "180000"  # 3 minutes - stricter for production
  alarm_description   = "This metric monitors Lambda duration in production"
  alarm_actions       = var.email_enabled ? [module.homebrew_sync.sns_topic_arn] : []

  dimensions = {
    FunctionName = module.homebrew_sync.lambda_orchestrator_function_name
  }

  tags = {
    Environment = "prod"
    Purpose     = "performance-monitoring"
    Criticality = "high"
  }
}

# Production availability monitoring
resource "aws_cloudwatch_metric_alarm" "prod_availability" {
  alarm_name          = "${var.project_name}-prod-availability"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Invocations"
  namespace           = "AWS/Lambda"
  period              = "3600"  # 1 hour
  statistic           = "Sum"
  threshold           = "1"
  alarm_description   = "This metric monitors if the system is running as expected"
  alarm_actions       = var.email_enabled ? [module.homebrew_sync.sns_topic_arn] : []
  treat_missing_data  = "breaching"

  dimensions = {
    FunctionName = module.homebrew_sync.lambda_orchestrator_function_name
  }

  tags = {
    Environment = "prod"
    Purpose     = "availability-monitoring"
    Criticality = "high"
  }
}

# Cost monitoring for production
resource "aws_cloudwatch_metric_alarm" "prod_cost_threshold" {
  count = var.enable_cost_alerts ? 1 : 0

  alarm_name          = "${var.project_name}-prod-cost-threshold"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "EstimatedCharges"
  namespace           = "AWS/Billing"
  period              = "86400"  # 24 hours
  statistic           = "Maximum"
  threshold           = var.cost_threshold_usd
  alarm_description   = "This metric monitors estimated charges for production environment"
  alarm_actions       = var.email_enabled ? [module.homebrew_sync.sns_topic_arn] : []

  dimensions = {
    Currency = "USD"
  }

  tags = {
    Environment = "prod"
    Purpose     = "cost-monitoring"
    Criticality = "medium"
  }
}

# Production CloudWatch dashboard with comprehensive metrics
resource "aws_cloudwatch_dashboard" "prod_dashboard" {
  dashboard_name = "${var.project_name}-prod-dashboard"

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
            [".", "Duration", ".", "."],
            [".", "Throttles", ".", "."]
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
            ["AWS/Lambda", "Invocations", "FunctionName", module.homebrew_sync.lambda_sync_function_name],
            [".", "Errors", ".", "."],
            [".", "Duration", ".", "."]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "Lambda Sync Worker Metrics"
          period  = 300
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 12
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/ECS", "CPUUtilization", "ServiceName", "homebrew-sync-service", "ClusterName", module.homebrew_sync.ecs_cluster_name],
            [".", "MemoryUtilization", ".", ".", ".", "."],
            [".", "RunningTaskCount", ".", ".", ".", "."]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "ECS Cluster Metrics"
          period  = 300
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 18
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/S3", "BucketSizeBytes", "BucketName", module.homebrew_sync.s3_bucket_name, "StorageType", "StandardStorage"],
            [".", "NumberOfObjects", ".", ".", ".", "AllStorageTypes"]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "S3 Storage Metrics"
          period  = 86400
        }
      }
    ]
  })

  tags = {
    Environment = "prod"
    Purpose     = "monitoring"
    Criticality = "high"
  }
}

# Production backup configuration
resource "aws_backup_vault" "prod_backup" {
  count = var.enable_backup ? 1 : 0

  name        = "${var.project_name}-prod-backup-vault"
  kms_key_arn = var.backup_kms_key_arn

  tags = {
    Environment = "prod"
    Purpose     = "backup"
    Criticality = "high"
  }
}

# Environment isolation module
module "environment_isolation" {
  source = "../../modules/environment-isolation"
  
  project_name      = var.project_name
  environment       = "prod"
  github_repository = var.github_repository
  
  # Multi-account configuration (optional)
  dev_aws_account_id     = var.dev_aws_account_id
  staging_aws_account_id = var.staging_aws_account_id
  prod_aws_account_id    = var.prod_aws_account_id
  
  enable_cross_environment_isolation = true
  enforce_resource_tagging          = true
  enable_multi_account_isolation    = var.enable_multi_account_isolation
  
  # Allowed regions for production
  allowed_regions = ["us-east-1"]
  
  tags = {
    Environment = "prod"
    Project     = var.project_name
    ManagedBy   = "terraform"
    Purpose     = "environment-isolation"
    CostCenter  = "production"
    Criticality = "high"
  }
}

# Production backup plan
resource "aws_backup_plan" "prod_backup" {
  count = var.enable_backup ? 1 : 0

  name = "${var.project_name}-prod-backup-plan"

  rule {
    rule_name         = "daily_backup"
    target_vault_name = aws_backup_vault.prod_backup[0].name
    schedule          = "cron(0 5 ? * * *)"  # Daily at 5 AM

    lifecycle {
      cold_storage_after = 30
      delete_after       = 120
    }

    recovery_point_tags = {
      Environment = "prod"
      Purpose     = "backup"
    }
  }

  tags = {
    Environment = "prod"
    Purpose     = "backup"
    Criticality = "high"
  }
}# Out
put environment isolation information
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