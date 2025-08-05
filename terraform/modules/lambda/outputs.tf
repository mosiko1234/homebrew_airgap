output "lambda_orchestrator_function_name" {
  description = "Name of the Lambda orchestrator function"
  value       = aws_lambda_function.orchestrator.function_name
}

output "lambda_orchestrator_function_arn" {
  description = "ARN of the Lambda orchestrator function"
  value       = aws_lambda_function.orchestrator.arn
}

output "lambda_orchestrator_invoke_arn" {
  description = "Invoke ARN of the Lambda orchestrator function"
  value       = aws_lambda_function.orchestrator.invoke_arn
}

output "lambda_sync_function_name" {
  description = "Name of the Lambda sync worker function"
  value       = aws_lambda_function.sync.function_name
}

output "lambda_sync_function_arn" {
  description = "ARN of the Lambda sync worker function"
  value       = aws_lambda_function.sync.arn
}

output "lambda_sync_invoke_arn" {
  description = "Invoke ARN of the Lambda sync worker function"
  value       = aws_lambda_function.sync.invoke_arn
}

output "lambda_layer_arn" {
  description = "ARN of the Lambda layer containing shared dependencies"
  value       = aws_lambda_layer_version.shared_dependencies.arn
}

output "lambda_layer_version" {
  description = "Version of the Lambda layer"
  value       = aws_lambda_layer_version.shared_dependencies.version
}

output "orchestrator_log_group_name" {
  description = "Name of the CloudWatch log group for the orchestrator function"
  value       = aws_cloudwatch_log_group.lambda_orchestrator_logs.name
}

output "orchestrator_log_group_arn" {
  description = "ARN of the CloudWatch log group for the orchestrator function"
  value       = aws_cloudwatch_log_group.lambda_orchestrator_logs.arn
}

output "sync_log_group_name" {
  description = "Name of the CloudWatch log group for the sync worker function"
  value       = aws_cloudwatch_log_group.lambda_sync_logs.name
}

output "sync_log_group_arn" {
  description = "ARN of the CloudWatch log group for the sync worker function"
  value       = aws_cloudwatch_log_group.lambda_sync_logs.arn
}

output "lambda_dlq_url" {
  description = "URL of the Lambda Dead Letter Queue (if enabled)"
  value       = var.enable_dlq ? aws_sqs_queue.lambda_dlq[0].url : null
}

output "lambda_dlq_arn" {
  description = "ARN of the Lambda Dead Letter Queue (if enabled)"
  value       = var.enable_dlq ? aws_sqs_queue.lambda_dlq[0].arn : null
}