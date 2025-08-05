# CloudWatch Monitoring Module for Homebrew Bottles Sync System
# This module creates CloudWatch alarms for automated failure alerting

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# CloudWatch Log Groups for structured logging
resource "aws_cloudwatch_log_group" "orchestrator_logs" {
  name              = "/aws/lambda/${var.orchestrator_function_name}"
  retention_in_days = var.log_retention_days

  tags = var.tags
}

resource "aws_cloudwatch_log_group" "sync_worker_logs" {
  name              = "/aws/lambda/${var.sync_worker_function_name}"
  retention_in_days = var.log_retention_days

  tags = var.tags
}

resource "aws_cloudwatch_log_group" "ecs_sync_logs" {
  name              = "/aws/ecs/${var.ecs_cluster_name}"
  retention_in_days = var.log_retention_days

  tags = var.tags
}

# CloudWatch Dashboard for monitoring
resource "aws_cloudwatch_dashboard" "homebrew_sync_dashboard" {
  dashboard_name = "${var.project_name}-sync-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["HomebrewSync", "SyncProgress", "SyncPhase", "bottle_download"],
            [".", "BottlesCompleted", ".", "."],
            [".", "BottlesTotal", ".", "."],
            [".", "BottlesFailed", ".", "."]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "Sync Progress"
          period  = 300
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["HomebrewSync", "Errors", "ErrorType", "network_error"],
            [".", ".", ".", "s3_error"],
            [".", ".", ".", "validation_error"],
            [".", ".", ".", "timeout_error"]
          ]
          view    = "timeSeries"
          stacked = true
          region  = var.aws_region
          title   = "Error Rates by Type"
          period  = 300
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 12
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["HomebrewSync", "OperationDuration", "Operation", "bottle_download"],
            [".", ".", ".", "s3_upload"],
            [".", ".", ".", "hash_update"]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "Operation Performance"
          period  = 300
        }
      },
      {
        type   = "log"
        x      = 0
        y      = 18
        width  = 24
        height = 6

        properties = {
          query  = "SOURCE '/aws/lambda/${var.orchestrator_function_name}' | fields @timestamp, level, message, operation\n| filter level = \"ERROR\"\n| sort @timestamp desc\n| limit 100"
          region = var.aws_region
          title  = "Recent Errors"
        }
      }
    ]
  })

  tags = var.tags
}

# SNS Topic for alarm notifications
resource "aws_sns_topic" "sync_alerts" {
  name = "${var.project_name}-sync-alerts"

  tags = var.tags
}

resource "aws_sns_topic_subscription" "email_alerts" {
  count     = var.alert_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.sync_alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

resource "aws_sns_topic_subscription" "slack_alerts" {
  count     = var.slack_webhook_url != "" ? 1 : 0
  topic_arn = aws_sns_topic.sync_alerts.arn
  protocol  = "https"
  endpoint  = var.slack_webhook_url
}

# CloudWatch Alarms for automated failure alerting

# Alarm for high error rate
resource "aws_cloudwatch_metric_alarm" "high_error_rate" {
  alarm_name          = "${var.project_name}-high-error-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Errors"
  namespace           = "HomebrewSync"
  period              = "300"
  statistic           = "Sum"
  threshold           = "5"
  alarm_description   = "This metric monitors error rate for Homebrew sync"
  alarm_actions       = [aws_sns_topic.sync_alerts.arn]
  ok_actions          = [aws_sns_topic.sync_alerts.arn]

  dimensions = {
    Component = "sync-system"
  }

  tags = var.tags
}

# Alarm for Lambda function errors
resource "aws_cloudwatch_metric_alarm" "lambda_orchestrator_errors" {
  alarm_name          = "${var.project_name}-orchestrator-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Sum"
  threshold           = "0"
  alarm_description   = "This metric monitors Lambda orchestrator errors"
  alarm_actions       = [aws_sns_topic.sync_alerts.arn]
  ok_actions          = [aws_sns_topic.sync_alerts.arn]

  dimensions = {
    FunctionName = var.orchestrator_function_name
  }

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "lambda_sync_worker_errors" {
  alarm_name          = "${var.project_name}-sync-worker-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Sum"
  threshold           = "0"
  alarm_description   = "This metric monitors Lambda sync worker errors"
  alarm_actions       = [aws_sns_topic.sync_alerts.arn]
  ok_actions          = [aws_sns_topic.sync_alerts.arn]

  dimensions = {
    FunctionName = var.sync_worker_function_name
  }

  tags = var.tags
}

# Alarm for Lambda function duration (timeout warning)
resource "aws_cloudwatch_metric_alarm" "lambda_orchestrator_duration" {
  alarm_name          = "${var.project_name}-orchestrator-duration"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Average"
  threshold           = "240000" # 4 minutes (warn before 5 min timeout)
  alarm_description   = "This metric monitors Lambda orchestrator duration"
  alarm_actions       = [aws_sns_topic.sync_alerts.arn]

  dimensions = {
    FunctionName = var.orchestrator_function_name
  }

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "lambda_sync_worker_duration" {
  alarm_name          = "${var.project_name}-sync-worker-duration"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Average"
  threshold           = "840000" # 14 minutes (warn before 15 min timeout)
  alarm_description   = "This metric monitors Lambda sync worker duration"
  alarm_actions       = [aws_sns_topic.sync_alerts.arn]

  dimensions = {
    FunctionName = var.sync_worker_function_name
  }

  tags = var.tags
}

# Alarm for ECS task failures
resource "aws_cloudwatch_metric_alarm" "ecs_task_failures" {
  alarm_name          = "${var.project_name}-ecs-task-failures"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "TasksStoppedReason"
  namespace           = "AWS/ECS"
  period              = "300"
  statistic           = "Sum"
  threshold           = "0"
  alarm_description   = "This metric monitors ECS task failures"
  alarm_actions       = [aws_sns_topic.sync_alerts.arn]

  dimensions = {
    ClusterName = var.ecs_cluster_name
    ServiceName = var.ecs_service_name
  }

  tags = var.tags
}

# Alarm for sync progress stalled
resource "aws_cloudwatch_metric_alarm" "sync_progress_stalled" {
  alarm_name          = "${var.project_name}-sync-stalled"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "3"
  metric_name         = "SyncProgress"
  namespace           = "HomebrewSync"
  period              = "600"
  statistic           = "Maximum"
  threshold           = "1"
  alarm_description   = "This metric monitors if sync progress has stalled"
  alarm_actions       = [aws_sns_topic.sync_alerts.arn]
  treat_missing_data  = "breaching"

  dimensions = {
    SyncPhase = "bottle_download"
  }

  tags = var.tags
}

# Alarm for high download failure rate
resource "aws_cloudwatch_metric_alarm" "high_download_failure_rate" {
  alarm_name          = "${var.project_name}-high-download-failure-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "BottlesFailed"
  namespace           = "HomebrewSync"
  period              = "300"
  statistic           = "Sum"
  threshold           = "10"
  alarm_description   = "This metric monitors bottle download failure rate"
  alarm_actions       = [aws_sns_topic.sync_alerts.arn]

  dimensions = {
    SyncPhase = "bottle_download"
  }

  tags = var.tags
}

# Alarm for low download throughput
resource "aws_cloudwatch_metric_alarm" "low_download_throughput" {
  alarm_name          = "${var.project_name}-low-download-throughput"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "3"
  metric_name         = "DownloadThroughput"
  namespace           = "HomebrewSync"
  period              = "300"
  statistic           = "Average"
  threshold           = "1" # 1 MB/s minimum
  alarm_description   = "This metric monitors download throughput"
  alarm_actions       = [aws_sns_topic.sync_alerts.arn]

  dimensions = {
    Success = "true"
  }

  tags = var.tags
}

# Composite alarm for overall sync health
resource "aws_cloudwatch_composite_alarm" "sync_health" {
  alarm_name        = "${var.project_name}-sync-health"
  alarm_description = "Overall health of the Homebrew sync system"

  alarm_rule = join(" OR ", [
    "ALARM(${aws_cloudwatch_metric_alarm.high_error_rate.alarm_name})",
    "ALARM(${aws_cloudwatch_metric_alarm.lambda_orchestrator_errors.alarm_name})",
    "ALARM(${aws_cloudwatch_metric_alarm.lambda_sync_worker_errors.alarm_name})",
    "ALARM(${aws_cloudwatch_metric_alarm.ecs_task_failures.alarm_name})",
    "ALARM(${aws_cloudwatch_metric_alarm.sync_progress_stalled.alarm_name})",
    "ALARM(${aws_cloudwatch_metric_alarm.high_download_failure_rate.alarm_name})"
  ])

  alarm_actions = [aws_sns_topic.sync_alerts.arn]
  ok_actions    = [aws_sns_topic.sync_alerts.arn]

  tags = var.tags
}

# CloudWatch Insights queries for troubleshooting
resource "aws_cloudwatch_query_definition" "error_analysis" {
  name = "${var.project_name}-error-analysis"

  log_group_names = [
    aws_cloudwatch_log_group.orchestrator_logs.name,
    aws_cloudwatch_log_group.sync_worker_logs.name,
    aws_cloudwatch_log_group.ecs_sync_logs.name
  ]

  query_string = <<EOF
fields @timestamp, level, message, operation, error, component
| filter level = "ERROR"
| stats count() by operation, error
| sort count desc
EOF
}

resource "aws_cloudwatch_query_definition" "performance_analysis" {
  name = "${var.project_name}-performance-analysis"

  log_group_names = [
    aws_cloudwatch_log_group.orchestrator_logs.name,
    aws_cloudwatch_log_group.sync_worker_logs.name,
    aws_cloudwatch_log_group.ecs_sync_logs.name
  ]

  query_string = <<EOF
fields @timestamp, operation, duration, success
| filter performance_event = true
| stats avg(duration), max(duration), min(duration) by operation
| sort avg(duration) desc
EOF
}

resource "aws_cloudwatch_query_definition" "sync_progress_tracking" {
  name = "${var.project_name}-sync-progress"

  log_group_names = [
    aws_cloudwatch_log_group.orchestrator_logs.name,
    aws_cloudwatch_log_group.sync_worker_logs.name,
    aws_cloudwatch_log_group.ecs_sync_logs.name
  ]

  query_string = <<EOF
fields @timestamp, event_type, completed, total, phase, progress_percentage
| filter sync_event = true and event_type = "progress_update"
| sort @timestamp desc
| limit 100
EOF
}