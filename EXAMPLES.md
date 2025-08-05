# Homebrew Bottles Sync - Examples and Reference

This document provides detailed examples of Slack notification formats, S3 bucket structure, API responses, and configuration examples for the Homebrew Bottles Sync System.

## Slack Notification Examples

The system sends various types of Slack notifications throughout the sync process. Here are examples of each notification type:

### 1. Sync Start Notification

**Scenario**: Weekly sync begins on schedule

```json
{
  "text": "🚀 Homebrew Bottles Sync Started",
  "blocks": [
    {
      "type": "header",
      "text": {
        "type": "plain_text",
        "text": "🚀 Homebrew Bottles Sync Started"
      }
    },
    {
      "type": "section",
      "fields": [
        {
          "type": "mrkdwn",
          "text": "*Environment:* prod"
        },
        {
          "type": "mrkdwn",
          "text": "*Date:* 2025-07-21"
        },
        {
          "type": "mrkdwn",
          "text": "*Estimated Bottles:* 1,247"
        },
        {
          "type": "mrkdwn",
          "text": "*Estimated Size:* 15.3 GB"
        },
        {
          "type": "mrkdwn",
          "text": "*Sync Method:* Lambda"
        },
        {
          "type": "mrkdwn",
          "text": "*Trigger:* Scheduled"
        }
      ]
    },
    {
      "type": "context",
      "elements": [
        {
          "type": "mrkdwn",
          "text": "Started at 2025-07-21 03:00:15 UTC"
        }
      ]
    }
  ]
}
```

**Rendered Output**:
```
🚀 Homebrew Bottles Sync Started

Environment: prod          Date: 2025-07-21
Estimated Bottles: 1,247   Estimated Size: 15.3 GB
Sync Method: Lambda        Trigger: Scheduled

Started at 2025-07-21 03:00:15 UTC
```

### 2. Large Download ECS Notification

**Scenario**: Download size exceeds Lambda threshold, routing to ECS

```json
{
  "text": "⚡ Large Download Detected - Routing to ECS",
  "blocks": [
    {
      "type": "header",
      "text": {
        "type": "plain_text",
        "text": "⚡ Large Download Detected"
      }
    },
    {
      "type": "section",
      "fields": [
        {
          "type": "mrkdwn",
          "text": "*Environment:* prod"
        },
        {
          "type": "mrkdwn",
          "text": "*Date:* 2025-07-21"
        },
        {
          "type": "mrkdwn",
          "text": "*Total Size:* 47.8 GB"
        },
        {
          "type": "mrkdwn",
          "text": "*Threshold:* 20 GB"
        },
        {
          "type": "mrkdwn",
          "text": "*Bottles Count:* 2,156"
        },
        {
          "type": "mrkdwn",
          "text": "*ECS Cluster:* homebrew-sync"
        }
      ]
    },
    {
      "type": "section",
      "text": {
        "type": "mrkdwn",
        "text": "Starting ECS Fargate task for large-scale download. Expected duration: 45-60 minutes."
      }
    }
  ]
}
```

### 3. Progress Update (ECS Only)

**Scenario**: ECS task provides progress updates during long downloads

```json
{
  "text": "⏳ Homebrew Sync Progress Update",
  "blocks": [
    {
      "type": "header",
      "text": {
        "type": "plain_text",
        "text": "⏳ Sync Progress Update"
      }
    },
    {
      "type": "section",
      "fields": [
        {
          "type": "mrkdwn",
          "text": "*Downloaded:* 456/2,156 bottles (21%)"
        },
        {
          "type": "mrkdwn",
          "text": "*Size Progress:* 8.3 GB / 47.8 GB"
        },
        {
          "type": "mrkdwn",
          "text": "*Duration:* 12 minutes"
        },
        {
          "type": "mrkdwn",
          "text": "*ETA:* 35 minutes"
        },
        {
          "type": "mrkdwn",
          "text": "*Speed:* 11.2 MB/s"
        },
        {
          "type": "mrkdwn",
          "text": "*Current:* downloading node@20.5.1"
        }
      ]
    },
    {
      "type": "section",
      "text": {
        "type": "mrkdwn",
        "text": "Progress bar: ████████░░░░░░░░░░░░░░░░░░░░ 21%"
      }
    }
  ]
}
```

### 4. Success Notification

**Scenario**: Sync completes successfully

```json
{
  "text": "✅ Homebrew Bottles Sync Complete",
  "blocks": [
    {
      "type": "header",
      "text": {
        "type": "plain_text",
        "text": "✅ Homebrew Bottles Sync Complete"
      }
    },
    {
      "type": "section",
      "fields": [
        {
          "type": "mrkdwn",
          "text": "*Environment:* prod"
        },
        {
          "type": "mrkdwn",
          "text": "*Date:* 2025-07-21"
        },
        {
          "type": "mrkdwn",
          "text": "*New Bottles:* 143"
        },
        {
          "type": "mrkdwn",
          "text": "*Skipped (Existing):* 2,013"
        },
        {
          "type": "mrkdwn",
          "text": "*Total Downloaded:* 3.2 GB"
        },
        {
          "type": "mrkdwn",
          "text": "*Duration:* 8 minutes 34 seconds"
        }
      ]
    },
    {
      "type": "section",
      "text": {
        "type": "mrkdwn",
        "text": "*S3 Location:* `s3://homebrew-bottles-prod/2025-07-21/`"
      }
    },
    {
      "type": "section",
      "text": {
        "type": "mrkdwn",
        "text": "*Top Downloaded Formulas:*\n• node@20.5.1 (arm64_sonoma, arm64_ventura, monterey)\n• python@3.11 (arm64_sonoma, arm64_ventura)\n• curl@8.2.1 (arm64_sonoma)\n• wget@1.21.4 (monterey)\n• git@2.41.0 (arm64_ventura)"
      }
    },
    {
      "type": "context",
      "elements": [
        {
          "type": "mrkdwn",
          "text": "Hash file updated successfully • Next sync: 2025-07-28 03:00 UTC"
        }
      ]
    }
  ]
}
```

### 5. Failure Notification

**Scenario**: Sync fails due to network timeout

```json
{
  "text": "❌ Homebrew Bottles Sync Failed",
  "blocks": [
    {
      "type": "header",
      "text": {
        "type": "plain_text",
        "text": "❌ Homebrew Bottles Sync Failed"
      }
    },
    {
      "type": "section",
      "fields": [
        {
          "type": "mrkdwn",
          "text": "*Environment:* prod"
        },
        {
          "type": "mrkdwn",
          "text": "*Date:* 2025-07-21"
        },
        {
          "type": "mrkdwn",
          "text": "*Error Type:* Network Timeout"
        },
        {
          "type": "mrkdwn",
          "text": "*Duration:* 14 minutes 23 seconds"
        },
        {
          "type": "mrkdwn",
          "text": "*Bottles Downloaded:* 89/1,247"
        },
        {
          "type": "mrkdwn",
          "text": "*Partial Size:* 1.8 GB"
        }
      ]
    },
    {
      "type": "section",
      "text": {
        "type": "mrkdwn",
        "text": "*Error Details:*\n```\nTimeout downloading curl-8.2.1.arm64_sonoma.bottle.tar.gz\nConnection timeout after 300 seconds\nRetried 3 times, all attempts failed\n```"
      }
    },
    {
      "type": "section",
      "text": {
        "type": "mrkdwn",
        "text": "*Troubleshooting:*\n• Check CloudWatch logs: `/aws/lambda/homebrew-sync-orchestrator`\n• Verify network connectivity and NAT Gateway status\n• Consider manual retry or investigate Homebrew API status"
      }
    },
    {
      "type": "actions",
      "elements": [
        {
          "type": "button",
          "text": {
            "type": "plain_text",
            "text": "View Logs"
          },
          "url": "https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups/log-group/$252Faws$252Flambda$252Fhomebrew-sync-orchestrator"
        },
        {
          "type": "button",
          "text": {
            "type": "plain_text",
            "text": "Retry Sync"
          },
          "url": "https://console.aws.amazon.com/lambda/home?region=us-east-1#/functions/homebrew-sync-orchestrator"
        }
      ]
    }
  ]
}
```

### 6. Warning Notification

**Scenario**: Partial failure with some bottles downloaded

```json
{
  "text": "⚠️ Homebrew Sync Completed with Warnings",
  "blocks": [
    {
      "type": "header",
      "text": {
        "type": "plain_text",
        "text": "⚠️ Sync Completed with Warnings"
      }
    },
    {
      "type": "section",
      "fields": [
        {
          "type": "mrkdwn",
          "text": "*Environment:* prod"
        },
        {
          "type": "mrkdwn",
          "text": "*Date:* 2025-07-21"
        },
        {
          "type": "mrkdwn",
          "text": "*Successful:* 1,198/1,247 bottles"
        },
        {
          "type": "mrkdwn",
          "text": "*Failed:* 49 bottles"
        },
        {
          "type": "mrkdwn",
          "text": "*Success Rate:* 96.1%"
        },
        {
          "type": "mrkdwn",
          "text": "*Duration:* 11 minutes 45 seconds"
        }
      ]
    },
    {
      "type": "section",
      "text": {
        "type": "mrkdwn",
        "text": "*Failed Downloads:*\n• opencv@4.8.0 (arm64_sonoma) - SHA mismatch\n• tensorflow@2.13.0 (monterey) - File not found\n• llvm@16.0.6 (arm64_ventura) - Connection timeout\n• ... and 46 others"
      }
    },
    {
      "type": "section",
      "text": {
        "type": "mrkdwn",
        "text": "*Recommendation:* Review failed downloads and consider manual retry for critical packages."
      }
    }
  ]
}
```

## S3 Bucket Structure Examples

### Complete Bucket Structure

```
s3://homebrew-bottles-prod/
├── bottles_hash.json                           # Global hash tracking file
├── 2025-07-14/                                # Weekly sync folders
│   ├── curl-8.2.1.arm64_sonoma.bottle.tar.gz
│   ├── curl-8.2.1.arm64_ventura.bottle.tar.gz
│   ├── curl-8.2.1.monterey.bottle.tar.gz
│   ├── node-20.5.1.arm64_sonoma.bottle.tar.gz
│   ├── node-20.5.1.arm64_ventura.bottle.tar.gz
│   ├── node-20.5.1.monterey.bottle.tar.gz
│   ├── python@3.11-3.11.4.arm64_sonoma.bottle.tar.gz
│   ├── python@3.11-3.11.4.arm64_ventura.bottle.tar.gz
│   ├── python@3.11-3.11.4.monterey.bottle.tar.gz
│   └── ... (1,200+ more bottles)
├── 2025-07-21/                                # Current week
│   ├── git-2.41.0.arm64_sonoma.bottle.tar.gz
│   ├── git-2.41.0.arm64_ventura.bottle.tar.gz
│   ├── git-2.41.0.monterey.bottle.tar.gz
│   ├── wget-1.21.4.arm64_sonoma.bottle.tar.gz
│   ├── wget-1.21.4.monterey.bottle.tar.gz
│   └── ... (143 new bottles this week)
├── 2025-07-28/                                # Future sync (empty until next run)
└── archive/                                   # Optional: older bottles moved by lifecycle policy
    ├── 2025-06-30/
    ├── 2025-06-23/
    └── ...
```

### Hash File Structure (`bottles_hash.json`)

```json
{
  "last_updated": "2025-07-21T03:08:42Z",
  "sync_version": "1.0.0",
  "total_bottles": 2156,
  "total_size_bytes": 52847392768,
  "platforms": ["arm64_sonoma", "arm64_ventura", "monterey"],
  "bottles": {
    "curl-8.2.1-arm64_sonoma": {
      "sha256": "a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456",
      "download_date": "2025-07-21",
      "file_size": 1048576,
      "formula_name": "curl",
      "formula_version": "8.2.1",
      "platform": "arm64_sonoma",
      "url": "https://ghcr.io/v2/homebrew/core/curl/blobs/sha256:a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456",
      "s3_key": "2025-07-21/curl-8.2.1.arm64_sonoma.bottle.tar.gz"
    },
    "curl-8.2.1-arm64_ventura": {
      "sha256": "b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef1234567a",
      "download_date": "2025-07-21",
      "file_size": 1052672,
      "formula_name": "curl",
      "formula_version": "8.2.1",
      "platform": "arm64_ventura",
      "url": "https://ghcr.io/v2/homebrew/core/curl/blobs/sha256:b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef1234567a",
      "s3_key": "2025-07-21/curl-8.2.1.arm64_ventura.bottle.tar.gz"
    },
    "node-20.5.1-arm64_sonoma": {
      "sha256": "c3d4e5f6789012345678901234567890abcdef1234567890abcdef1234567ab2",
      "download_date": "2025-07-14",
      "file_size": 15728640,
      "formula_name": "node",
      "formula_version": "20.5.1",
      "platform": "arm64_sonoma",
      "url": "https://ghcr.io/v2/homebrew/core/node/blobs/sha256:c3d4e5f6789012345678901234567890abcdef1234567890abcdef1234567ab2",
      "s3_key": "2025-07-14/node-20.5.1.arm64_sonoma.bottle.tar.gz"
    }
  },
  "statistics": {
    "by_platform": {
      "arm64_sonoma": {
        "count": 1247,
        "total_size_bytes": 18234567890
      },
      "arm64_ventura": {
        "count": 1198,
        "total_size_bytes": 17456789012
      },
      "monterey": {
        "count": 711,
        "total_size_bytes": 17156035866
      }
    },
    "by_date": {
      "2025-07-21": {
        "count": 143,
        "total_size_bytes": 3456789012
      },
      "2025-07-14": {
        "count": 1247,
        "total_size_bytes": 16234567890
      },
      "2025-07-07": {
        "count": 766,
        "total_size_bytes": 33156035866
      }
    }
  }
}
```

### S3 Object Metadata Examples

Each bottle file in S3 includes metadata:

```bash
# Example: curl bottle metadata
aws s3api head-object --bucket homebrew-bottles-prod --key 2025-07-21/curl-8.2.1.arm64_sonoma.bottle.tar.gz
```

```json
{
    "AcceptRanges": "bytes",
    "LastModified": "2025-07-21T03:05:23+00:00",
    "ContentLength": 1048576,
    "ETag": "\"a1b2c3d4e5f6789012345678901234567890abcdef\"",
    "ContentType": "application/gzip",
    "ServerSideEncryption": "AES256",
    "Metadata": {
        "formula-name": "curl",
        "formula-version": "8.2.1",
        "platform": "arm64_sonoma",
        "download-date": "2025-07-21",
        "sha256": "a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456",
        "sync-version": "1.0.0",
        "homebrew-api-url": "https://formulae.brew.sh/api/formula/curl.json"
    }
}
```

## Homebrew API Response Examples

### Formula List Response

```json
[
  {
    "name": "curl",
    "full_name": "curl",
    "tap": "homebrew/core",
    "oldname": null,
    "aliases": [],
    "versioned_formulae": [],
    "desc": "Get a file from an HTTP, HTTPS or FTP server",
    "license": "curl",
    "homepage": "https://curl.se",
    "versions": {
      "stable": "8.2.1",
      "head": "HEAD",
      "bottle": true
    },
    "urls": {
      "stable": {
        "url": "https://curl.se/download/curl-8.2.1.tar.bz2",
        "tag": null,
        "revision": null,
        "checksum": "dd322f6bd0a20e6cebdfd388f69e98c3d183bed792cf4713c8a7ef498cba4894"
      }
    },
    "revision": 0,
    "version_scheme": 0,
    "bottle": {
      "stable": {
        "rebuild": 0,
        "root_url": "https://ghcr.io/v2/homebrew/core/curl",
        "files": {
          "arm64_sonoma": {
            "cellar": "/opt/homebrew/Cellar",
            "url": "https://ghcr.io/v2/homebrew/core/curl/blobs/sha256:a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456",
            "sha256": "a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456"
          },
          "arm64_ventura": {
            "cellar": "/opt/homebrew/Cellar",
            "url": "https://ghcr.io/v2/homebrew/core/curl/blobs/sha256:b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef1234567a",
            "sha256": "b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef1234567a"
          },
          "monterey": {
            "cellar": "/opt/homebrew/Cellar",
            "url": "https://ghcr.io/v2/homebrew/core/curl/blobs/sha256:c3d4e5f6789012345678901234567890abcdef1234567890abcdef1234567ab2",
            "sha256": "c3d4e5f6789012345678901234567890abcdef1234567890abcdef1234567ab2"
          }
        }
      }
    },
    "dependencies": ["brotli", "libidn2", "libnghttp2", "libssh2", "openssl@3", "rtmpdump", "zstd"],
    "build_dependencies": ["pkg-config"],
    "conflicts_with": [],
    "conflicts_with_reasons": [],
    "link_overwrite": [],
    "caveats": null,
    "installed": [],
    "linked_keg": null,
    "pinned": false,
    "outdated": false,
    "deprecated": false,
    "deprecation_date": null,
    "deprecation_reason": null,
    "disabled": false,
    "disable_date": null,
    "disable_reason": null,
    "post_install_defined": false,
    "service": null,
    "tap_git_head": "4eeae4ea50839e967536ba646d5e0ed6fbcbad7f",
    "ruby_source_path": "Formula/c/curl.rb",
    "ruby_source_checksum": {
      "sha256": "83abc123def456789012345678901234567890abcdef1234567890abcdef12345"
    }
  }
]
```

## Configuration Examples

### Terraform Variables Examples

#### Production Configuration (`prod.tfvars`)

```hcl
# Basic Configuration
project_name = "homebrew-bottles-sync"
environment  = "prod"
aws_region   = "us-east-1"

# Lambda Configuration
lambda_layer_zip_path             = "../build/layer.zip"
lambda_orchestrator_zip_path      = "../build/orchestrator.zip"
lambda_sync_zip_path              = "../build/sync.zip"
lambda_orchestrator_memory_size   = 1024
lambda_sync_memory_size           = 3008
lambda_orchestrator_timeout       = 300
lambda_sync_timeout               = 900

# ECS Configuration
ecs_container_image               = "123456789012.dkr.ecr.us-east-1.amazonaws.com/homebrew-bottles-sync:latest"
ecs_task_cpu                      = 4096
ecs_task_memory                   = 16384
ecs_ephemeral_storage_size_gb     = 200
ecs_enable_fargate_spot           = false

# Storage Configuration
s3_bucket_name                    = "homebrew-bottles-prod"
enable_s3_versioning              = true
s3_lifecycle_expiration_days      = 365
s3_noncurrent_version_expiration_days = 90

# EFS Configuration (for ECS)
enable_efs_storage                = true
efs_performance_mode              = "generalPurpose"
efs_throughput_mode               = "provisioned"
efs_provisioned_throughput        = 500

# Scheduling
schedule_expression               = "cron(0 3 ? * SUN *)"  # Sunday 3 AM UTC
schedule_enabled                  = true

# Sync Configuration
size_threshold_gb                 = 20
target_platforms                  = ["arm64_sonoma", "arm64_ventura", "monterey"]
max_concurrent_downloads          = 10
download_timeout_seconds          = 300
retry_attempts                    = 3

# Notifications
slack_webhook_url                 = "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX"
slack_channel                     = "#homebrew-sync"
slack_username                    = "Homebrew Sync Bot"
enable_sns_notifications          = true
notification_email_addresses      = ["devops@company.com", "alerts@company.com"]

# Monitoring
enable_detailed_monitoring        = true
enable_xray_tracing               = true
log_retention_days                = 30
lambda_error_rate_threshold       = 5
ecs_cpu_utilization_threshold     = 80
monthly_budget_limit              = 500

# Security
enable_vpc_endpoints              = true
enable_secrets_rotation           = false
kms_key_id                        = ""

# Tags
tags = {
  Environment   = "prod"
  Project       = "homebrew-bottles-sync"
  Team          = "devops"
  CostCenter    = "engineering"
  Backup        = "required"
  Compliance    = "required"
}
```

#### Development Configuration (`dev.tfvars`)

```hcl
# Basic Configuration
project_name = "homebrew-bottles-sync"
environment  = "dev"
aws_region   = "us-west-2"

# Smaller resources for cost savings
lambda_orchestrator_memory_size   = 512
lambda_sync_memory_size           = 1024
ecs_task_cpu                      = 1024
ecs_task_memory                   = 4096
ecs_ephemeral_storage_size_gb     = 50
ecs_enable_fargate_spot           = true

# More frequent testing schedule
schedule_expression               = "cron(0 */6 * * ? *)"  # Every 6 hours

# Smaller threshold for testing ECS routing
size_threshold_gb                 = 5

# Shorter retention for cost savings
log_retention_days                = 7
s3_lifecycle_expiration_days      = 30

# Development-specific settings
enable_detailed_monitoring        = false
enable_xray_tracing               = false
enable_efs_storage                = false
monthly_budget_limit              = 50

# Slack notifications to dev channel
slack_channel                     = "#homebrew-sync-dev"
enable_sns_notifications          = false

tags = {
  Environment = "dev"
  Project     = "homebrew-bottles-sync"
  Team        = "devops"
  AutoShutdown = "enabled"
}
```

### Environment Variables Examples

#### Lambda Function Environment Variables

```bash
# Orchestrator Lambda
S3_BUCKET_NAME=homebrew-bottles-prod
SLACK_WEBHOOK_SECRET_NAME=homebrew-sync/slack-webhook
SIZE_THRESHOLD_GB=20
AWS_REGION=us-east-1
ECS_CLUSTER_NAME=homebrew-sync
ECS_TASK_DEFINITION=homebrew-bottles-sync:1
LAMBDA_SYNC_FUNCTION=homebrew-sync-worker
ECS_SUBNETS=subnet-12345678,subnet-87654321
ECS_SECURITY_GROUPS=sg-abcdef123
LOG_LEVEL=INFO
TARGET_PLATFORMS=arm64_sonoma,arm64_ventura,monterey
MAX_CONCURRENT_DOWNLOADS=10
RETRY_ATTEMPTS=3

# Sync Worker Lambda
S3_BUCKET_NAME=homebrew-bottles-prod
SLACK_WEBHOOK_SECRET_NAME=homebrew-sync/slack-webhook
AWS_REGION=us-east-1
LOG_LEVEL=INFO
DOWNLOAD_TIMEOUT_SECONDS=300
TEMP_DIR=/tmp/bottles
```

#### ECS Task Environment Variables

```bash
# ECS Container Environment
S3_BUCKET_NAME=homebrew-bottles-prod
SLACK_WEBHOOK_SECRET_NAME=homebrew-sync/slack-webhook
AWS_REGION=us-east-1
LOG_LEVEL=INFO
DOWNLOAD_CONCURRENCY=5
TEMP_STORAGE_PATH=/tmp/bottles
EFS_MOUNT_PATH=/mnt/efs
PROGRESS_UPDATE_INTERVAL=300
BATCH_SIZE=50
MAX_DOWNLOAD_SIZE_GB=100
RETRY_ATTEMPTS=3
RETRY_DELAY_SECONDS=30
```

## API Integration Examples

### Manual Sync Trigger

```bash
# Trigger via AWS CLI
aws events put-events \
  --entries '[
    {
      "Source": "homebrew.sync",
      "DetailType": "Manual Sync Trigger",
      "Detail": "{\"trigger_type\":\"manual\",\"requested_by\":\"admin@company.com\",\"priority\":\"high\"}"
    }
  ]'

# Trigger specific formulas
aws events put-events \
  --entries '[
    {
      "Source": "homebrew.sync",
      "DetailType": "Selective Sync",
      "Detail": "{\"formula_names\":[\"curl\",\"node\",\"python@3.11\"],\"platforms\":[\"arm64_sonoma\"],\"force_download\":true}"
    }
  ]'
```

### Lambda Direct Invocation

```bash
# Invoke orchestrator directly
aws lambda invoke \
  --function-name homebrew-sync-orchestrator \
  --payload '{
    "source": "manual",
    "sync_type": "full",
    "force_rebuild_hash": false,
    "notification_channel": "#homebrew-sync-manual"
  }' \
  response.json

# Invoke sync worker directly (for testing)
aws lambda invoke \
  --function-name homebrew-sync-worker \
  --payload '{
    "formulas": [
      {
        "name": "curl",
        "version": "8.2.1",
        "bottles": {
          "arm64_sonoma": {
            "url": "https://ghcr.io/v2/homebrew/core/curl/blobs/sha256:abc123...",
            "sha256": "abc123...",
            "size": 1048576
          }
        }
      }
    ],
    "sync_date": "2025-07-21"
  }' \
  response.json
```

## Monitoring Examples

### CloudWatch Dashboard JSON

```json
{
  "widgets": [
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["AWS/Lambda", "Invocations", "FunctionName", "homebrew-sync-orchestrator"],
          [".", "Errors", ".", "."],
          [".", "Duration", ".", "."]
        ],
        "period": 300,
        "stat": "Sum",
        "region": "us-east-1",
        "title": "Lambda Orchestrator Metrics"
      }
    },
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["AWS/ECS", "CPUUtilization", "ServiceName", "homebrew-bottles-sync", "ClusterName", "homebrew-sync"],
          [".", "MemoryUtilization", ".", ".", ".", "."]
        ],
        "period": 300,
        "stat": "Average",
        "region": "us-east-1",
        "title": "ECS Task Resource Utilization"
      }
    },
    {
      "type": "log",
      "properties": {
        "query": "SOURCE '/aws/lambda/homebrew-sync-orchestrator'\n| fields @timestamp, @message\n| filter @message like /Downloaded/\n| sort @timestamp desc\n| limit 20",
        "region": "us-east-1",
        "title": "Recent Downloads"
      }
    }
  ]
}
```

### Custom Metrics Examples

```python
import boto3

cloudwatch = boto3.client('cloudwatch')

# Publish custom metrics
cloudwatch.put_metric_data(
    Namespace='HomebrewSync',
    MetricData=[
        {
            'MetricName': 'BottlesDownloaded',
            'Value': 143,
            'Unit': 'Count',
            'Dimensions': [
                {'Name': 'Environment', 'Value': 'prod'},
                {'Name': 'SyncDate', 'Value': '2025-07-21'}
            ]
        },
        {
            'MetricName': 'SyncDuration',
            'Value': 514,  # seconds
            'Unit': 'Seconds',
            'Dimensions': [
                {'Name': 'Environment', 'Value': 'prod'},
                {'Name': 'SyncType', 'Value': 'lambda'}
            ]
        },
        {
            'MetricName': 'DownloadSize',
            'Value': 3456789012,  # bytes
            'Unit': 'Bytes',
            'Dimensions': [
                {'Name': 'Environment', 'Value': 'prod'}
            ]
        }
    ]
)
```

This comprehensive examples document provides detailed reference material for understanding the system's behavior, configuration options, and integration patterns.