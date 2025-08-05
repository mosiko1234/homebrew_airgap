# EventBridge Module

This Terraform module creates Amazon EventBridge (formerly CloudWatch Events) infrastructure for scheduling and triggering the Homebrew Bottles Sync System. The module provides flexible scheduling capabilities with support for cron expressions, event patterns, and multiple target types.

## Features

- **Scheduled Rules**: Cron-based scheduling for weekly sync operations
- **Event-Driven Rules**: Custom event patterns for manual triggers and integrations
- **Multiple Targets**: Support for Lambda functions, ECS tasks, and SNS topics
- **Dead Letter Queues**: Error handling for failed event deliveries
- **Input Transformation**: Custom payload transformation for different targets
- **IAM Integration**: Automatic IAM role creation for EventBridge permissions

## Usage

```hcl
module "eventbridge" {
  source = "./modules/eventbridge"

  project_name   = "homebrew-bottles-sync"
  environment    = "prod"
  aws_region     = "us-west-2"
  aws_account_id = "123456789012"

  # Scheduled sync configuration
  schedule_expression = "cron(0 3 ? * SUN *)"  # Every Sunday at 3 AM UTC
  schedule_enabled    = true

  # Lambda targets
  lambda_orchestrator_arn = module.lambda.lambda_orchestrator_function_arn
  lambda_sync_arn        = module.lambda.lambda_sync_function_arn

  # ECS targets
  ecs_cluster_arn        = module.ecs.cluster_arn
  ecs_task_definition_arn = module.ecs.task_definition_arn
  ecs_subnet_ids         = module.network.private_subnet_ids
  ecs_security_group_ids = [module.network.ecs_security_group_id]

  # Notification targets
  sns_topic_arn = module.notifications.sns_topic_arn

  # Error handling
  enable_dlq = true
  dlq_retention_days = 14

  # Custom event patterns
  enable_manual_trigger = true
  enable_api_integration = false

  tags = {
    Environment = "prod"
    Project     = "homebrew-bottles-sync"
  }
}
```

## Scheduling Configuration

### Default Schedule
The module creates a weekly schedule that runs every Sunday at 03:00 UTC:

```
cron(0 3 ? * SUN *)
```

### Custom Schedules
You can customize the schedule using standard cron expressions:

```hcl
# Daily at 2 AM UTC
schedule_expression = "cron(0 2 * * ? *)"

# Twice weekly (Wednesday and Sunday at 3 AM UTC)
schedule_expression = "cron(0 3 ? * WED,SUN *)"

# Monthly on the 1st at midnight UTC
schedule_expression = "cron(0 0 1 * ? *)"
```

### Rate-Based Schedules
Alternative to cron expressions:

```hcl
# Every 7 days
schedule_expression = "rate(7 days)"

# Every 12 hours
schedule_expression = "rate(12 hours)"
```

## Event Patterns

### Manual Trigger Events
When `enable_manual_trigger` is true, the module creates rules for manual sync triggers:

```json
{
  "source": ["homebrew.sync"],
  "detail-type": ["Manual Sync Trigger"],
  "detail": {
    "trigger_type": ["manual", "api"]
  }
}
```

### API Integration Events
When `enable_api_integration` is true, supports external API triggers:

```json
{
  "source": ["homebrew.api"],
  "detail-type": ["Formula Update", "Bottle Release"],
  "detail": {
    "formula_name": [{"exists": true}],
    "version": [{"exists": true}]
  }
}
```

## Target Configuration

### Lambda Function Targets

#### Orchestrator Target
- **Function**: Lambda Orchestrator
- **Input**: Transformed event payload with sync parameters
- **Retry Policy**: 3 attempts with exponential backoff
- **DLQ**: Enabled for failed invocations

#### Sync Worker Target
- **Function**: Lambda Sync Worker (for small downloads)
- **Input**: Formula list and configuration
- **Conditional**: Only triggered for estimated size < threshold

### ECS Task Targets

#### Large Download Tasks
- **Cluster**: ECS Fargate cluster
- **Task Definition**: Homebrew sync container
- **Network**: Private subnets with security groups
- **Input**: Environment variables and formula list
- **Conditional**: Only triggered for estimated size ≥ threshold

### SNS Notification Targets

#### Alert Notifications
- **Topic**: SNS topic for admin alerts
- **Message**: Event details and sync status
- **Filtering**: Only critical events and failures

## Input Transformation

The module provides input transformation for different target types:

### Lambda Input Transformation
```json
{
  "sync_type": "scheduled",
  "trigger_time": "<aws.events.event.ingestion-time>",
  "source": "<source>",
  "environment": "prod"
}
```

### ECS Input Transformation
```json
{
  "containerOverrides": [
    {
      "name": "homebrew-sync",
      "environment": [
        {"name": "SYNC_TYPE", "value": "scheduled"},
        {"name": "TRIGGER_TIME", "value": "<aws.events.event.ingestion-time>"}
      ]
    }
  ]
}
```

## Error Handling

### Dead Letter Queue
When `enable_dlq` is true, the module creates:

- **SQS Queue**: For failed event deliveries
- **Retention**: Configurable message retention (default: 14 days)
- **Redrive Policy**: Automatic retry with exponential backoff
- **Monitoring**: CloudWatch alarms for DLQ message count

### Retry Configuration
- **Maximum Retry Attempts**: 3 (configurable)
- **Retry Interval**: Exponential backoff (1s, 2s, 4s)
- **Maximum Age**: 24 hours for event processing
- **Jitter**: Random delay to prevent thundering herd

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| project_name | Name of the project | `string` | n/a | yes |
| environment | Environment name | `string` | `"prod"` | no |
| aws_region | AWS region | `string` | n/a | yes |
| aws_account_id | AWS account ID | `string` | n/a | yes |
| schedule_expression | Cron or rate expression for scheduling | `string` | `"cron(0 3 ? * SUN *)"` | no |
| schedule_enabled | Enable scheduled sync | `bool` | `true` | no |
| lambda_orchestrator_arn | Lambda orchestrator function ARN | `string` | n/a | yes |
| lambda_sync_arn | Lambda sync worker function ARN | `string` | n/a | yes |
| ecs_cluster_arn | ECS cluster ARN | `string` | n/a | yes |
| ecs_task_definition_arn | ECS task definition ARN | `string` | n/a | yes |
| ecs_subnet_ids | ECS subnet IDs | `list(string)` | n/a | yes |
| ecs_security_group_ids | ECS security group IDs | `list(string)` | n/a | yes |
| sns_topic_arn | SNS topic ARN for notifications | `string` | `""` | no |
| enable_dlq | Enable Dead Letter Queue | `bool` | `true` | no |
| dlq_retention_days | DLQ message retention days | `number` | `14` | no |
| enable_manual_trigger | Enable manual trigger events | `bool` | `true` | no |
| enable_api_integration | Enable API integration events | `bool` | `false` | no |
| max_retry_attempts | Maximum retry attempts | `number` | `3` | no |
| max_event_age_seconds | Maximum event age in seconds | `number` | `86400` | no |
| tags | Tags to apply to resources | `map(string)` | `{}` | no |

## Outputs

| Name | Description |
|------|-------------|
| rule_arn | ARN of the EventBridge rule |
| rule_name | Name of the EventBridge rule |
| rule_id | ID of the EventBridge rule |
| manual_trigger_rule_arn | ARN of manual trigger rule (if enabled) |
| manual_trigger_rule_name | Name of manual trigger rule (if enabled) |
| api_integration_rule_arn | ARN of API integration rule (if enabled) |
| api_integration_rule_name | Name of API integration rule (if enabled) |
| dlq_url | URL of the Dead Letter Queue (if enabled) |
| dlq_arn | ARN of the Dead Letter Queue (if enabled) |
| eventbridge_role_arn | ARN of the EventBridge IAM role |
| eventbridge_role_name | Name of the EventBridge IAM role |

## Manual Triggering

### Using AWS CLI
```bash
# Trigger scheduled sync
aws events put-events \
  --entries Source=homebrew.sync,DetailType="Manual Sync Trigger",Detail='{"trigger_type":"manual"}'

# Trigger specific formula sync
aws events put-events \
  --entries Source=homebrew.sync,DetailType="Formula Sync",Detail='{"formula_names":["curl","wget"],"trigger_type":"selective"}'
```

### Using AWS SDK (Python)
```python
import boto3

client = boto3.client('events')

# Manual sync trigger
response = client.put_events(
    Entries=[
        {
            'Source': 'homebrew.sync',
            'DetailType': 'Manual Sync Trigger',
            'Detail': json.dumps({
                'trigger_type': 'manual',
                'requested_by': 'admin@example.com'
            })
        }
    ]
)
```

## Monitoring and Troubleshooting

### CloudWatch Metrics
- `AWS/Events/SuccessfulInvocations`: Successful rule executions
- `AWS/Events/FailedInvocations`: Failed rule executions
- `AWS/Events/MatchedEvents`: Events matching rule patterns
- `AWS/Events/InvocationsCount`: Total invocations

### Troubleshooting Commands
```bash
# Check rule status
aws events describe-rule --name homebrew-sync-schedule

# List rule targets
aws events list-targets-by-rule --rule homebrew-sync-schedule

# Check DLQ messages
aws sqs receive-message --queue-url https://sqs.region.amazonaws.com/account/dlq-name

# View EventBridge logs
aws logs tail /aws/events/rule/homebrew-sync-schedule --follow
```

### Common Issues

#### Rule Not Triggering
- Verify rule is enabled: `State: "ENABLED"`
- Check cron expression syntax
- Verify target permissions and IAM roles
- Check CloudWatch metrics for failed invocations

#### Target Failures
- Check target function/service logs
- Verify IAM permissions for EventBridge to invoke targets
- Check input transformation syntax
- Review DLQ messages for error details

#### Permission Errors
- Ensure EventBridge has permission to invoke Lambda/ECS
- Verify cross-account permissions if applicable
- Check resource-based policies on targets

## Cost Considerations

- **EventBridge Rules**: Free for first 14 million events per month
- **Custom Events**: $1.00 per million events after free tier
- **Cross-Region Events**: $0.02 per million events
- **DLQ (SQS)**: $0.40 per million requests
- **CloudWatch Logs**: $0.50 per GB ingested

Estimated monthly cost for typical usage: $1-5

## Requirements Satisfied

This module satisfies the following requirements:

- **Requirement 1.1**: Weekly scheduled execution (Sunday at 03:00 UTC)
- **Requirement 5.1**: Modular Terraform infrastructure deployment
- **Requirement 8.4**: EventBridge integration for triggering ECS tasks
- **Requirement 5.3**: Amazon EventBridge with cron expressions