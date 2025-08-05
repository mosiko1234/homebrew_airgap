# Homebrew Bottles Sync System

An AWS-based automated solution that downloads and mirrors Homebrew bottles for the three most recent macOS versions on a weekly schedule. The system uses Terraform for infrastructure management, AWS Lambda for orchestration, ECS for large downloads, and S3 for storage.

## Features

- **Automated Weekly Sync**: Runs every Sunday at 03:00 UTC via EventBridge
- **Intelligent Routing**: Uses Lambda for small downloads (<20GB), ECS for large downloads (≥20GB)
- **Duplicate Prevention**: Tracks downloaded bottles via SHA checksums to avoid redundant downloads
- **External Hash File Support**: Load pre-existing bottle hashes from S3 or HTTPS URLs to skip already-downloaded bottles
- **Organized Storage**: Date-based folder structure in S3 for easy management
- **Real-time Notifications**: Slack integration for sync status updates
- **Infrastructure as Code**: Complete Terraform modules for reproducible deployments
- **Cost Optimized**: Lifecycle policies and intelligent routing minimize AWS costs

## Architecture Overview

```
EventBridge → Lambda Orchestrator → [Lambda Sync | ECS Sync] → S3 Storage
                     ↓
              Slack Notifications
```

The system targets bottles for:
- `arm64_sonoma` (macOS Sonoma on Apple Silicon)
- `arm64_ventura` (macOS Ventura on Apple Silicon) 
- `monterey` (macOS Monterey on Intel/Apple Silicon)

## Quick Start

### Prerequisites

- AWS CLI configured with appropriate permissions
- Terraform >= 1.0
- Python 3.9+ (for local testing)
- Slack webhook URL (optional, for notifications)

### 1. Clone and Configure

```bash
git clone <repository-url>
cd homebrew-bottles-sync
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
```

### 2. Configure Variables

Edit `terraform/terraform.tfvars`:

```hcl
# Required
aws_region = "us-west-2"
environment = "prod"
s3_bucket_name = "my-homebrew-bottle-mirror"

# Optional
slack_webhook_url = "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
size_threshold_gb = 20
enable_notifications = true
```

### 3. Deploy Infrastructure

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

### 4. Verify Deployment

The system will automatically start syncing on the next scheduled run (Sunday 03:00 UTC). To trigger a manual sync:

```bash
aws events put-events --entries file://manual-trigger.json
```

## Configuration

### Environment Variables

The system uses the following configuration options:

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `aws_region` | AWS region for deployment | `us-west-2` | Yes |
| `environment` | Environment name (dev/staging/prod) | `prod` | Yes |
| `s3_bucket_name` | S3 bucket for bottle storage | - | Yes |
| `slack_webhook_url` | Slack webhook for notifications | - | No |
| `size_threshold_gb` | Threshold for Lambda vs ECS routing | `20` | No |
| `enable_notifications` | Enable Slack notifications | `true` | No |
| `schedule_expression` | EventBridge cron expression | `cron(0 3 ? * SUN *)` | No |
| `external_hash_file_s3_key` | S3 key for external hash file | - | No |
| `external_hash_file_s3_bucket` | S3 bucket for external hash file | - | No |
| `external_hash_file_url` | HTTPS URL for external hash file | - | No |

### External Hash File Support

The system can load pre-existing bottle hashes from external sources to skip already-downloaded bottles. This is useful for:

- Initial deployment with existing bottle collections
- Migration from other sync systems
- Disaster recovery scenarios

See [EXTERNAL_HASH_FILE.md](EXTERNAL_HASH_FILE.md) for detailed configuration and usage instructions.

### Terraform Modules

The infrastructure is organized into modular Terraform components:

- **network**: VPC, subnets, security groups for ECS
- **s3**: S3 bucket with versioning and lifecycle policies  
- **lambda**: Orchestrator and sync Lambda functions
- **ecs**: ECS cluster and task definitions for large downloads
- **iam**: IAM roles and policies with least privilege
- **eventbridge**: Scheduled triggers for weekly sync
- **notifications**: Secrets Manager and SNS for alerts
- **monitoring**: CloudWatch alarms and custom metrics

## Usage

### Manual Sync Trigger

To manually trigger a sync outside the scheduled time:

```bash
# Using AWS CLI
aws lambda invoke \
  --function-name homebrew-sync-orchestrator \
  --payload '{"source": "manual"}' \
  response.json

# Using EventBridge
aws events put-events \
  --entries Source=homebrew.sync,DetailType="Manual Sync",Detail='{}'
```

### Monitoring Sync Progress

Check CloudWatch logs for detailed sync progress:

```bash
# Orchestrator logs
aws logs tail /aws/lambda/homebrew-sync-orchestrator --follow

# ECS task logs (when applicable)
aws logs tail /aws/ecs/homebrew-sync --follow
```

### Accessing Downloaded Bottles

Bottles are stored in S3 with the following structure:

```
s3://your-bucket-name/
├── bottles_hash.json                    # Global hash tracking file
├── 2025-07-21/                         # Weekly sync folders
│   ├── curl-8.0.0.arm64_sonoma.bottle.tar.gz
│   ├── curl-8.0.0.arm64_ventura.bottle.tar.gz
│   ├── curl-8.0.0.monterey.bottle.tar.gz
│   └── ...
├── 2025-07-28/
│   └── ...
└── 2025-08-04/
    └── ...
```

Download bottles using AWS CLI:

```bash
# List available dates
aws s3 ls s3://your-bucket-name/ --recursive

# Download specific bottle
aws s3 cp s3://your-bucket-name/2025-07-21/curl-8.0.0.arm64_sonoma.bottle.tar.gz ./

# Sync entire date folder
aws s3 sync s3://your-bucket-name/2025-07-21/ ./bottles/
```

## Slack Notifications

The system sends notifications at key points during the sync process:

### Sync Start Notification
```
🚀 Homebrew Bottles Sync Started
Environment: prod
Date: 2025-07-21
Estimated bottles: 1,247
Estimated size: 15.3 GB
Sync method: Lambda
```

### Progress Updates (ECS only)
```
⏳ Homebrew Sync Progress
Downloaded: 45/150 bottles (30%)
Size: 2.3 GB / 7.8 GB
ETA: 12 minutes
```

### Success Notification
```
✅ Homebrew Bottles Sync Complete
Environment: prod
Date: 2025-07-21
New bottles: 143
Total size: 512 MB
Duration: 8 minutes
S3 location: s3://homebrew-bottles/2025-07-21/
```

### Failure Notification
```
❌ Homebrew Bottles Sync Failed
Environment: prod
Date: 2025-07-21
Error: Timeout downloading curl-8.0.0.arm64_sonoma.bottle.tar.gz
Duration: 14 minutes
Check logs: /aws/lambda/homebrew-sync-orchestrator
```

## Troubleshooting

### Common Issues

#### 1. Lambda Timeout Errors

**Symptom**: Lambda function times out during sync
```
Task timed out after 900.00 seconds
```

**Solution**: 
- Check if download size exceeds Lambda threshold (20GB)
- Verify ECS cluster is properly configured
- Increase Lambda timeout in Terraform configuration

```hcl
# In terraform/modules/lambda/main.tf
resource "aws_lambda_function" "orchestrator" {
  timeout = 900  # Increase if needed
}
```

#### 2. S3 Permission Errors

**Symptom**: Access denied when uploading to S3
```
An error occurred (AccessDenied) when calling the PutObject operation
```

**Solution**:
- Verify IAM roles have S3 permissions
- Check S3 bucket policy allows Lambda/ECS access
- Ensure bucket exists and is in correct region

```bash
# Check IAM role permissions
aws iam get-role-policy --role-name homebrew-sync-lambda-role --policy-name S3Access

# Verify bucket exists
aws s3 ls s3://your-bucket-name/
```

#### 3. ECS Task Failures

**Symptom**: ECS tasks fail to start or complete
```
Task stopped with exit code 1
```

**Solution**:
- Check ECS task logs in CloudWatch
- Verify ECS cluster has sufficient capacity
- Ensure task definition has correct IAM role

```bash
# Check ECS cluster status
aws ecs describe-clusters --clusters homebrew-sync

# View task logs
aws logs tail /aws/ecs/homebrew-sync --follow
```

#### 4. Hash File Corruption

**Symptom**: Sync fails with hash file validation errors
```
Invalid hash file format: bottles_hash.json
```

**Solution**:
- Delete corrupted hash file to trigger rebuild
- Check S3 versioning to restore previous version

```bash
# Delete corrupted hash file
aws s3 rm s3://your-bucket-name/bottles_hash.json

# Restore from version (if versioning enabled)
aws s3api list-object-versions --bucket your-bucket-name --prefix bottles_hash.json
aws s3api get-object --bucket your-bucket-name --key bottles_hash.json --version-id VERSION_ID bottles_hash.json
```

#### 5. Slack Notification Failures

**Symptom**: No Slack notifications received
```
Failed to send Slack notification: 404 Not Found
```

**Solution**:
- Verify Slack webhook URL is correct
- Check Secrets Manager contains valid webhook
- Test webhook manually

```bash
# Check secret value
aws secretsmanager get-secret-value --secret-id homebrew-sync/slack-webhook

# Test webhook manually
curl -X POST -H 'Content-type: application/json' \
  --data '{"text":"Test notification"}' \
  YOUR_WEBHOOK_URL
```

### Debugging Steps

1. **Check CloudWatch Logs**
   ```bash
   # Lambda orchestrator
   aws logs tail /aws/lambda/homebrew-sync-orchestrator --follow
   
   # Lambda sync worker
   aws logs tail /aws/lambda/homebrew-sync-worker --follow
   
   # ECS tasks
   aws logs tail /aws/ecs/homebrew-sync --follow
   ```

2. **Verify Infrastructure State**
   ```bash
   cd terraform
   terraform plan  # Check for configuration drift
   terraform show  # View current state
   ```

3. **Check AWS Resources**
   ```bash
   # EventBridge rules
   aws events list-rules --name-prefix homebrew-sync
   
   # Lambda functions
   aws lambda list-functions --function-version ALL
   
   # ECS clusters
   aws ecs list-clusters
   aws ecs describe-clusters --clusters homebrew-sync
   ```

4. **Monitor Metrics**
   - CloudWatch dashboard: `homebrew-sync-dashboard`
   - Key metrics: sync duration, error rate, bottle count
   - Alarms: sync failures, cost thresholds

### Performance Optimization

#### Reduce Sync Time
- Increase ECS task CPU/memory allocation
- Enable parallel downloads in sync workers
- Use S3 Transfer Acceleration

#### Reduce Costs
- Adjust S3 lifecycle policies
- Use Spot instances for ECS (if acceptable)
- Optimize Lambda memory allocation

#### Improve Reliability
- Enable S3 Cross-Region Replication
- Implement retry logic with exponential backoff
- Set up CloudWatch alarms for proactive monitoring

## Development

### Local Testing

```bash
# Install dependencies
pip install -r requirements.txt
pip install -r lambda/orchestrator/requirements.txt
pip install -r lambda/sync/requirements.txt

# Run unit tests
python -m pytest tests/ -v

# Run integration tests (requires AWS credentials)
python -m pytest tests/test_integration.py -v
```

### Adding New Features

1. Update requirements in `.kiro/specs/homebrew-bottles-sync/requirements.md`
2. Modify design in `.kiro/specs/homebrew-bottles-sync/design.md`
3. Add implementation tasks to `.kiro/specs/homebrew-bottles-sync/tasks.md`
4. Implement changes following the existing patterns
5. Add tests for new functionality
6. Update documentation

## Security Considerations

- All IAM roles follow least privilege principle
- Secrets stored in AWS Secrets Manager
- S3 bucket has server-side encryption enabled
- ECS tasks run in private subnets
- CloudTrail logging enabled for audit trail

## Cost Estimation

Typical monthly costs for moderate usage:

- Lambda: $5-15 (orchestrator + sync functions)
- ECS: $10-30 (Fargate tasks for large syncs)
- S3: $20-100 (storage + requests, varies by bottle count)
- EventBridge: <$1 (scheduled rules)
- CloudWatch: $5-15 (logs + metrics)

**Total: $40-160/month** (varies significantly based on bottle storage)

## Support

For issues and questions:

1. Check this troubleshooting guide
2. Review CloudWatch logs for error details
3. Consult Terraform module documentation
4. Open an issue in the project repository

## License

[Add your license information here]