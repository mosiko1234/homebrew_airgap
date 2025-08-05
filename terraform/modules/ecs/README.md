# ECS Module

This Terraform module creates an Amazon ECS (Elastic Container Service) infrastructure for running large-scale Homebrew bottle downloads that exceed the Lambda size threshold. The module uses AWS Fargate for serverless container execution with configurable CPU, memory, and storage resources.

## Features

- **ECS Fargate Cluster**: Serverless container execution without managing EC2 instances
- **Task Definition**: Optimized for large file downloads with configurable resources
- **EFS Integration**: Optional persistent storage for temporary files during downloads
- **Auto Scaling**: Automatic scaling based on CPU and memory utilization
- **CloudWatch Logging**: Centralized logging with configurable retention
- **Security Groups**: Minimal required network access for downloads
- **IAM Integration**: Least-privilege roles for task execution and application access

## Architecture

```
EventBridge → Lambda Orchestrator → ECS Task (Fargate)
                                        ↓
                                   EFS Storage (optional)
                                        ↓
                                   S3 Bucket
```

## Usage

```hcl
module "ecs" {
  source = "./modules/ecs"

  project_name   = "homebrew-bottles-sync"
  environment    = "prod"
  aws_region     = "us-west-2"
  aws_account_id = "123456789012"

  # Network configuration
  vpc_id              = module.network.vpc_id
  private_subnet_ids  = module.network.private_subnet_ids
  security_group_ids  = [module.network.ecs_security_group_id]

  # IAM roles
  task_execution_role_arn = module.iam.ecs_task_execution_role_arn
  task_role_arn          = module.iam.ecs_task_role_arn

  # Container configuration
  container_image = "homebrew-bottles-sync:latest"
  container_port  = 8080

  # Resource allocation
  task_cpu    = 2048  # 2 vCPUs
  task_memory = 8192  # 8 GB

  # Storage configuration
  enable_efs_storage    = true
  efs_throughput_mode   = "provisioned"
  efs_provisioned_throughput = 100  # MB/s

  # Auto scaling
  enable_auto_scaling     = true
  min_capacity           = 0
  max_capacity           = 10
  target_cpu_utilization = 70
  target_memory_utilization = 80

  # Environment variables
  environment_variables = {
    S3_BUCKET_NAME           = module.s3.bucket_name
    SLACK_WEBHOOK_SECRET_NAME = module.notifications.slack_webhook_secret_name
    AWS_REGION              = var.aws_region
    LOG_LEVEL               = "INFO"
    DOWNLOAD_CONCURRENCY    = "5"
    TEMP_STORAGE_PATH       = "/tmp/bottles"
  }

  # Logging configuration
  log_retention_days = 30
  log_level         = "INFO"

  tags = {
    Environment = "prod"
    Project     = "homebrew-bottles-sync"
  }
}
```

## Container Requirements

The ECS tasks expect a container image with the following characteristics:

### Base Image
- Python 3.11+ runtime
- Required system packages: `curl`, `wget`, `unzip`
- AWS CLI (optional, for debugging)

### Application Structure
```
/app/
├── main.py              # Entry point for ECS task
├── requirements.txt     # Python dependencies
├── shared/             # Shared modules
│   ├── models.py
│   ├── homebrew_api.py
│   ├── s3_service.py
│   └── notification_service.py
└── Dockerfile
```

### Environment Variables
The container receives the following environment variables:

- `S3_BUCKET_NAME`: Target S3 bucket for bottles
- `SLACK_WEBHOOK_SECRET_NAME`: Secrets Manager secret name
- `AWS_REGION`: AWS region for API calls
- `LOG_LEVEL`: Logging verbosity (DEBUG, INFO, WARNING, ERROR)
- `DOWNLOAD_CONCURRENCY`: Number of concurrent downloads
- `TEMP_STORAGE_PATH`: Path for temporary file storage
- `EFS_MOUNT_PATH`: EFS mount point (if enabled)

## EFS Storage Configuration

When `enable_efs_storage` is true, the module creates:

### EFS File System
- **Performance Mode**: General Purpose (default) or Max I/O
- **Throughput Mode**: Bursting (default) or Provisioned
- **Encryption**: Enabled at rest and in transit
- **Backup**: Automatic daily backups (configurable)

### Mount Targets
- Created in each private subnet for high availability
- Security group allows NFS traffic from ECS tasks
- DNS resolution enabled for easy mounting

### Access Points
- Dedicated access point for ECS tasks
- POSIX permissions configured for application user
- Root directory creation with appropriate ownership

## Auto Scaling Configuration

The module supports automatic scaling based on CloudWatch metrics:

### Scaling Policies
- **Scale Up**: When CPU > target utilization for 2 consecutive periods
- **Scale Down**: When CPU < target utilization for 5 consecutive periods
- **Memory Scaling**: Similar policies for memory utilization
- **Custom Metrics**: Support for application-specific scaling metrics

### Scaling Limits
- **Min Capacity**: Minimum number of running tasks (default: 0)
- **Max Capacity**: Maximum number of running tasks (default: 10)
- **Scale-out Cooldown**: 300 seconds (configurable)
- **Scale-in Cooldown**: 600 seconds (configurable)

## Security Features

### Network Security
- Tasks run in private subnets with no direct internet access
- Outbound internet access via NAT Gateway
- Security groups allow only required ports (HTTPS, DNS)
- VPC Flow Logs for network monitoring

### IAM Security
- Task execution role: Minimal permissions for ECS operations
- Task role: Application-specific permissions (S3, Secrets Manager)
- No privileged container execution
- Read-only root filesystem (configurable)

### Data Security
- EFS encryption at rest and in transit
- S3 server-side encryption for uploaded bottles
- Secrets Manager for sensitive configuration
- CloudWatch Logs encryption

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| project_name | Name of the project | `string` | n/a | yes |
| environment | Environment name | `string` | `"prod"` | no |
| aws_region | AWS region | `string` | n/a | yes |
| aws_account_id | AWS account ID | `string` | n/a | yes |
| vpc_id | VPC ID for ECS cluster | `string` | n/a | yes |
| private_subnet_ids | Private subnet IDs for ECS tasks | `list(string)` | n/a | yes |
| security_group_ids | Security group IDs for ECS tasks | `list(string)` | n/a | yes |
| task_execution_role_arn | IAM role ARN for task execution | `string` | n/a | yes |
| task_role_arn | IAM role ARN for application access | `string` | n/a | yes |
| container_image | Docker image for ECS tasks | `string` | n/a | yes |
| container_port | Container port for health checks | `number` | `8080` | no |
| task_cpu | CPU units for ECS task (1024 = 1 vCPU) | `number` | `2048` | no |
| task_memory | Memory for ECS task (MB) | `number` | `8192` | no |
| enable_efs_storage | Enable EFS storage for tasks | `bool` | `true` | no |
| efs_performance_mode | EFS performance mode | `string` | `"generalPurpose"` | no |
| efs_throughput_mode | EFS throughput mode | `string` | `"bursting"` | no |
| efs_provisioned_throughput | EFS provisioned throughput (MB/s) | `number` | `100` | no |
| enable_auto_scaling | Enable auto scaling for ECS service | `bool` | `true` | no |
| min_capacity | Minimum number of tasks | `number` | `0` | no |
| max_capacity | Maximum number of tasks | `number` | `10` | no |
| target_cpu_utilization | Target CPU utilization for scaling | `number` | `70` | no |
| target_memory_utilization | Target memory utilization for scaling | `number` | `80` | no |
| environment_variables | Environment variables for container | `map(string)` | `{}` | no |
| secrets | Secrets from Secrets Manager | `map(string)` | `{}` | no |
| log_retention_days | CloudWatch log retention days | `number` | `30` | no |
| log_level | Application log level | `string` | `"INFO"` | no |
| enable_execute_command | Enable ECS Exec for debugging | `bool` | `false` | no |
| health_check_grace_period | Health check grace period (seconds) | `number` | `300` | no |
| tags | Tags to apply to resources | `map(string)` | `{}` | no |

## Outputs

| Name | Description |
|------|-------------|
| cluster_name | Name of the ECS cluster |
| cluster_arn | ARN of the ECS cluster |
| cluster_id | ID of the ECS cluster |
| service_name | Name of the ECS service |
| service_arn | ARN of the ECS service |
| service_id | ID of the ECS service |
| task_definition_arn | ARN of the task definition |
| task_definition_family | Family name of the task definition |
| task_definition_revision | Revision of the task definition |
| efs_file_system_id | ID of the EFS file system (if enabled) |
| efs_file_system_arn | ARN of the EFS file system (if enabled) |
| efs_access_point_id | ID of the EFS access point (if enabled) |
| efs_access_point_arn | ARN of the EFS access point (if enabled) |
| log_group_name | Name of the CloudWatch log group |
| log_group_arn | ARN of the CloudWatch log group |
| auto_scaling_target_arn | ARN of the auto scaling target (if enabled) |
| security_group_id | ID of the ECS security group |

## Troubleshooting

### Common Issues

#### Task Startup Failures
```bash
# Check task definition
aws ecs describe-task-definition --task-definition homebrew-bottles-sync

# Check service events
aws ecs describe-services --cluster homebrew-sync --services homebrew-bottles-sync

# Check task logs
aws logs tail /aws/ecs/homebrew-bottles-sync --follow
```

#### EFS Mount Issues
```bash
# Check EFS mount targets
aws efs describe-mount-targets --file-system-id fs-xxxxxxxxx

# Check security group rules
aws ec2 describe-security-groups --group-ids sg-xxxxxxxxx

# Test EFS connectivity from task
aws ecs execute-command --cluster homebrew-sync --task TASK_ID --interactive --command "/bin/bash"
```

#### Resource Constraints
```bash
# Check cluster capacity
aws ecs describe-clusters --clusters homebrew-sync

# Check task resource utilization
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name CPUUtilization \
  --dimensions Name=ServiceName,Value=homebrew-bottles-sync \
  --start-time 2025-07-21T00:00:00Z \
  --end-time 2025-07-21T23:59:59Z \
  --period 300 \
  --statistics Average
```

### Performance Optimization

#### CPU and Memory Tuning
- Monitor CloudWatch metrics for resource utilization
- Adjust `task_cpu` and `task_memory` based on workload
- Consider using larger task sizes for better performance

#### Storage Optimization
- Use EFS Provisioned Throughput for consistent performance
- Consider using EBS volumes for temporary storage
- Optimize file I/O patterns in application code

#### Network Optimization
- Use placement groups for tasks requiring high network performance
- Consider using Enhanced Networking for better throughput
- Monitor VPC Flow Logs for network bottlenecks

## Cost Considerations

### Fargate Pricing
- **CPU**: $0.04048 per vCPU per hour
- **Memory**: $0.004445 per GB per hour
- **Storage**: $0.000111 per GB per hour (ephemeral)

### EFS Pricing
- **Standard Storage**: $0.30 per GB per month
- **Provisioned Throughput**: $6.00 per MB/s per month
- **Requests**: $0.0004 per 1,000 requests

### Example Monthly Cost (2 vCPU, 8GB RAM, 4 hours/week)
- Fargate: ~$13/month
- EFS (100GB, provisioned): ~$630/month
- CloudWatch Logs: ~$5/month
- **Total**: ~$650/month

## Requirements Satisfied

This module satisfies the following requirements:

- **Requirement 8.1**: ECS-based sync for large downloads (≥20GB)
- **Requirement 8.2**: Sufficient CPU, memory, and disk space configuration
- **Requirement 8.3**: Temporary working directory support via EFS
- **Requirement 8.4**: EventBridge integration for triggering ECS tasks
- **Requirement 8.5**: Appropriate resource configuration for large-scale downloads
- **Requirement 5.1**: Modular Terraform infrastructure deployment
- **Requirement 6.1**: AWS security best practices implementation