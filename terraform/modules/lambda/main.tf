# Lambda Layer for shared dependencies
resource "aws_lambda_layer_version" "shared_dependencies" {
  filename         = var.lambda_layer_zip_path
  layer_name       = "${var.project_name}-shared-dependencies"
  description      = "Shared dependencies for Homebrew bottles sync Lambda functions"
  source_code_hash = var.lambda_layer_source_hash

  compatible_runtimes = ["python3.11", "python3.12"]

  lifecycle {
    create_before_destroy = true
  }

  tags = var.tags
}

# CloudWatch Log Group for Lambda Orchestrator
resource "aws_cloudwatch_log_group" "lambda_orchestrator_logs" {
  name              = "/aws/lambda/${var.project_name}-orchestrator"
  retention_in_days = var.log_retention_days

  tags = var.tags
}

# CloudWatch Log Group for Lambda Sync Worker
resource "aws_cloudwatch_log_group" "lambda_sync_logs" {
  name              = "/aws/lambda/${var.project_name}-sync"
  retention_in_days = var.log_retention_days

  tags = var.tags
}

# Lambda Orchestrator Function
resource "aws_lambda_function" "orchestrator" {
  filename         = var.lambda_orchestrator_zip_path
  function_name    = "${var.project_name}-orchestrator"
  role             = var.lambda_orchestrator_role_arn
  handler          = "handler.lambda_handler"
  runtime          = var.python_runtime
  timeout          = var.orchestrator_timeout
  memory_size      = var.orchestrator_memory_size
  source_code_hash = var.lambda_orchestrator_source_hash

  layers = [aws_lambda_layer_version.shared_dependencies.arn]

  environment {
    variables = {
      S3_BUCKET_NAME                = var.s3_bucket_name
      SLACK_WEBHOOK_SECRET          = var.slack_webhook_secret_name
      SIZE_THRESHOLD_GB             = var.size_threshold_gb
      AWS_REGION                    = var.aws_region
      ECS_CLUSTER_NAME              = var.ecs_cluster_name
      ECS_TASK_DEFINITION           = var.ecs_task_definition_name
      LAMBDA_SYNC_FUNCTION          = aws_lambda_function.sync.function_name
      ECS_SUBNETS                   = join(",", var.ecs_subnets)
      ECS_SECURITY_GROUPS           = join(",", var.ecs_security_groups)
      LOG_LEVEL                     = var.log_level
      EXTERNAL_HASH_FILE_S3_KEY     = var.external_hash_file_s3_key
      EXTERNAL_HASH_FILE_S3_BUCKET  = var.external_hash_file_s3_bucket
      EXTERNAL_HASH_FILE_URL        = var.external_hash_file_url
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.lambda_orchestrator_logs,
  ]

  tags = var.tags
}

# Lambda Sync Worker Function
resource "aws_lambda_function" "sync" {
  filename         = var.lambda_sync_zip_path
  function_name    = "${var.project_name}-sync"
  role             = var.lambda_sync_role_arn
  handler          = "handler.lambda_handler"
  runtime          = var.python_runtime
  timeout          = var.sync_timeout
  memory_size      = var.sync_memory_size
  source_code_hash = var.lambda_sync_source_hash

  layers = [aws_lambda_layer_version.shared_dependencies.arn]

  environment {
    variables = {
      S3_BUCKET_NAME                = var.s3_bucket_name
      SLACK_WEBHOOK_SECRET_NAME     = var.slack_webhook_secret_name
      AWS_REGION                    = var.aws_region
      LOG_LEVEL                     = var.log_level
      EXTERNAL_HASH_FILE_S3_KEY     = var.external_hash_file_s3_key
      EXTERNAL_HASH_FILE_S3_BUCKET  = var.external_hash_file_s3_bucket
      EXTERNAL_HASH_FILE_URL        = var.external_hash_file_url
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.lambda_sync_logs,
  ]

  tags = var.tags
}

# Lambda permission for EventBridge to invoke orchestrator
resource "aws_lambda_permission" "allow_eventbridge_orchestrator" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.orchestrator.function_name
  principal     = "events.amazonaws.com"
  source_arn    = var.eventbridge_rule_arn
}

# Lambda permission for orchestrator to invoke sync worker
resource "aws_lambda_permission" "allow_orchestrator_invoke_sync" {
  statement_id  = "AllowExecutionFromOrchestrator"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.sync.function_name
  principal     = "lambda.amazonaws.com"
  source_arn    = aws_lambda_function.orchestrator.arn
}

# Dead Letter Queue for Lambda functions (optional)
resource "aws_sqs_queue" "lambda_dlq" {
  count = var.enable_dlq ? 1 : 0

  name                      = "${var.project_name}-lambda-dlq"
  message_retention_seconds = 1209600 # 14 days

  tags = var.tags
}

# Dead Letter Queue policy
resource "aws_sqs_queue_policy" "lambda_dlq_policy" {
  count     = var.enable_dlq ? 1 : 0
  queue_url = aws_sqs_queue.lambda_dlq[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = [
          "sqs:SendMessage"
        ]
        Resource = aws_sqs_queue.lambda_dlq[0].arn
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = var.aws_account_id
          }
        }
      }
    ]
  })
}

# Update Lambda functions to use DLQ if enabled
resource "aws_lambda_function_event_invoke_config" "orchestrator_config" {
  count         = var.enable_dlq ? 1 : 0
  function_name = aws_lambda_function.orchestrator.function_name

  maximum_retry_attempts = var.lambda_max_retry_attempts

  dead_letter_config {
    target_arn = aws_sqs_queue.lambda_dlq[0].arn
  }
}

resource "aws_lambda_function_event_invoke_config" "sync_config" {
  count         = var.enable_dlq ? 1 : 0
  function_name = aws_lambda_function.sync.function_name

  maximum_retry_attempts = var.lambda_max_retry_attempts

  dead_letter_config {
    target_arn = aws_sqs_queue.lambda_dlq[0].arn
  }
}