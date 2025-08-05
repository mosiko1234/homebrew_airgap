# IAM Module

This module creates IAM roles and policies for the Homebrew Bottles Sync System.

## Resources Created

### IAM Roles
- **Lambda Orchestrator Role**: For the main orchestration Lambda function
- **Lambda Sync Role**: For the sync worker Lambda function  
- **ECS Task Execution Role**: For ECS service to manage tasks (pull images, logging)
- **ECS Task Role**: For application-level permissions within ECS tasks

### IAM Policies
- **S3 Access Policy**: Minimal S3 permissions for bucket operations
- **Secrets Manager Policy**: Access to Slack webhook URL secret
- **CloudWatch Logs Policy**: Logging permissions for Lambda and ECS
- **ECS Task Execution Policy**: ECR and logging permissions for ECS
- **Lambda Orchestrator Policy**: Permissions to trigger ECS tasks and invoke Lambdas

## Usage

```hcl
module "iam" {
  source = "./modules/iam"
  
  project_name              = "homebrew-bottles-sync"
  aws_region               = "us-west-2"
  aws_account_id           = "123456789012"
  s3_bucket_arn            = module.s3.bucket_arn
  slack_webhook_secret_arn = module.notifications.slack_webhook_secret_arn
  ecs_cluster_name         = "homebrew-sync-cluster"
  
  tags = {
    Project     = "homebrew-bottles-sync"
    Environment = "production"
  }
}
```

## Inputs

| Name | Description | Type | Required |
|------|-------------|------|----------|
| project_name | Name of the project, used for resource naming | string | yes |
| aws_region | AWS region where resources are deployed | string | yes |
| aws_account_id | AWS account ID | string | yes |
| s3_bucket_arn | ARN of the S3 bucket for storing Homebrew bottles | string | yes |
| slack_webhook_secret_arn | ARN of the Secrets Manager secret containing Slack webhook URL | string | yes |
| ecs_cluster_name | Name of the ECS cluster | string | yes |
| tags | Tags to apply to all resources | map(string) | no |

## Outputs

| Name | Description |
|------|-------------|
| lambda_orchestrator_role_arn | ARN of the Lambda orchestrator IAM role |
| lambda_orchestrator_role_name | Name of the Lambda orchestrator IAM role |
| lambda_sync_role_arn | ARN of the Lambda sync worker IAM role |
| lambda_sync_role_name | Name of the Lambda sync worker IAM role |
| ecs_task_execution_role_arn | ARN of the ECS task execution IAM role |
| ecs_task_execution_role_name | Name of the ECS task execution IAM role |
| ecs_task_role_arn | ARN of the ECS task IAM role |
| ecs_task_role_name | Name of the ECS task IAM role |

## Security Considerations

- All roles follow the principle of least privilege
- Lambda roles are scoped to specific resource patterns
- ECS roles separate execution permissions from application permissions
- S3 access is limited to the specific bucket
- Secrets Manager access is limited to the specific webhook secret
- CloudWatch logs access is scoped to project-specific log groups