# Lambda Module

This Terraform module creates AWS Lambda functions for the Homebrew Bottles Sync System, including:

- Lambda Orchestrator function for coordinating sync operations
- Lambda Sync Worker function for downloading bottles under 20GB
- Lambda Layer with shared dependencies (boto3, requests, shared modules)
- CloudWatch Log Groups with configurable retention
- Dead Letter Queue for error handling (optional)

## Usage

```hcl
module "lambda" {
  source = "./modules/lambda"

  project_name                      = var.project_name
  aws_region                       = var.aws_region
  aws_account_id                   = data.aws_caller_identity.current.account_id
  
  # Lambda Layer and Function ZIP files
  lambda_layer_zip_path            = "lambda-layer.zip"
  lambda_layer_source_hash         = filebase64sha256("lambda-layer.zip")
  lambda_orchestrator_zip_path     = "lambda-orchestrator.zip"
  lambda_orchestrator_source_hash  = filebase64sha256("lambda-orchestrator.zip")
  lambda_sync_zip_path            = "lambda-sync.zip"
  lambda_sync_source_hash         = filebase64sha256("lambda-sync.zip")
  
  # IAM Roles (from IAM module)
  lambda_orchestrator_role_arn     = module.iam.lambda_orchestrator_role_arn
  lambda_sync_role_arn            = module.iam.lambda_sync_role_arn
  
  # Environment Configuration
  s3_bucket_name                  = module.s3.bucket_name
  slack_webhook_secret_name       = module.notifications.slack_webhook_secret_name
  size_threshold_gb               = 20
  
  # ECS Configuration
  ecs_cluster_name               = module.ecs.cluster_name
  ecs_task_definition_name       = module.ecs.task_definition_name
  ecs_subnets                    = module.network.private_subnet_ids
  ecs_security_groups            = [module.network.ecs_security_group_id]
  
  # EventBridge Configuration
  eventbridge_rule_arn           = module.eventbridge.rule_arn
  
  # Optional Configuration
  log_retention_days             = 14
  log_level                      = "INFO"
  enable_dlq                     = true
  
  tags = var.tags
}
```

## Building Lambda Packages

Before using this module, you need to build the Lambda layer and function packages:

### 1. Build Lambda Layer

The Lambda layer contains shared dependencies (boto3, requests) and shared modules:

```bash
# Run the build script
./terraform/modules/lambda/build_layer.sh

# This creates lambda-layer.zip in the lambda module directory
```

### 2. Package Lambda Functions

Create ZIP files for the Lambda functions:

```bash
# Package orchestrator function
cd lambda/orchestrator
zip -r ../../terraform/modules/lambda/lambda-orchestrator.zip . -x "__pycache__/*" "*.pyc"

# Package sync worker function
cd ../sync
zip -r ../../terraform/modules/lambda/lambda-sync.zip . -x "__pycache__/*" "*.pyc"
```

## Lambda Layer Contents

The Lambda layer includes:

- **boto3**: AWS SDK for Python
- **requests**: HTTP library for API calls
- **shared modules**: Common code shared between Lambda functions
  - `shared/models.py`: Data models and validation
  - `shared/homebrew_api.py`: Homebrew API client
  - `shared/s3_service.py`: S3 operations
  - `shared/notification_service.py`: Slack notifications

## Function Configuration

### Orchestrator Function

- **Runtime**: Python 3.11
- **Timeout**: 5 minutes (configurable)
- **Memory**: 512 MB (configurable)
- **Purpose**: Coordinate sync operations and route to Lambda or ECS

### Sync Worker Function

- **Runtime**: Python 3.11
- **Timeout**: 15 minutes (Lambda maximum)
- **Memory**: 3008 MB (maximum for better performance)
- **Purpose**: Download bottles under size threshold

## Environment Variables

The module configures the following environment variables for Lambda functions:

### Orchestrator Function

- `S3_BUCKET_NAME`: S3 bucket for storing bottles
- `SLACK_WEBHOOK_SECRET`: Secrets Manager secret name for Slack webhook
- `SIZE_THRESHOLD_GB`: Size threshold for routing decisions
- `AWS_REGION`: AWS region
- `ECS_CLUSTER_NAME`: ECS cluster name for large downloads
- `ECS_TASK_DEFINITION`: ECS task definition name
- `LAMBDA_SYNC_FUNCTION`: Name of sync worker function
- `ECS_SUBNETS`: Comma-separated list of subnet IDs
- `ECS_SECURITY_GROUPS`: Comma-separated list of security group IDs
- `LOG_LEVEL`: Logging level

### Sync Worker Function

- `S3_BUCKET_NAME`: S3 bucket for storing bottles
- `SLACK_WEBHOOK_SECRET_NAME`: Secrets Manager secret name
- `AWS_REGION`: AWS region
- `LOG_LEVEL`: Logging level

## CloudWatch Logs

The module creates CloudWatch Log Groups with configurable retention:

- `/aws/lambda/{project_name}-orchestrator`
- `/aws/lambda/{project_name}-sync`

Default retention: 14 days (configurable via `log_retention_days`)

## Dead Letter Queue

Optional SQS Dead Letter Queue for handling failed Lambda invocations:

- Enabled by default (`enable_dlq = true`)
- 14-day message retention
- Maximum 2 retry attempts (configurable)

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| project_name | Name of the project, used for resource naming | `string` | n/a | yes |
| aws_region | AWS region where resources are deployed | `string` | n/a | yes |
| aws_account_id | AWS account ID | `string` | n/a | yes |
| lambda_layer_zip_path | Path to the Lambda layer ZIP file | `string` | n/a | yes |
| lambda_layer_source_hash | Source code hash for the Lambda layer | `string` | n/a | yes |
| lambda_orchestrator_zip_path | Path to orchestrator ZIP file | `string` | n/a | yes |
| lambda_orchestrator_source_hash | Source hash for orchestrator | `string` | n/a | yes |
| lambda_sync_zip_path | Path to sync worker ZIP file | `string` | n/a | yes |
| lambda_sync_source_hash | Source hash for sync worker | `string` | n/a | yes |
| lambda_orchestrator_role_arn | IAM role ARN for orchestrator | `string` | n/a | yes |
| lambda_sync_role_arn | IAM role ARN for sync worker | `string` | n/a | yes |
| s3_bucket_name | S3 bucket name for bottles | `string` | n/a | yes |
| slack_webhook_secret_name | Secrets Manager secret name | `string` | n/a | yes |
| ecs_cluster_name | ECS cluster name | `string` | n/a | yes |
| ecs_task_definition_name | ECS task definition name | `string` | n/a | yes |
| ecs_subnets | List of subnet IDs for ECS | `list(string)` | n/a | yes |
| ecs_security_groups | List of security group IDs | `list(string)` | n/a | yes |
| eventbridge_rule_arn | EventBridge rule ARN | `string` | n/a | yes |
| python_runtime | Python runtime version | `string` | `"python3.11"` | no |
| orchestrator_timeout | Orchestrator timeout (seconds) | `number` | `300` | no |
| orchestrator_memory_size | Orchestrator memory (MB) | `number` | `512` | no |
| sync_timeout | Sync worker timeout (seconds) | `number` | `900` | no |
| sync_memory_size | Sync worker memory (MB) | `number` | `3008` | no |
| size_threshold_gb | Size threshold for routing | `number` | `20` | no |
| log_retention_days | CloudWatch log retention days | `number` | `14` | no |
| log_level | Log level (DEBUG/INFO/WARNING/ERROR) | `string` | `"INFO"` | no |
| enable_dlq | Enable Dead Letter Queue | `bool` | `true` | no |
| lambda_max_retry_attempts | Max retry attempts | `number` | `2` | no |
| tags | Tags to apply to resources | `map(string)` | `{}` | no |

## Outputs

| Name | Description |
|------|-------------|
| lambda_orchestrator_function_name | Name of orchestrator function |
| lambda_orchestrator_function_arn | ARN of orchestrator function |
| lambda_orchestrator_invoke_arn | Invoke ARN of orchestrator function |
| lambda_sync_function_name | Name of sync worker function |
| lambda_sync_function_arn | ARN of sync worker function |
| lambda_sync_invoke_arn | Invoke ARN of sync worker function |
| lambda_layer_arn | ARN of Lambda layer |
| lambda_layer_version | Version of Lambda layer |
| orchestrator_log_group_name | CloudWatch log group name (orchestrator) |
| orchestrator_log_group_arn | CloudWatch log group ARN (orchestrator) |
| sync_log_group_name | CloudWatch log group name (sync worker) |
| sync_log_group_arn | CloudWatch log group ARN (sync worker) |
| lambda_dlq_url | Dead Letter Queue URL (if enabled) |
| lambda_dlq_arn | Dead Letter Queue ARN (if enabled) |

## Requirements

- Terraform >= 1.0
- AWS Provider >= 5.0
- Python 3.11+ (for building packages)
- zip utility (for creating packages)