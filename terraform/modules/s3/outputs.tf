# Outputs for S3 Module

output "bucket_name" {
  description = "Name of the S3 bucket"
  value       = aws_s3_bucket.homebrew_bottles.id
}

output "bucket_arn" {
  description = "ARN of the S3 bucket"
  value       = aws_s3_bucket.homebrew_bottles.arn
}

output "bucket_domain_name" {
  description = "Domain name of the S3 bucket"
  value       = aws_s3_bucket.homebrew_bottles.bucket_domain_name
}

output "bucket_regional_domain_name" {
  description = "Regional domain name of the S3 bucket"
  value       = aws_s3_bucket.homebrew_bottles.bucket_regional_domain_name
}

output "bucket_region" {
  description = "Region of the S3 bucket"
  value       = aws_s3_bucket.homebrew_bottles.region
}

output "lambda_s3_policy_arn" {
  description = "ARN of the IAM policy for Lambda S3 access"
  value       = aws_iam_policy.lambda_s3_access.arn
}

output "ecs_s3_policy_arn" {
  description = "ARN of the IAM policy for ECS S3 access"
  value       = aws_iam_policy.ecs_s3_access.arn
}

output "lambda_s3_policy_name" {
  description = "Name of the IAM policy for Lambda S3 access"
  value       = aws_iam_policy.lambda_s3_access.name
}

output "ecs_s3_policy_name" {
  description = "Name of the IAM policy for ECS S3 access"
  value       = aws_iam_policy.ecs_s3_access.name
}

output "bucket_versioning_status" {
  description = "Versioning status of the S3 bucket"
  value       = aws_s3_bucket_versioning.homebrew_bottles.versioning_configuration[0].status
}

output "bucket_encryption_algorithm" {
  description = "Server-side encryption algorithm used by the bucket"
  value       = aws_s3_bucket_server_side_encryption_configuration.homebrew_bottles.rule[0].apply_server_side_encryption_by_default.sse_algorithm
}

output "cloudwatch_log_group_name" {
  description = "Name of the CloudWatch log group for S3 access logs"
  value       = aws_cloudwatch_log_group.s3_access_logs.name
}

output "cloudwatch_log_group_arn" {
  description = "ARN of the CloudWatch log group for S3 access logs"
  value       = aws_cloudwatch_log_group.s3_access_logs.arn
}