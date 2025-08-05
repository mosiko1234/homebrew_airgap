# Homebrew Bottles Sync - Troubleshooting Guide

This guide provides comprehensive troubleshooting information for the Homebrew Bottles Sync System, covering common issues, diagnostic procedures, and resolution steps.

## Quick Diagnostic Checklist

Before diving into specific issues, run through this quick checklist:

1. **Check System Status**
   ```bash
   # Verify all AWS resources exist
   aws lambda list-functions --query 'Functions[?contains(FunctionName, `homebrew`)]'
   aws ecs list-clusters --query 'clusterArns[?contains(@, `homebrew`)]'
   aws s3 ls | grep homebrew
   ```

2. **Check Recent Logs**
   ```bash
   # Lambda orchestrator logs (last 1 hour)
   aws logs tail /aws/lambda/homebrew-sync-orchestrator --since 1h
   
   # ECS task logs (if applicable)
   aws logs tail /aws/ecs/homebrew-sync --since 1h
   ```

3. **Verify Permissions**
   ```bash
   # Check IAM roles
   aws iam get-role --role-name homebrew-sync-lambda-orchestrator-role
   aws iam get-role --role-name homebrew-sync-ecs-task-role
   ```

4. **Check EventBridge Schedule**
   ```bash
   aws events describe-rule --name homebrew-sync-schedule
   ```

## Common Issues and Solutions

### 1. Sync Not Running on Schedule

#### Symptoms
- No sync activity on expected schedule
- No CloudWatch logs generated
- EventBridge rule shows no invocations

#### Diagnostic Steps
```bash
# Check EventBridge rule status
aws events describe-rule --name homebrew-sync-schedule

# Check rule targets
aws events list-targets-by-rule --rule homebrew-sync-schedule

# Check CloudWatch metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Events \
  --metric-name SuccessfulInvocations \
  --dimensions Name=RuleName,Value=homebrew-sync-schedule \
  --start-time $(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 3600 \
  --statistics Sum
```

#### Common Causes and Solutions

**Rule is Disabled**
```bash
# Enable the rule
aws events enable-rule --name homebrew-sync-schedule
```

**Incorrect Cron Expression**
```bash
# Verify cron syntax (Sunday 3 AM UTC)
aws events put-rule \
  --name homebrew-sync-schedule \
  --schedule-expression "cron(0 3 ? * SUN *)" \
  --state ENABLED
```

**Missing IAM Permissions**
```bash
# Check EventBridge role permissions
aws iam list-attached-role-policies --role-name EventBridgeExecutionRole
```

### 2. Lambda Function Timeouts

#### Symptoms
- Lambda function times out after 15 minutes
- Partial sync completion
- Error: "Task timed out after 900.00 seconds"

#### Diagnostic Steps
```bash
# Check Lambda configuration
aws lambda get-function-configuration --function-name homebrew-sync-orchestrator

# Check recent invocations
aws lambda get-function --function-name homebrew-sync-orchestrator \
  --query 'Configuration.[Timeout,MemorySize,Runtime]'

# Check CloudWatch metrics for duration
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=homebrew-sync-orchestrator \
  --start-time $(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average,Maximum
```

#### Solutions

**Increase Lambda Timeout**
```bash
# Increase timeout to maximum (15 minutes)
aws lambda update-function-configuration \
  --function-name homebrew-sync-orchestrator \
  --timeout 900
```

**Route Large Downloads to ECS**
- Verify size threshold configuration
- Check ECS cluster availability
- Ensure proper routing logic in orchestrator

**Optimize Lambda Performance**
```bash
# Increase memory allocation (improves CPU)
aws lambda update-function-configuration \
  --function-name homebrew-sync-orchestrator \
  --memory-size 1024
```

### 3. ECS Task Failures

#### Symptoms
- ECS tasks fail to start or exit with non-zero code
- Error: "Task stopped with exit code 1"
- No bottles downloaded despite large size threshold

#### Diagnostic Steps
```bash
# Check ECS cluster status
aws ecs describe-clusters --clusters homebrew-sync

# Check service status
aws ecs describe-services --cluster homebrew-sync --services homebrew-bottles-sync

# List recent tasks
aws ecs list-tasks --cluster homebrew-sync --service-name homebrew-bottles-sync

# Get task details
TASK_ARN=$(aws ecs list-tasks --cluster homebrew-sync --query 'taskArns[0]' --output text)
aws ecs describe-tasks --cluster homebrew-sync --tasks $TASK_ARN

# Check task logs
aws logs tail /aws/ecs/homebrew-sync --follow
```

#### Common Causes and Solutions

**Insufficient ECS Capacity**
```bash
# Check cluster capacity
aws ecs describe-clusters --clusters homebrew-sync \
  --query 'clusters[0].[registeredContainerInstancesCount,runningTasksCount,pendingTasksCount]'

# Check Fargate capacity (if using Fargate)
aws service-quotas get-service-quota \
  --service-code fargate \
  --quota-code L-3032A538  # Running Fargate tasks
```

**Container Image Issues**
```bash
# Check if image exists and is accessible
aws ecr describe-images --repository-name homebrew-bottles-sync

# Test image locally
docker pull your-account.dkr.ecr.region.amazonaws.com/homebrew-bottles-sync:latest
docker run --rm homebrew-bottles-sync:latest python --version
```

**Network Configuration Issues**
```bash
# Check security groups
aws ec2 describe-security-groups --group-ids sg-xxxxxxxxx

# Check subnet configuration
aws ec2 describe-subnets --subnet-ids subnet-xxxxxxxxx

# Check NAT Gateway status
aws ec2 describe-nat-gateways --filter "Name=state,Values=available"
```

**EFS Mount Issues** (if using EFS)
```bash
# Check EFS file system
aws efs describe-file-systems --file-system-id fs-xxxxxxxxx

# Check mount targets
aws efs describe-mount-targets --file-system-id fs-xxxxxxxxx

# Test EFS connectivity
aws ecs execute-command \
  --cluster homebrew-sync \
  --task $TASK_ARN \
  --interactive \
  --command "df -h /mnt/efs"
```

### 4. S3 Access Issues

#### Symptoms
- Access denied errors when uploading bottles
- Hash file update failures
- Error: "An error occurred (AccessDenied) when calling the PutObject operation"

#### Diagnostic Steps
```bash
# Check S3 bucket exists and is accessible
aws s3 ls s3://your-homebrew-bucket/

# Check bucket policy
aws s3api get-bucket-policy --bucket your-homebrew-bucket

# Check IAM role permissions
aws iam list-attached-role-policies --role-name homebrew-sync-lambda-role
aws iam get-role-policy --role-name homebrew-sync-lambda-role --policy-name S3Access

# Test S3 access with current credentials
aws s3 cp test.txt s3://your-homebrew-bucket/test.txt
aws s3 rm s3://your-homebrew-bucket/test.txt
```

#### Solutions

**Fix IAM Permissions**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::your-homebrew-bucket",
        "arn:aws:s3:::your-homebrew-bucket/*"
      ]
    }
  ]
}
```

**Check Bucket Policy**
```bash
# Remove overly restrictive bucket policies
aws s3api delete-bucket-policy --bucket your-homebrew-bucket

# Or update bucket policy to allow access
aws s3api put-bucket-policy --bucket your-homebrew-bucket --policy file://bucket-policy.json
```

**Verify Bucket Region**
```bash
# Ensure bucket is in the same region as Lambda/ECS
aws s3api get-bucket-location --bucket your-homebrew-bucket
```

### 5. Hash File Corruption

#### Symptoms
- Sync fails with "Invalid hash file format"
- JSON parsing errors in logs
- All bottles being re-downloaded

#### Diagnostic Steps
```bash
# Download and inspect hash file
aws s3 cp s3://your-homebrew-bucket/bottles_hash.json ./
cat bottles_hash.json | jq .

# Check file size and modification time
aws s3 ls s3://your-homebrew-bucket/bottles_hash.json

# Check S3 object versions (if versioning enabled)
aws s3api list-object-versions --bucket your-homebrew-bucket --prefix bottles_hash.json
```

#### Solutions

**Restore from S3 Version**
```bash
# List available versions
aws s3api list-object-versions --bucket your-homebrew-bucket --prefix bottles_hash.json

# Restore specific version
aws s3api copy-object \
  --copy-source your-homebrew-bucket/bottles_hash.json?versionId=VERSION_ID \
  --bucket your-homebrew-bucket \
  --key bottles_hash.json
```

**Rebuild Hash File**
```bash
# Delete corrupted hash file (will trigger rebuild)
aws s3 rm s3://your-homebrew-bucket/bottles_hash.json

# Manually trigger sync to rebuild
aws lambda invoke \
  --function-name homebrew-sync-orchestrator \
  --payload '{"source": "manual", "rebuild_hash": true}' \
  response.json
```

**Validate Hash File Format**
```python
import json

# Validate JSON structure
with open('bottles_hash.json', 'r') as f:
    data = json.load(f)
    
required_fields = ['last_updated', 'bottles']
for field in required_fields:
    if field not in data:
        print(f"Missing required field: {field}")
```

### 6. Slack Notification Failures

#### Symptoms
- No Slack notifications received
- Error: "Failed to send Slack notification: 404 Not Found"
- Webhook timeout errors

#### Diagnostic Steps
```bash
# Check Secrets Manager secret
aws secretsmanager get-secret-value --secret-id homebrew-sync/slack-webhook

# Test webhook manually
curl -X POST -H 'Content-type: application/json' \
  --data '{"text":"Test notification from troubleshooting"}' \
  YOUR_WEBHOOK_URL

# Check Lambda logs for notification errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/homebrew-sync-orchestrator \
  --filter-pattern "notification" \
  --start-time $(date -d '1 hour ago' +%s)000
```

#### Solutions

**Update Webhook URL**
```bash
# Update secret with correct webhook URL
aws secretsmanager update-secret \
  --secret-id homebrew-sync/slack-webhook \
  --secret-string "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
```

**Check Slack App Configuration**
- Verify webhook URL is active in Slack app settings
- Check channel permissions for the bot
- Ensure webhook hasn't been revoked

**Test Notification Service**
```python
import boto3
import json

# Test notification function directly
lambda_client = boto3.client('lambda')

test_payload = {
    "message": "Test notification",
    "status": "success",
    "details": {"bottles_downloaded": 5, "total_size": "100MB"}
}

response = lambda_client.invoke(
    FunctionName='homebrew-sync-orchestrator',
    Payload=json.dumps(test_payload)
)
```

### 7. Network Connectivity Issues

#### Symptoms
- Timeouts when downloading bottles
- DNS resolution failures
- Connection refused errors

#### Diagnostic Steps
```bash
# Check NAT Gateway status
aws ec2 describe-nat-gateways --filter "Name=state,Values=available"

# Check route tables
aws ec2 describe-route-tables --filters "Name=tag:Name,Values=*homebrew*"

# Check security group rules
aws ec2 describe-security-groups --group-ids sg-xxxxxxxxx

# Test connectivity from ECS task
aws ecs execute-command \
  --cluster homebrew-sync \
  --task $TASK_ARN \
  --interactive \
  --command "curl -I https://formulae.brew.sh/api/formula.json"
```

#### Solutions

**Fix Security Group Rules**
```bash
# Allow HTTPS outbound
aws ec2 authorize-security-group-egress \
  --group-id sg-xxxxxxxxx \
  --protocol tcp \
  --port 443 \
  --cidr 0.0.0.0/0

# Allow DNS outbound
aws ec2 authorize-security-group-egress \
  --group-id sg-xxxxxxxxx \
  --protocol udp \
  --port 53 \
  --cidr 0.0.0.0/0
```

**Check NAT Gateway Configuration**
```bash
# Verify NAT Gateway has Elastic IP
aws ec2 describe-nat-gateways --nat-gateway-ids nat-xxxxxxxxx

# Check route table associations
aws ec2 describe-route-tables --route-table-ids rtb-xxxxxxxxx
```

### 8. Performance Issues

#### Symptoms
- Slow download speeds
- High memory usage
- Long sync duration

#### Diagnostic Steps
```bash
# Check CloudWatch metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=homebrew-sync-orchestrator \
  --start-time $(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average,Maximum

# Check ECS task resource utilization
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name CPUUtilization \
  --dimensions Name=ServiceName,Value=homebrew-bottles-sync \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average,Maximum
```

#### Solutions

**Optimize Lambda Configuration**
```bash
# Increase memory (also increases CPU)
aws lambda update-function-configuration \
  --function-name homebrew-sync-orchestrator \
  --memory-size 1024

# Enable provisioned concurrency for consistent performance
aws lambda put-provisioned-concurrency-config \
  --function-name homebrew-sync-orchestrator \
  --provisioned-concurrency-config ProvisionedConcurrencyCount=2
```

**Optimize ECS Configuration**
```bash
# Update task definition with more resources
aws ecs register-task-definition \
  --family homebrew-bottles-sync \
  --cpu 4096 \
  --memory 16384 \
  --requires-compatibilities FARGATE \
  --network-mode awsvpc
```

**Enable EFS Provisioned Throughput**
```bash
# Increase EFS throughput for better I/O performance
aws efs modify-file-system \
  --file-system-id fs-xxxxxxxxx \
  --throughput-mode provisioned \
  --provisioned-throughput-in-mibps 500
```

## Monitoring and Alerting

### Key Metrics to Monitor

1. **Lambda Metrics**
   - Duration, Errors, Throttles
   - Memory utilization
   - Concurrent executions

2. **ECS Metrics**
   - CPU and memory utilization
   - Task count and health
   - Service events

3. **S3 Metrics**
   - Request counts and error rates
   - Bucket size growth
   - Data transfer costs

4. **Custom Application Metrics**
   - Bottles downloaded per sync
   - Sync success/failure rate
   - Download size and duration

### Setting Up Alerts

```bash
# Create CloudWatch alarm for Lambda errors
aws cloudwatch put-metric-alarm \
  --alarm-name "homebrew-sync-lambda-errors" \
  --alarm-description "Lambda function errors" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --threshold 1 \
  --comparison-operator GreaterThanOrEqualToThreshold \
  --dimensions Name=FunctionName,Value=homebrew-sync-orchestrator \
  --evaluation-periods 1 \
  --alarm-actions arn:aws:sns:region:account:homebrew-sync-alerts

# Create alarm for ECS task failures
aws cloudwatch put-metric-alarm \
  --alarm-name "homebrew-sync-ecs-failures" \
  --alarm-description "ECS task failures" \
  --metric-name TaskCount \
  --namespace AWS/ECS \
  --statistic Average \
  --period 300 \
  --threshold 0 \
  --comparison-operator LessThanThreshold \
  --dimensions Name=ServiceName,Value=homebrew-bottles-sync \
  --evaluation-periods 2 \
  --alarm-actions arn:aws:sns:region:account:homebrew-sync-alerts
```

## Log Analysis

### Useful Log Queries

**Find Sync Failures**
```bash
aws logs filter-log-events \
  --log-group-name /aws/lambda/homebrew-sync-orchestrator \
  --filter-pattern "ERROR" \
  --start-time $(date -d '24 hours ago' +%s)000
```

**Analyze Sync Performance**
```bash
aws logs start-query \
  --log-group-name /aws/lambda/homebrew-sync-orchestrator \
  --start-time $(date -d '24 hours ago' +%s) \
  --end-time $(date +%s) \
  --query-string 'fields @timestamp, @duration | filter @type = "REPORT" | stats avg(@duration), max(@duration), min(@duration) by bin(5m)'
```

**Track Bottle Downloads**
```bash
aws logs filter-log-events \
  --log-group-name /aws/ecs/homebrew-sync \
  --filter-pattern "Downloaded bottle" \
  --start-time $(date -d '1 hour ago' +%s)000
```

## Recovery Procedures

### Complete System Recovery

1. **Verify Infrastructure**
   ```bash
   cd terraform
   terraform plan
   terraform apply
   ```

2. **Rebuild Hash File**
   ```bash
   aws s3 rm s3://your-homebrew-bucket/bottles_hash.json
   ```

3. **Trigger Manual Sync**
   ```bash
   aws lambda invoke \
     --function-name homebrew-sync-orchestrator \
     --payload '{"source": "recovery"}' \
     response.json
   ```

4. **Monitor Recovery**
   ```bash
   aws logs tail /aws/lambda/homebrew-sync-orchestrator --follow
   ```

### Partial Recovery

For specific component failures, refer to the individual troubleshooting sections above.

## Getting Help

If you're still experiencing issues after following this guide:

1. **Collect Diagnostic Information**
   - CloudWatch logs from the last 24 hours
   - Terraform state and configuration
   - AWS resource configurations
   - Error messages and stack traces

2. **Check Documentation**
   - Review module READMEs in `terraform/modules/`
   - Check AWS service documentation
   - Review Homebrew API documentation

3. **Contact Support**
   - Include all diagnostic information
   - Specify your environment (dev/staging/prod)
   - Provide steps to reproduce the issue

## Prevention

### Best Practices

1. **Regular Monitoring**
   - Set up CloudWatch dashboards
   - Configure appropriate alarms
   - Review logs weekly

2. **Testing**
   - Test manual triggers monthly
   - Validate backup and recovery procedures
   - Monitor cost trends

3. **Maintenance**
   - Keep Terraform modules updated
   - Review and rotate secrets regularly
   - Update container images for security patches

4. **Documentation**
   - Keep runbooks updated
   - Document any custom configurations
   - Maintain change logs