# Main Terraform configuration for Homebrew Bottles Sync System
# This configuration combines all modules to deploy the complete infrastructure

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
}

# Configure the AWS Provider
provider "aws" {
  region = var.aws_region

  default_tags {
    tags = local.common_tags
  }
}

# Data sources for AWS account information
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}
data "aws_availability_zones" "available" {
  state = "available"
}

# Local values for common configuration
locals {
  aws_account_id = data.aws_caller_identity.current.account_id
  aws_region     = data.aws_region.current.name

  common_tags = merge(var.tags, {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
    Repository  = "homebrew-bottles-sync"
  })

  # Generate unique bucket name with account ID to avoid conflicts
  bucket_name = "${var.project_name}-${var.environment}-${local.aws_account_id}"

  # ECS cluster and task definition names
  ecs_cluster_name         = "${var.project_name}-${var.environment}-cluster"
  ecs_task_definition_name = "${var.project_name}-${var.environment}-sync-worker"

  # Lambda function names
  lambda_orchestrator_name = "${var.project_name}-${var.environment}-orchestrator"
  lambda_sync_name         = "${var.project_name}-${var.environment}-sync-worker"

  # Secrets Manager secret name
  slack_webhook_secret_name = "${var.project_name}-${var.environment}-slack-webhook"

  # Use provided availability zones or default to first 2 in region
  availability_zones = length(var.availability_zones) > 0 ? var.availability_zones : slice(data.aws_availability_zones.available.names, 0, 2)
}

# Network Module - VPC, subnets, security groups
module "network" {
  source = "./modules/network"

  project_name         = var.project_name
  environment          = var.environment
  vpc_cidr             = var.vpc_cidr
  availability_zones   = local.availability_zones
  public_subnet_cidrs  = var.public_subnet_cidrs
  private_subnet_cidrs = var.private_subnet_cidrs
  enable_nat_gateway   = var.enable_nat_gateway
}

# S3 Module - Storage for Homebrew bottles
module "s3" {
  source = "./modules/s3"

  bucket_name                        = local.bucket_name
  environment                        = var.environment
  enable_versioning                  = var.s3_enable_versioning
  lifecycle_expiration_days          = var.s3_lifecycle_expiration_days
  noncurrent_version_expiration_days = var.s3_noncurrent_version_expiration_days
  enable_access_logging              = var.s3_enable_access_logging
  access_log_bucket                  = var.s3_access_log_bucket
  kms_key_id                         = var.s3_kms_key_id
  tags                               = local.common_tags

  # Will be populated after IAM module creates roles
  lambda_role_arns = [
    module.iam.lambda_orchestrator_role_arn,
    module.iam.lambda_sync_role_arn
  ]
  ecs_role_arns = [
    module.iam.ecs_task_role_arn
  ]
}

# Notifications Module - Slack integration and SNS
module "notifications" {
  source = "./modules/notifications"

  project_name                 = var.project_name
  environment                  = var.environment
  slack_webhook_url            = var.slack_webhook_url
  slack_channel                = var.slack_channel
  slack_username               = var.slack_username
  secret_recovery_window_days  = var.secret_recovery_window_days
  enable_secret_rotation       = var.enable_secret_rotation
  secret_rotation_days         = var.secret_rotation_days
  enable_sns_notifications     = var.enable_sns_notifications
  notification_email_addresses = var.notification_email_addresses
  log_retention_days           = var.log_retention_days
  kms_key_id                   = var.notifications_kms_key_id
  enable_cross_region_backup   = var.enable_cross_region_backup
  backup_region                = var.backup_region
  tags                         = local.common_tags

  # Will be populated after IAM module creates roles
  lambda_role_arns = [
    module.iam.lambda_orchestrator_role_arn,
    module.iam.lambda_sync_role_arn
  ]
  ecs_role_arns = [
    module.iam.ecs_task_role_arn
  ]
}

# IAM Module - Roles and policies for Lambda and ECS
module "iam" {
  source = "./modules/iam"

  project_name             = var.project_name
  aws_region               = local.aws_region
  aws_account_id           = local.aws_account_id
  s3_bucket_arn            = module.s3.bucket_arn
  slack_webhook_secret_arn = module.notifications.slack_webhook_secret_arn
  ecs_cluster_name         = local.ecs_cluster_name
  tags                     = local.common_tags
}

# ECS Module - Fargate cluster and task definition for large downloads
module "ecs" {
  source = "./modules/ecs"

  project_name               = var.project_name
  aws_region                 = local.aws_region
  aws_account_id             = local.aws_account_id
  cluster_name               = local.ecs_cluster_name
  enable_container_insights  = var.ecs_enable_container_insights
  fargate_base_capacity      = var.ecs_fargate_base_capacity
  fargate_weight             = var.ecs_fargate_weight
  enable_fargate_spot        = var.ecs_enable_fargate_spot
  fargate_spot_base_capacity = var.ecs_fargate_spot_base_capacity
  fargate_spot_weight        = var.ecs_fargate_spot_weight
  container_image            = var.ecs_container_image
  task_cpu                   = var.ecs_task_cpu
  task_memory                = var.ecs_task_memory
  ephemeral_storage_size_gb  = var.ecs_ephemeral_storage_size_gb
  stop_timeout               = var.ecs_stop_timeout
  task_execution_role_arn    = module.iam.ecs_task_execution_role_arn
  task_role_arn              = module.iam.ecs_task_role_arn
  vpc_id                     = module.network.vpc_id
  private_subnet_ids         = module.network.private_subnet_ids
  s3_bucket_name             = module.s3.bucket_name
  slack_webhook_secret_arn   = module.notifications.slack_webhook_secret_arn
  target_platforms           = var.target_platforms
  size_threshold_gb          = var.size_threshold_gb
  max_concurrent_downloads   = var.max_concurrent_downloads
  retry_attempts             = var.retry_attempts
  progress_report_interval   = var.progress_report_interval
  enable_efs                 = var.ecs_enable_efs
  efs_performance_mode       = var.ecs_efs_performance_mode
  efs_throughput_mode        = var.ecs_efs_throughput_mode
  efs_provisioned_throughput = var.ecs_efs_provisioned_throughput
  efs_transition_to_ia       = var.ecs_efs_transition_to_ia
  log_retention_days         = var.log_retention_days
  log_level                  = var.log_level
  enable_cloudwatch_alarms   = var.enable_cloudwatch_alarms
  alarm_sns_topic_arn        = var.enable_sns_notifications ? module.notifications.sns_topic_arn : ""
  external_hash_file_s3_key    = var.external_hash_file_s3_key
  external_hash_file_s3_bucket = var.external_hash_file_s3_bucket
  external_hash_file_url       = var.external_hash_file_url
  tags                       = local.common_tags
}

# Lambda Module - Orchestrator and sync worker functions
module "lambda" {
  source = "./modules/lambda"

  project_name                    = var.project_name
  aws_region                      = local.aws_region
  aws_account_id                  = local.aws_account_id
  lambda_layer_zip_path           = var.lambda_layer_zip_path
  lambda_layer_source_hash        = var.lambda_layer_source_hash
  lambda_orchestrator_zip_path    = var.lambda_orchestrator_zip_path
  lambda_orchestrator_source_hash = var.lambda_orchestrator_source_hash
  lambda_sync_zip_path            = var.lambda_sync_zip_path
  lambda_sync_source_hash         = var.lambda_sync_source_hash
  lambda_orchestrator_role_arn    = module.iam.lambda_orchestrator_role_arn
  lambda_sync_role_arn            = module.iam.lambda_sync_role_arn
  python_runtime                  = var.python_runtime
  orchestrator_timeout            = var.lambda_orchestrator_timeout
  orchestrator_memory_size        = var.lambda_orchestrator_memory_size
  sync_timeout                    = var.lambda_sync_timeout
  sync_memory_size                = var.lambda_sync_memory_size
  s3_bucket_name                  = module.s3.bucket_name
  slack_webhook_secret_name       = module.notifications.slack_webhook_secret_name
  size_threshold_gb               = var.size_threshold_gb
  ecs_cluster_name                = module.ecs.cluster_name
  ecs_task_definition_name        = module.ecs.task_definition_family
  ecs_subnets                     = module.network.private_subnet_ids
  ecs_security_groups             = [module.ecs.ecs_security_group_id]
  eventbridge_rule_arn            = module.eventbridge.eventbridge_rule_arn
  log_retention_days              = var.log_retention_days
  log_level                       = var.log_level
  enable_dlq                      = var.lambda_enable_dlq
  lambda_max_retry_attempts       = var.lambda_max_retry_attempts
  external_hash_file_s3_key       = var.external_hash_file_s3_key
  external_hash_file_s3_bucket    = var.external_hash_file_s3_bucket
  external_hash_file_url          = var.external_hash_file_url
  tags                            = local.common_tags
}

# EventBridge Module - Scheduled triggers for sync operations
module "eventbridge" {
  source = "./modules/eventbridge"

  project_name                 = var.project_name
  schedule_expression          = var.schedule_expression
  rule_state                   = var.eventbridge_rule_state
  lambda_orchestrator_arn      = module.lambda.lambda_orchestrator_function_arn
  max_retry_attempts           = var.eventbridge_max_retry_attempts
  max_event_age_seconds        = var.eventbridge_max_event_age_seconds
  dlq_arn                      = var.lambda_enable_dlq ? module.lambda.lambda_dlq_arn : null
  enable_logging               = var.eventbridge_enable_logging
  log_retention_days           = var.log_retention_days
  enable_failure_alarm         = var.eventbridge_enable_failure_alarm
  enable_missed_schedule_alarm = var.eventbridge_enable_missed_schedule_alarm
  alarm_actions                = var.enable_sns_notifications ? [module.notifications.sns_topic_arn] : []
  tags                         = local.common_tags
}

# Monitoring Module - CloudWatch dashboards, alarms, and insights
module "monitoring" {
  source = "./modules/monitoring"

  project_name               = var.project_name
  aws_region                 = local.aws_region
  orchestrator_function_name = module.lambda.lambda_orchestrator_function_name
  sync_worker_function_name  = module.lambda.lambda_sync_function_name
  ecs_cluster_name           = module.ecs.cluster_name
  ecs_service_name           = var.monitoring_ecs_service_name
  log_retention_days         = var.log_retention_days
  alert_email                = var.monitoring_alert_email
  slack_webhook_url          = var.slack_webhook_url
  tags                       = local.common_tags
}