# S3 Module for Homebrew Bottles Sync
# Creates S3 bucket with versioning, lifecycle policies, and IAM policies

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# Variables are defined in variables.tf

# S3 Bucket
resource "aws_s3_bucket" "homebrew_bottles" {
  bucket = var.bucket_name

  tags = {
    Name        = var.bucket_name
    Environment = var.environment
    Purpose     = "homebrew-bottles-sync"
    ManagedBy   = "terraform"
  }
}

# S3 Bucket Versioning
resource "aws_s3_bucket_versioning" "homebrew_bottles" {
  bucket = aws_s3_bucket.homebrew_bottles.id
  versioning_configuration {
    status = var.enable_versioning ? "Enabled" : "Disabled"
  }
}

# S3 Bucket Server-Side Encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "homebrew_bottles" {
  bucket = aws_s3_bucket.homebrew_bottles.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

# S3 Bucket Public Access Block
resource "aws_s3_bucket_public_access_block" "homebrew_bottles" {
  bucket = aws_s3_bucket.homebrew_bottles.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# S3 Bucket Lifecycle Configuration
resource "aws_s3_bucket_lifecycle_configuration" "homebrew_bottles" {
  bucket = aws_s3_bucket.homebrew_bottles.id

  rule {
    id     = "bottles_lifecycle"
    status = "Enabled"

    # Delete old bottle files after specified days
    expiration {
      days = var.lifecycle_expiration_days
    }

    # Delete noncurrent versions after specified days
    noncurrent_version_expiration {
      noncurrent_days = var.noncurrent_version_expiration_days
    }

    # Transition to IA after 30 days for cost optimization
    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    # Transition to Glacier after 90 days for long-term storage
    transition {
      days          = 90
      storage_class = "GLACIER"
    }
  }

  rule {
    id     = "hash_file_lifecycle"
    status = "Enabled"

    # Special handling for bottles_hash.json - keep more versions
    filter {
      prefix = "bottles_hash.json"
    }

    noncurrent_version_expiration {
      noncurrent_days = 90
    }
  }

  rule {
    id     = "multipart_upload_cleanup"
    status = "Enabled"

    # Clean up incomplete multipart uploads after 7 days
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}
# S3 Bucket Policy for Lambda and ECS Access
resource "aws_s3_bucket_policy" "homebrew_bottles" {
  bucket = aws_s3_bucket.homebrew_bottles.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowLambdaAccess"
        Effect = "Allow"
        Principal = {
          AWS = var.lambda_role_arns
        }
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.homebrew_bottles.arn,
          "${aws_s3_bucket.homebrew_bottles.arn}/*"
        ]
        Condition = {
          StringEquals = {
            "s3:x-amz-server-side-encryption" = "AES256"
          }
        }
      },
      {
        Sid    = "AllowECSAccess"
        Effect = "Allow"
        Principal = {
          AWS = var.ecs_role_arns
        }
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.homebrew_bottles.arn,
          "${aws_s3_bucket.homebrew_bottles.arn}/*"
        ]
        Condition = {
          StringEquals = {
            "s3:x-amz-server-side-encryption" = "AES256"
          }
        }
      }
    ]
  })

  depends_on = [aws_s3_bucket_public_access_block.homebrew_bottles]
}

# IAM Policy Document for Lambda Functions
data "aws_iam_policy_document" "lambda_s3_access" {
  statement {
    sid    = "S3BucketAccess"
    effect = "Allow"
    actions = [
      "s3:ListBucket",
      "s3:GetBucketLocation",
      "s3:GetBucketVersioning"
    ]
    resources = [aws_s3_bucket.homebrew_bottles.arn]
  }

  statement {
    sid    = "S3ObjectAccess"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:GetObjectVersion",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:RestoreObject"
    ]
    resources = ["${aws_s3_bucket.homebrew_bottles.arn}/*"]

    condition {
      test     = "StringEquals"
      variable = "s3:x-amz-server-side-encryption"
      values   = ["AES256"]
    }
  }
}

# IAM Policy Document for ECS Tasks
data "aws_iam_policy_document" "ecs_s3_access" {
  statement {
    sid    = "S3BucketAccess"
    effect = "Allow"
    actions = [
      "s3:ListBucket",
      "s3:GetBucketLocation",
      "s3:GetBucketVersioning"
    ]
    resources = [aws_s3_bucket.homebrew_bottles.arn]
  }

  statement {
    sid    = "S3ObjectAccess"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:GetObjectVersion",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:RestoreObject"
    ]
    resources = ["${aws_s3_bucket.homebrew_bottles.arn}/*"]

    condition {
      test     = "StringEquals"
      variable = "s3:x-amz-server-side-encryption"
      values   = ["AES256"]
    }
  }

  statement {
    sid    = "S3MultipartUpload"
    effect = "Allow"
    actions = [
      "s3:AbortMultipartUpload",
      "s3:ListMultipartUploadParts"
    ]
    resources = ["${aws_s3_bucket.homebrew_bottles.arn}/*"]
  }
}

# IAM Policy for Lambda Functions
resource "aws_iam_policy" "lambda_s3_access" {
  name_prefix = "homebrew-lambda-s3-access-"
  description = "IAM policy for Lambda functions to access Homebrew bottles S3 bucket"
  policy      = data.aws_iam_policy_document.lambda_s3_access.json

  tags = {
    Name        = "homebrew-lambda-s3-access"
    Environment = var.environment
    Purpose     = "homebrew-bottles-sync"
    ManagedBy   = "terraform"
  }
}

# IAM Policy for ECS Tasks
resource "aws_iam_policy" "ecs_s3_access" {
  name_prefix = "homebrew-ecs-s3-access-"
  description = "IAM policy for ECS tasks to access Homebrew bottles S3 bucket"
  policy      = data.aws_iam_policy_document.ecs_s3_access.json

  tags = {
    Name        = "homebrew-ecs-s3-access"
    Environment = var.environment
    Purpose     = "homebrew-bottles-sync"
    ManagedBy   = "terraform"
  }
}

# CloudWatch Log Group for S3 access logs (optional)
resource "aws_cloudwatch_log_group" "s3_access_logs" {
  name              = "/aws/s3/${var.bucket_name}/access-logs"
  retention_in_days = 30

  tags = {
    Name        = "s3-access-logs"
    Environment = var.environment
    Purpose     = "homebrew-bottles-sync"
    ManagedBy   = "terraform"
  }
}

# Outputs are defined in outputs.tf