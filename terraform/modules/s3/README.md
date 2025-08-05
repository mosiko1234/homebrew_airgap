# S3 Module for Homebrew Bottles Sync

This Terraform module creates an S3 bucket optimized for storing Homebrew bottles with appropriate security, lifecycle policies, and IAM permissions.

## Features

- **S3 Bucket with Versioning**: Protects against accidental deletions and corruption
- **Server-Side Encryption**: AES256 encryption for all objects
- **Lifecycle Policies**: Cost optimization through storage class transitions and automatic cleanup
- **IAM Policies**: Separate policies for Lambda and ECS access with least privilege
- **Security**: Public access blocked, encryption enforced
- **Monitoring**: CloudWatch log group for access logging

## Usage

```hcl
module "s3" {
  source = "./modules/s3"

  bucket_name        = "my-homebrew-bottles-bucket"
  environment        = "prod"
  lambda_role_arns   = [aws_iam_role.lambda_orchestrator.arn, aws_iam_role.lambda_sync.arn]
  ecs_role_arns      = [aws_iam_role.ecs_task.arn]
  enable_versioning  = true
  
  # Cost optimization settings
  lifecycle_expiration_days           = 90
  noncurrent_version_expiration_days  = 30
}
```

## Storage Structure

The bucket is designed to store bottles in the following structure:

```
s3://bucket-name/
├── bottles_hash.json                    # Global hash tracking file
├── 2025-07-21/                         # Date-based folders
│   ├── curl-8.0.0.arm64_sonoma.bottle.tar.gz
│   ├── curl-8.0.0.arm64_ventura.bottle.tar.gz
│   └── curl-8.0.0.monterey.bottle.tar.gz
└── 2025-07-28/
    └── ...
```

## Lifecycle Policies

The module implements several lifecycle rules for cost optimization:

1. **Bottles Lifecycle**: 
   - Transition to Standard-IA after 30 days
   - Transition to Glacier after 90 days
   - Delete after configurable expiration period

2. **Hash File Lifecycle**: 
   - Special handling for `bottles_hash.json`
   - Keeps more versions (90 days) for recovery

3. **Multipart Upload Cleanup**: 
   - Automatically cleans up incomplete uploads after 7 days

## Security Features

- **Public Access Blocked**: All public access is explicitly blocked
- **Encryption Enforced**: All objects must be encrypted with AES256
- **IAM Policies**: Separate least-privilege policies for Lambda and ECS
- **Bucket Policy**: Additional layer of access control

## Variables

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| bucket_name | Name of the S3 bucket | `string` | n/a | yes |
| environment | Environment name | `string` | `"prod"` | no |
| lambda_role_arns | Lambda execution role ARNs | `list(string)` | `[]` | no |
| ecs_role_arns | ECS task role ARNs | `list(string)` | `[]` | no |
| enable_versioning | Enable bucket versioning | `bool` | `true` | no |
| lifecycle_expiration_days | Days before object expiration | `number` | `90` | no |
| noncurrent_version_expiration_days | Days before noncurrent version expiration | `number` | `30` | no |

## Outputs

| Name | Description |
|------|-------------|
| bucket_name | Name of the S3 bucket |
| bucket_arn | ARN of the S3 bucket |
| bucket_domain_name | Domain name of the S3 bucket |
| bucket_regional_domain_name | Regional domain name of the S3 bucket |
| lambda_s3_policy_arn | ARN of the Lambda S3 access policy |
| ecs_s3_policy_arn | ARN of the ECS S3 access policy |
| bucket_versioning_status | Versioning status of the bucket |

## IAM Permissions

### Lambda Functions
- `s3:ListBucket`, `s3:GetBucketLocation`, `s3:GetBucketVersioning`
- `s3:GetObject`, `s3:GetObjectVersion`, `s3:PutObject`, `s3:DeleteObject`, `s3:RestoreObject`

### ECS Tasks
- Same as Lambda functions plus:
- `s3:AbortMultipartUpload`, `s3:ListMultipartUploadParts`

## Requirements

| Name | Version |
|------|---------|
| terraform | >= 1.0 |
| aws | ~> 5.0 |

## Cost Considerations

- Standard storage for new objects
- Automatic transition to Standard-IA after 30 days (45% cost reduction)
- Automatic transition to Glacier after 90 days (68% cost reduction)
- Automatic cleanup of incomplete multipart uploads
- Configurable object expiration to prevent indefinite storage costs