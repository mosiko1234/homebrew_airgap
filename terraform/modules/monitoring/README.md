# Monitoring Module

This Terraform module creates comprehensive monitoring and observability infrastructure for the Homebrew Bottles Sync System, including CloudWatch dashboards, alarms, custom metrics, and X-Ray tracing.

## Features

- **CloudWatch Dashboard**: Visual monitoring of sync operations, performance metrics, and system health
- **CloudWatch Alarms**: Automated alerting for failures, performance issues, and cost thresholds
- **Custom Metrics**: Application-specific metrics for sync progress, bottle counts, and error rates
- **X-Ray Tracing**: Distributed tracing for Lambda functions to identify performance bottlenecks
- **Log Insights Queries**: Pre-configured queries for troubleshooting and analysis
- **Cost Monitoring**: Budget alerts and cost optimization recommendations

## Usage

```hcl
module "monitoring" {
  source = "./modules/monitoring"

  project_name     = "homebrew-bottles-sync"
  environment      = "prod"
  aws_region       = "us-west-2"
  aws_account_id   = "123456789012"

  # Lambda function names for monitoring
  lambda_orchestrator_function_name = module.lambda.lambda_orchestrator_function_name
  lambda_sync_function_name        = module.lambda.lambda_sync_function_name

  # ECS cluster and service names
  ecs_cluster_name = module.ecs.cluster_name
  ecs_service_name = module.ecs.service_name

  # S3 bucket for monitoring
  s3_bucket_name = module.s3.bucket_name

  # SNS topic for alerts
  sns_topic_arn = module.notifications.sns_topic_arn

  # Monitoring configuration
  enable_detailed_monitoring = true
  enable_xray_tracing       = true
  dashboard_refresh_interval = "PT1M"  # 1 minute

  # Alert thresholds
  lambda_error_rate_threshold    = 5    # 5% error rate
  lambda_duration_threshold      = 300  # 5 minutes
  ecs_cpu_utilization_threshold  = 80   # 80% CPU
  ecs_memory_utilization_threshold = 80 # 80% memory
  s3_request_error_threshold     = 10   # 10 errors per minute

  # Cost monitoring
  monthly_budget_limit = 200  # $200 USD
  cost_alert_threshold = 80   # Alert at 80% of budget

  tags = {
    Environment = "prod"
    Project     = "homebrew-bottles-sync"
  }
}
```

## CloudWatch Dashboard

The module creates a comprehensive dashboard with the following widgets:

### Lambda Metrics
- Function invocations and duration
- Error rates and success rates
- Memory utilization and throttles
- Concurrent executions

### ECS Metrics
- Task count and service status
- CPU and memory utilization
- Network I/O and disk usage
- Task start/stop events

### S3 Metrics
- Request counts (GET, PUT, DELETE)
- Error rates (4xx, 5xx)
- Bucket size and object count
- Data transfer metrics

### Custom Application Metrics
- Bottles downloaded per sync
- Sync duration and success rate
- Hash file update frequency
- Download size and transfer rate

## CloudWatch Alarms

The module creates the following alarms:

### Critical Alarms (Immediate Action Required)
- **Lambda Function Errors**: Error rate > threshold
- **ECS Task Failures**: Task exit code != 0
- **S3 Access Errors**: 4xx/5xx error rate > threshold
- **Sync Job Failures**: Custom metric for failed syncs

### Warning Alarms (Investigation Recommended)
- **Lambda Duration**: Function duration > threshold
- **ECS High CPU/Memory**: Resource utilization > threshold
- **Large Download Size**: Unexpected increase in download volume
- **Cost Budget**: Monthly spend > threshold

### Informational Alarms
- **Sync Completion**: Successful sync notifications
- **New Bottles Detected**: Significant increase in new bottles

## Custom Metrics

The module defines custom CloudWatch metrics that are published by the application:

### Sync Metrics
- `HomebrewSync/BottlesDownloaded`: Count of bottles downloaded per sync
- `HomebrewSync/SyncDuration`: Time taken for complete sync operation
- `HomebrewSync/SyncSuccess`: Binary metric (1 = success, 0 = failure)
- `HomebrewSync/DownloadSize`: Total size of bottles downloaded (bytes)

### Performance Metrics
- `HomebrewSync/APIResponseTime`: Homebrew API response time
- `HomebrewSync/S3UploadRate`: S3 upload throughput (bytes/second)
- `HomebrewSync/HashFileUpdateTime`: Time to update bottles_hash.json

### Error Metrics
- `HomebrewSync/DownloadErrors`: Count of failed bottle downloads
- `HomebrewSync/ValidationErrors`: Count of SHA validation failures
- `HomebrewSync/NotificationErrors`: Count of failed Slack notifications

## X-Ray Tracing

When enabled, X-Ray tracing provides:

- **Service Map**: Visual representation of service interactions
- **Trace Analysis**: Detailed timing of Lambda function execution
- **Error Analysis**: Root cause analysis for failures
- **Performance Insights**: Identification of bottlenecks

### Traced Services
- Lambda Orchestrator function
- Lambda Sync Worker function
- S3 operations (upload, download, list)
- Secrets Manager operations
- External API calls (Homebrew API)

## Log Insights Queries

Pre-configured CloudWatch Logs Insights queries for common troubleshooting scenarios:

### Error Analysis
```sql
fields @timestamp, @message
| filter @message like /ERROR/
| sort @timestamp desc
| limit 100
```

### Sync Performance
```sql
fields @timestamp, @duration
| filter @type = "REPORT"
| stats avg(@duration), max(@duration), min(@duration) by bin(5m)
```

### Bottle Download Analysis
```sql
fields @timestamp, bottle_name, download_size, duration
| filter @message like /Downloaded bottle/
| sort @timestamp desc
| limit 50
```

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| project_name | Name of the project | `string` | n/a | yes |
| environment | Environment name | `string` | `"prod"` | no |
| aws_region | AWS region | `string` | n/a | yes |
| aws_account_id | AWS account ID | `string` | n/a | yes |
| lambda_orchestrator_function_name | Orchestrator Lambda function name | `string` | n/a | yes |
| lambda_sync_function_name | Sync Lambda function name | `string` | n/a | yes |
| ecs_cluster_name | ECS cluster name | `string` | n/a | yes |
| ecs_service_name | ECS service name | `string` | n/a | yes |
| s3_bucket_name | S3 bucket name | `string` | n/a | yes |
| sns_topic_arn | SNS topic ARN for alerts | `string` | n/a | yes |
| enable_detailed_monitoring | Enable detailed CloudWatch monitoring | `bool` | `true` | no |
| enable_xray_tracing | Enable X-Ray tracing | `bool` | `true` | no |
| dashboard_refresh_interval | Dashboard refresh interval | `string` | `"PT1M"` | no |
| lambda_error_rate_threshold | Lambda error rate alarm threshold (%) | `number` | `5` | no |
| lambda_duration_threshold | Lambda duration alarm threshold (seconds) | `number` | `300` | no |
| ecs_cpu_utilization_threshold | ECS CPU utilization alarm threshold (%) | `number` | `80` | no |
| ecs_memory_utilization_threshold | ECS memory utilization alarm threshold (%) | `number` | `80` | no |
| s3_request_error_threshold | S3 request error alarm threshold (per minute) | `number` | `10` | no |
| monthly_budget_limit | Monthly budget limit (USD) | `number` | `200` | no |
| cost_alert_threshold | Cost alert threshold (% of budget) | `number` | `80` | no |
| log_retention_days | CloudWatch logs retention days | `number` | `30` | no |
| tags | Tags to apply to resources | `map(string)` | `{}` | no |

## Outputs

| Name | Description |
|------|-------------|
| dashboard_url | URL of the CloudWatch dashboard |
| dashboard_arn | ARN of the CloudWatch dashboard |
| alarm_arns | Map of alarm names to ARNs |
| log_group_arns | Map of log group names to ARNs |
| xray_service_map_url | URL of the X-Ray service map |
| budget_arn | ARN of the cost budget |
| custom_metric_namespace | Namespace for custom metrics |

## Cost Considerations

- CloudWatch dashboards: $3/month per dashboard
- CloudWatch alarms: $0.10/month per alarm
- CloudWatch Logs: $0.50/GB ingested, $0.03/GB stored
- X-Ray traces: $5.00 per 1 million traces recorded
- Custom metrics: $0.30 per metric per month

Estimated monthly cost: $15-50 depending on log volume and trace frequency.

## Best Practices

### Alarm Configuration
- Set appropriate thresholds based on historical data
- Use composite alarms for complex conditions
- Configure alarm actions (SNS notifications, auto-scaling)
- Test alarm notifications regularly

### Dashboard Design
- Group related metrics together
- Use appropriate time ranges and aggregation periods
- Include both technical and business metrics
- Keep dashboards focused and actionable

### Log Management
- Use structured logging (JSON format)
- Include correlation IDs for tracing
- Set appropriate log retention periods
- Use log sampling for high-volume applications

### Cost Optimization
- Use metric filters to reduce custom metric costs
- Set appropriate log retention periods
- Use CloudWatch Logs Insights instead of exporting logs
- Monitor and optimize X-Ray sampling rates

## Requirements Satisfied

This module satisfies the following requirements:

- **Requirement 6.3**: Comprehensive error logging and CloudWatch metrics
- **Requirement 4.3**: Automated failure alerting through CloudWatch alarms
- **Requirement 9.1**: Monitoring and observability documentation