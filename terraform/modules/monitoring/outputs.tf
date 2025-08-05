# Outputs for the monitoring module

output "sns_topic_arn" {
  description = "ARN of the SNS topic for alerts"
  value       = aws_sns_topic.sync_alerts.arn
}

output "dashboard_url" {
  description = "URL of the CloudWatch dashboard"
  value       = "https://${var.aws_region}.console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${aws_cloudwatch_dashboard.homebrew_sync_dashboard.dashboard_name}"
}

output "log_group_names" {
  description = "Names of the CloudWatch log groups"
  value = {
    orchestrator = aws_cloudwatch_log_group.orchestrator_logs.name
    sync_worker  = aws_cloudwatch_log_group.sync_worker_logs.name
    ecs_sync     = aws_cloudwatch_log_group.ecs_sync_logs.name
  }
}

output "alarm_names" {
  description = "Names of the CloudWatch alarms"
  value = {
    high_error_rate         = aws_cloudwatch_metric_alarm.high_error_rate.alarm_name
    orchestrator_errors     = aws_cloudwatch_metric_alarm.lambda_orchestrator_errors.alarm_name
    sync_worker_errors      = aws_cloudwatch_metric_alarm.lambda_sync_worker_errors.alarm_name
    orchestrator_duration   = aws_cloudwatch_metric_alarm.lambda_orchestrator_duration.alarm_name
    sync_worker_duration    = aws_cloudwatch_metric_alarm.lambda_sync_worker_duration.alarm_name
    ecs_task_failures       = aws_cloudwatch_metric_alarm.ecs_task_failures.alarm_name
    sync_progress_stalled   = aws_cloudwatch_metric_alarm.sync_progress_stalled.alarm_name
    high_download_failure   = aws_cloudwatch_metric_alarm.high_download_failure_rate.alarm_name
    low_download_throughput = aws_cloudwatch_metric_alarm.low_download_throughput.alarm_name
    sync_health_composite   = aws_cloudwatch_composite_alarm.sync_health.alarm_name
  }
}

output "query_definition_names" {
  description = "Names of the CloudWatch Insights query definitions"
  value = {
    error_analysis       = aws_cloudwatch_query_definition.error_analysis.name
    performance_analysis = aws_cloudwatch_query_definition.performance_analysis.name
    sync_progress        = aws_cloudwatch_query_definition.sync_progress_tracking.name
  }
}