output "lambda_orchestrator_role_arn" {
  description = "ARN of the Lambda orchestrator IAM role"
  value       = aws_iam_role.lambda_orchestrator_role.arn
}

output "lambda_orchestrator_role_name" {
  description = "Name of the Lambda orchestrator IAM role"
  value       = aws_iam_role.lambda_orchestrator_role.name
}

output "lambda_sync_role_arn" {
  description = "ARN of the Lambda sync worker IAM role"
  value       = aws_iam_role.lambda_sync_role.arn
}

output "lambda_sync_role_name" {
  description = "Name of the Lambda sync worker IAM role"
  value       = aws_iam_role.lambda_sync_role.name
}

output "ecs_task_execution_role_arn" {
  description = "ARN of the ECS task execution IAM role"
  value       = aws_iam_role.ecs_task_execution_role.arn
}

output "ecs_task_execution_role_name" {
  description = "Name of the ECS task execution IAM role"
  value       = aws_iam_role.ecs_task_execution_role.name
}

output "ecs_task_role_arn" {
  description = "ARN of the ECS task IAM role"
  value       = aws_iam_role.ecs_task_role.arn
}

output "ecs_task_role_name" {
  description = "Name of the ECS task IAM role"
  value       = aws_iam_role.ecs_task_role.name
}