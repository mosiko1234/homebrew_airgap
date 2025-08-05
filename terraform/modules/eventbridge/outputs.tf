output "eventbridge_rule_name" {
  description = "Name of the EventBridge rule"
  value       = aws_cloudwatch_event_rule.homebrew_sync_schedule.name
}

output "eventbridge_rule_arn" {
  description = "ARN of the EventBridge rule"
  value       = aws_cloudwatch_event_rule.homebrew_sync_schedule.arn
}

output "eventbridge_rule_id" {
  description = "ID of the EventBridge rule"
  value       = aws_cloudwatch_event_rule.homebrew_sync_schedule.id
}

output "eventbridge_rule_state" {
  description = "Current state of the EventBridge rule"
  value       = aws_cloudwatch_event_rule.homebrew_sync_schedule.state
}

output "eventbridge_target_id" {
  description = "ID of the EventBridge target"
  value       = aws_cloudwatch_event_target.lambda_orchestrator_target.target_id
}

output "schedule_expression" {
  description = "Schedule expression used by the EventBridge rule"
  value       = aws_cloudwatch_event_rule.homebrew_sync_schedule.schedule_expression
}

output "log_group_name" {
  description = "Name of the CloudWatch log group for EventBridge (if enabled)"
  value       = var.enable_logging ? aws_cloudwatch_log_group.eventbridge_logs[0].name : null
}

output "log_group_arn" {
  description = "ARN of the CloudWatch log group for EventBridge (if enabled)"
  value       = var.enable_logging ? aws_cloudwatch_log_group.eventbridge_logs[0].arn : null
}

output "failure_alarm_name" {
  description = "Name of the CloudWatch alarm for EventBridge failures (if enabled)"
  value       = var.enable_failure_alarm ? aws_cloudwatch_metric_alarm.eventbridge_failures[0].alarm_name : null
}

output "failure_alarm_arn" {
  description = "ARN of the CloudWatch alarm for EventBridge failures (if enabled)"
  value       = var.enable_failure_alarm ? aws_cloudwatch_metric_alarm.eventbridge_failures[0].arn : null
}

output "missed_schedule_alarm_name" {
  description = "Name of the CloudWatch alarm for missed schedules (if enabled)"
  value       = var.enable_missed_schedule_alarm ? aws_cloudwatch_metric_alarm.eventbridge_missed_schedules[0].alarm_name : null
}

output "missed_schedule_alarm_arn" {
  description = "ARN of the CloudWatch alarm for missed schedules (if enabled)"
  value       = var.enable_missed_schedule_alarm ? aws_cloudwatch_metric_alarm.eventbridge_missed_schedules[0].arn : null
}