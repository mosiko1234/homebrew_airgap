# ECS Module for Homebrew Bottles Sync System
# Creates ECS cluster, task definition, and supporting resources for large-scale bottle downloads

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# ECS Cluster
resource "aws_ecs_cluster" "homebrew_sync" {
  name = var.cluster_name

  setting {
    name  = "containerInsights"
    value = var.enable_container_insights ? "enabled" : "disabled"
  }

  tags = var.tags
}

# ECS Cluster Capacity Providers
resource "aws_ecs_cluster_capacity_providers" "homebrew_sync" {
  cluster_name = aws_ecs_cluster.homebrew_sync.name

  capacity_providers = ["FARGATE", "FARGATE_SPOT"]

  default_capacity_provider_strategy {
    base              = var.fargate_base_capacity
    weight            = var.fargate_weight
    capacity_provider = "FARGATE"
  }

  dynamic "default_capacity_provider_strategy" {
    for_each = var.enable_fargate_spot ? [1] : []
    content {
      base              = var.fargate_spot_base_capacity
      weight            = var.fargate_spot_weight
      capacity_provider = "FARGATE_SPOT"
    }
  }
}

# CloudWatch Log Group for ECS Tasks
resource "aws_cloudwatch_log_group" "ecs_sync_logs" {
  name              = "/aws/ecs/${var.project_name}-sync"
  retention_in_days = var.log_retention_days

  tags = var.tags
}

# EFS File System for temporary storage
resource "aws_efs_file_system" "homebrew_sync" {
  count = var.enable_efs ? 1 : 0

  creation_token   = "${var.project_name}-efs"
  performance_mode = var.efs_performance_mode
  throughput_mode  = var.efs_throughput_mode

  dynamic "provisioned_throughput_in_mibps" {
    for_each = var.efs_throughput_mode == "provisioned" ? [var.efs_provisioned_throughput] : []
    content {
      provisioned_throughput_in_mibps = provisioned_throughput_in_mibps.value
    }
  }

  encrypted = true

  lifecycle_policy {
    transition_to_ia = var.efs_transition_to_ia
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-efs"
  })
}

# EFS Mount Targets
resource "aws_efs_mount_target" "homebrew_sync" {
  count = var.enable_efs ? length(var.private_subnet_ids) : 0

  file_system_id  = aws_efs_file_system.homebrew_sync[0].id
  subnet_id       = var.private_subnet_ids[count.index]
  security_groups = [aws_security_group.efs[0].id]
}

# Security Group for EFS
resource "aws_security_group" "efs" {
  count = var.enable_efs ? 1 : 0

  name_prefix = "${var.project_name}-efs-"
  vpc_id      = var.vpc_id
  description = "Security group for EFS file system"

  ingress {
    description     = "NFS from ECS tasks"
    from_port       = 2049
    to_port         = 2049
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_tasks.id]
  }

  egress {
    description = "All outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-efs-sg"
  })

  lifecycle {
    create_before_destroy = true
  }
}

# Security Group for ECS Tasks
resource "aws_security_group" "ecs_tasks" {
  name_prefix = "${var.project_name}-ecs-tasks-"
  vpc_id      = var.vpc_id
  description = "Security group for ECS sync tasks"

  # Outbound internet access for downloading bottles
  egress {
    description = "HTTPS outbound"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "HTTP outbound"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # NFS access to EFS (if enabled)
  dynamic "egress" {
    for_each = var.enable_efs ? [1] : []
    content {
      description     = "NFS to EFS"
      from_port       = 2049
      to_port         = 2049
      protocol        = "tcp"
      security_groups = [aws_security_group.efs[0].id]
    }
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-ecs-tasks-sg"
  })

  lifecycle {
    create_before_destroy = true
  }
}

# ECS Task Definition
resource "aws_ecs_task_definition" "sync_worker" {
  family                   = "${var.project_name}-sync-task"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  execution_role_arn       = var.task_execution_role_arn
  task_role_arn            = var.task_role_arn

  # Ephemeral storage configuration
  ephemeral_storage {
    size_in_gib = var.ephemeral_storage_size_gb
  }

  container_definitions = jsonencode([
    {
      name  = "homebrew-sync"
      image = var.container_image

      # Resource limits
      cpu    = var.task_cpu
      memory = var.task_memory

      # Essential container
      essential = true

      # Environment variables
      environment = concat([
        {
          name  = "S3_BUCKET_NAME"
          value = var.s3_bucket_name
        },
        {
          name  = "AWS_REGION"
          value = var.aws_region
        },
        {
          name  = "TARGET_PLATFORMS"
          value = join(",", var.target_platforms)
        },
        {
          name  = "SIZE_THRESHOLD_GB"
          value = tostring(var.size_threshold_gb)
        },
        {
          name  = "MAX_CONCURRENT_DOWNLOADS"
          value = tostring(var.max_concurrent_downloads)
        },
        {
          name  = "RETRY_ATTEMPTS"
          value = tostring(var.retry_attempts)
        },
        {
          name  = "LOG_LEVEL"
          value = var.log_level
        },
        {
          name  = "PROGRESS_REPORT_INTERVAL"
          value = tostring(var.progress_report_interval)
        },
        {
          name  = "WORK_DIR"
          value = var.enable_efs ? "/mnt/efs/homebrew-sync" : "/tmp/homebrew-sync"
        }
      ], var.external_hash_file_s3_key != null ? [
        {
          name  = "EXTERNAL_HASH_FILE_S3_KEY"
          value = var.external_hash_file_s3_key
        }
      ] : [], var.external_hash_file_s3_bucket != null ? [
        {
          name  = "EXTERNAL_HASH_FILE_S3_BUCKET"
          value = var.external_hash_file_s3_bucket
        }
      ] : [], var.external_hash_file_url != null ? [
        {
          name  = "EXTERNAL_HASH_FILE_URL"
          value = var.external_hash_file_url
        }
      ] : [])

      # Secrets from AWS Secrets Manager
      secrets = [
        {
          name      = "SLACK_WEBHOOK_SECRET_NAME"
          valueFrom = var.slack_webhook_secret_arn
        }
      ]

      # Mount points for EFS (if enabled)
      mountPoints = var.enable_efs ? [
        {
          sourceVolume  = "efs-storage"
          containerPath = "/mnt/efs"
          readOnly      = false
        }
      ] : []

      # CloudWatch logging
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ecs_sync_logs.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }

      # Health check
      healthCheck = {
        command = [
          "CMD-SHELL",
          "python -c 'import sys; sys.exit(0)' || exit 1"
        ]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }

      # Stop timeout
      stopTimeout = var.stop_timeout
    }
  ])

  # EFS volume configuration (if enabled)
  dynamic "volume" {
    for_each = var.enable_efs ? [1] : []
    content {
      name = "efs-storage"

      efs_volume_configuration {
        file_system_id          = aws_efs_file_system.homebrew_sync[0].id
        root_directory          = "/"
        transit_encryption      = "ENABLED"
        transit_encryption_port = 2049

        authorization_config {
          access_point_id = aws_efs_access_point.homebrew_sync[0].id
          iam             = "ENABLED"
        }
      }
    }
  }

  tags = var.tags
}

# EFS Access Point (if EFS is enabled)
resource "aws_efs_access_point" "homebrew_sync" {
  count = var.enable_efs ? 1 : 0

  file_system_id = aws_efs_file_system.homebrew_sync[0].id

  posix_user {
    gid = 1000
    uid = 1000
  }

  root_directory {
    path = "/homebrew-sync"
    creation_info {
      owner_gid   = 1000
      owner_uid   = 1000
      permissions = "755"
    }
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-efs-access-point"
  })
}

# CloudWatch Alarms for monitoring
resource "aws_cloudwatch_metric_alarm" "task_cpu_high" {
  count = var.enable_cloudwatch_alarms ? 1 : 0

  alarm_name          = "${var.project_name}-ecs-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "This metric monitors ECS task CPU utilization"
  alarm_actions       = var.alarm_sns_topic_arn != "" ? [var.alarm_sns_topic_arn] : []

  dimensions = {
    ServiceName = aws_ecs_task_definition.sync_worker.family
    ClusterName = aws_ecs_cluster.homebrew_sync.name
  }

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "task_memory_high" {
  count = var.enable_cloudwatch_alarms ? 1 : 0

  alarm_name          = "${var.project_name}-ecs-memory-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "MemoryUtilization"
  namespace           = "AWS/ECS"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "This metric monitors ECS task memory utilization"
  alarm_actions       = var.alarm_sns_topic_arn != "" ? [var.alarm_sns_topic_arn] : []

  dimensions = {
    ServiceName = aws_ecs_task_definition.sync_worker.family
    ClusterName = aws_ecs_cluster.homebrew_sync.name
  }

  tags = var.tags
}