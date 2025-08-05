# EventBridge Scheduled Rule for Homebrew Bottles Sync
resource "aws_cloudwatch_event_rule" "homebrew_sync_schedule" {
  name                = "${var.project_name}-homebrew-sync-schedule"
  description         = "Weekly schedule for Homebrew bottles synchronization"
  schedule_expression = var.schedule_expression
  state               = var.rule_state

  tags = var.tags
}

# EventBridge Target - Lambda Orchestrator Function
resource "aws_cloudwatch_event_target" "lambda_orchestrator_target" {
  rule      = aws_cloudwatch_event_rule.homebrew_sync_schedule.name
  target_id = "LambdaOrchestratorTarget"
  arn       = var.lambda_orchestrator_arn

  # Input transformer to provide context to the Lambda function
  input_transformer {
    input_paths = {
      "time" = "$.time"
    }
    input_template = jsonencode({
      "source"      = "eventbridge.schedule"
      "detail-type" = "Scheduled Event"
      "time"        = "<time>"
      "resources"   = [aws_cloudwatch_event_rule.homebrew_sync_schedule.arn]
    })
  }

  # Retry configuration for failed invocations
  retry_policy {
    maximum_retry_attempts       = var.max_retry_attempts
    maximum_event_age_in_seconds = var.max_event_age_seconds
  }

  # Dead letter queue configuration (optional)
  dynamic "dead_letter_config" {
    for_each = var.dlq_arn != null ? [1] : []
    content {
      arn = var.dlq_arn
    }
  }
}

# CloudWatch Log Group for EventBridge rule (for debugging)
resource "aws_cloudwatch_log_group" "eventbridge_logs" {
  count             = var.enable_logging ? 1 : 0
  name              = "/aws/events/rule/${var.project_name}-homebrew-sync"
  retention_in_days = var.log_retention_days

  tags = var.tags
}

# CloudWatch Log Destination for EventBridge (optional)
resource "aws_cloudwatch_log_destination" "eventbridge_log_destination" {
  count      = var.enable_logging ? 1 : 0
  name       = "${var.project_name}-eventbridge-logs"
  role_arn   = var.eventbridge_log_role_arn
  target_arn = aws_cloudwatch_log_group.eventbridge_logs[0].arn

  tags = var.tags
}

# CloudWatch Log Destination Policy
resource "aws_cloudwatch_log_destination_policy" "eventbridge_log_destination_policy" {
  count            = var.enable_logging ? 1 : 0
  destination_name = aws_cloudwatch_log_destination.eventbridge_log_destination[0].name
  access_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "events.amazonaws.com"
        }
        Action   = "logs:PutLogEvents"
        Resource = aws_cloudwatch_log_group.eventbridge_logs[0].arn
      }
    ]
  })
}

# CloudWatch Metric Alarm for EventBridge rule failures
resource "aws_cloudwatch_metric_alarm" "eventbridge_failures" {
  count               = var.enable_failure_alarm ? 1 : 0
  alarm_name          = "${var.project_name}-eventbridge-failures"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "FailedInvocations"
  namespace           = "AWS/Events"
  period              = "300"
  statistic           = "Sum"
  threshold           = "0"
  alarm_description   = "This metric monitors EventBridge rule failures for Homebrew sync"
  alarm_actions       = var.alarm_actions

  dimensions = {
    RuleName = aws_cloudwatch_event_rule.homebrew_sync_schedule.name
  }

  tags = var.tags
}

# CloudWatch Metric Alarm for missed schedules
resource "aws_cloudwatch_metric_alarm" "eventbridge_missed_schedules" {
  count               = var.enable_missed_schedule_alarm ? 1 : 0
  alarm_name          = "${var.project_name}-eventbridge-missed-schedules"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "SuccessfulInvocations"
  namespace           = "AWS/Events"
  period              = "604800" # 1 week in seconds
  statistic           = "Sum"
  threshold           = "1"
  alarm_description   = "This metric monitors for missed EventBridge scheduled executions"
  alarm_actions       = var.alarm_actions
  treat_missing_data  = "breaching"

  dimensions = {
    RuleName = aws_cloudwatch_event_rule.homebrew_sync_schedule.name
  }

  tags = var.tags
}