# Development Environment Configuration
# This configuration deploys the Homebrew Bottles Sync System to the development environment
# with cost-optimized settings and development-specific configurations

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
  # This should be configured per environment
  backend "s3" {
    # These values should be set via backend config file or CLI
    # bucket = "your-terraform-state-bucket-dev"
    # key    = "homebrew-bottles-sync/dev/terraform.tfstate"
    # region = "us-west-2"
    # encrypt = true
    # dynamodb_table = "terraform-state-lock-dev"
  }
}

# Configure the AWS Provider
provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = "dev"
      ManagedBy   = "terraform"
      Repository  = "homebrew-bottles-sync"
      CostCenter  = "development"
      AutoShutdown = var.auto_shutdown ? "enabled" : "disabled"
    }
  }
}

# Use the main module with development-specific overrides
module "homebrew_sync" {
  source = "../../"

  # Project configuration
  project_name = var.project_name
  environment  = "dev"
  aws_region   = var.aws_region

  # Development-specific resource optimization
  # Use smaller resources for cost optimization
  lambda_orchestrator_memory_size = var.lambda_orchestrator_memory
  lambda_sync_memory_size         = var.lambda_sync_memory
  lambda_orchestrator_timeout     = var.lambda_timeout
  lambda_sync_timeout             = var.lambda_timeout

  # ECS configuration optimized for development
  ecs_task_cpu                   = var.ecs_task_cpu
  ecs_task_memory                = var.ecs_task_memory
  ecs_ephemeral_storage_size_gb  = var.ecs_ephemeral_storage
  enable_fargate_spot            = var.enable_fargate_spot
  ecs_fargate_spot_weight        = 3  # Prefer spot instances for cost savings
  ecs_fargate_weight             = 1

  # Application configuration
  size_threshold_gb        = var.size_threshold_gb
  schedule_expression      = var.schedule_expression
  max_concurrent_downloads = 5  # Lower concurrency for dev
  retry_attempts          = 2   # Fewer retries for faster feedback

  # Network configuration - smaller subnets for dev
  vpc_cidr                = "10.1.0.0/16"
  public_subnet_cidrs     = ["10.1.1.0/24", "10.1.2.0/24"]
  private_subnet_cidrs    = ["10.1.10.0/24", "10.1.20.0/24"]

  # Notifications configuration
  slack_webhook_url               = var.slack_webhook_url
  slack_channel                   = var.slack_channel
  enable_sns_notifications        = var.email_enabled
  notification_email_addresses   = var.email_addresses

  # Monitoring and logging - reduced retention for cost savings
  log_retention_days              = 7   # Shorter retention for dev
  enable_cloudwatch_alarms        = true
  monitoring_alert_email          = length(var.email_addresses) > 0 ? var.email_addresses[0] : ""

  # Cost optimization settings
  s3_lifecycle_expiration_days           = 30  # Shorter lifecycle for dev
  s3_noncurrent_version_expiration_days  = 7   # Clean up old versions quickly

  # Security settings - can be relaxed for development
  enable_vpc_flow_logs    = var.enable_vpc_flow_logs
  enable_cloudtrail       = var.enable_cloudtrail
  encryption_at_rest      = var.encryption_at_rest
  encryption_in_transit   = var.encryption_in_transit

  # Development-specific tags
  tags = {
    Environment     = "dev"
    CostOptimized   = "true"
    AutoShutdown    = var.auto_shutdown ? "enabled" : "disabled"
    Owner          = "development-team"
    Purpose        = "development-testing"
  }
}

# Environment isolation module
module "environment_isolation" {
  source = "../../modules/environment-isolation"
  
  project_name      = var.project_name
  environment       = "dev"
  github_repository = var.github_repository
  
  # Multi-account configuration (optional)
  dev_aws_account_id     = var.dev_aws_account_id
  staging_aws_account_id = var.staging_aws_account_id
  prod_aws_account_id    = var.prod_aws_account_id
  
  enable_cross_environment_isolation = true
  enforce_resource_tagging          = true
  enable_multi_account_isolation    = var.enable_multi_account_isolation
  
  # Allowed regions for development
  allowed_regions = ["us-west-2", "us-east-1"]
  
  tags = {
    Environment = "dev"
    Project     = var.project_name
    ManagedBy   = "terraform"
    Purpose     = "environment-isolation"
    CostCenter  = "development"
  }
}

# Development-specific resources
# Auto-shutdown Lambda function for cost optimization
resource "aws_lambda_function" "auto_shutdown" {
  count = var.auto_shutdown ? 1 : 0

  filename         = "${path.module}/auto_shutdown.zip"
  function_name    = "${var.project_name}-dev-auto-shutdown"
  role            = aws_iam_role.auto_shutdown[0].arn
  handler         = "index.handler"
  runtime         = "python3.11"
  timeout         = 300

  environment {
    variables = {
      ECS_CLUSTER_NAME = module.homebrew_sync.ecs_cluster_name
      ENVIRONMENT      = "dev"
    }
  }

  tags = {
    Environment = "dev"
    Purpose     = "cost-optimization"
  }
}

# IAM role for auto-shutdown function
resource "aws_iam_role" "auto_shutdown" {
  count = var.auto_shutdown ? 1 : 0

  name = "${var.project_name}-dev-auto-shutdown-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Environment = "dev"
    Purpose     = "cost-optimization"
  }
}

# IAM policy for auto-shutdown function
resource "aws_iam_role_policy" "auto_shutdown" {
  count = var.auto_shutdown ? 1 : 0

  name = "${var.project_name}-dev-auto-shutdown-policy"
  role = aws_iam_role.auto_shutdown[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "ecs:UpdateService",
          "ecs:DescribeServices",
          "ecs:DescribeClusters"
        ]
        Resource = [
          module.homebrew_sync.ecs_cluster_arn,
          "${module.homebrew_sync.ecs_cluster_arn}/*"
        ]
      }
    ]
  })
}

# EventBridge rule for auto-shutdown (evening shutdown)
resource "aws_cloudwatch_event_rule" "auto_shutdown" {
  count = var.auto_shutdown ? 1 : 0

  name                = "${var.project_name}-dev-auto-shutdown"
  description         = "Trigger auto-shutdown for development environment"
  schedule_expression = var.dev_shutdown_schedule

  tags = {
    Environment = "dev"
    Purpose     = "cost-optimization"
  }
}

# EventBridge rule for auto-startup (morning startup)
resource "aws_cloudwatch_event_rule" "auto_startup" {
  count = var.auto_shutdown ? 1 : 0

  name                = "${var.project_name}-dev-auto-startup"
  description         = "Trigger auto-startup for development environment"
  schedule_expression = var.dev_startup_schedule

  tags = {
    Environment = "dev"
    Purpose     = "cost-optimization"
  }
}

# EventBridge targets for auto-shutdown/startup
resource "aws_cloudwatch_event_target" "auto_shutdown" {
  count = var.auto_shutdown ? 1 : 0

  rule      = aws_cloudwatch_event_rule.auto_shutdown[0].name
  target_id = "AutoShutdownTarget"
  arn       = aws_lambda_function.auto_shutdown[0].arn

  input = jsonencode({
    action = "shutdown"
  })
}

resource "aws_cloudwatch_event_target" "auto_startup" {
  count = var.auto_shutdown ? 1 : 0

  rule      = aws_cloudwatch_event_rule.auto_startup[0].name
  target_id = "AutoStartupTarget"
  arn       = aws_lambda_function.auto_shutdown[0].arn

  input = jsonencode({
    action = "startup"
  })
}

# Lambda permissions for EventBridge
resource "aws_lambda_permission" "allow_eventbridge_shutdown" {
  count = var.auto_shutdown ? 1 : 0

  statement_id  = "AllowExecutionFromEventBridgeShutdown"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.auto_shutdown[0].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.auto_shutdown[0].arn
}

resource "aws_lambda_permission" "allow_eventbridge_startup" {
  count = var.auto_shutdown ? 1 : 0

  statement_id  = "AllowExecutionFromEventBridgeStartup"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.auto_shutdown[0].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.auto_startup[0].arn
}

# Cost monitoring alarm
resource "aws_cloudwatch_metric_alarm" "cost_threshold" {
  count = var.enable_cost_alerts ? 1 : 0

  alarm_name          = "${var.project_name}-dev-cost-threshold"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "EstimatedCharges"
  namespace           = "AWS/Billing"
  period              = "86400"  # 24 hours
  statistic           = "Maximum"
  threshold           = var.cost_threshold_usd
  alarm_description   = "This metric monitors estimated charges for development environment"
  alarm_actions       = var.email_enabled ? [module.homebrew_sync.sns_topic_arn] : []

  dimensions = {
    Currency = "USD"
  }

  tags = {
    Environment = "dev"
    Purpose     = "cost-monitoring"
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