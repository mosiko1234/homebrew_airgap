# Implementation Plan

- [x] 1. Set up project structure and core data models
  - Create directory structure for Terraform modules, Lambda functions, and ECS tasks
  - Define Python data classes for Formula, BottleInfo, HashEntry, and SyncConfig
  - Implement validation methods for all data models
  - Create unit tests for data model validation and serialization
  - _Requirements: 7.3, 8.3, 9.3_

- [x] 2. Implement S3 storage service and hash file management
  - Create S3Service class with methods for upload, download, and bucket operations
  - Implement HashFileManager class for loading, updating, and validating bottles_hash.json
  - Add atomic update functionality for hash file to prevent corruption
  - Write unit tests for S3 operations and hash file management
  - _Requirements: 2.1, 2.4, 3.1, 3.2, 3.3, 7.1, 7.2, 7.3_

- [x] 3. Create Homebrew API client and formula processing
  - Implement HomebrewAPIClient class to fetch formula data from https://formulae.brew.sh/api/formula.json
  - Add formula parsing and filtering for target macOS versions (arm64_sonoma, arm64_ventura, monterey)
  - Implement download size estimation logic for routing decisions
  - Create unit tests for API client and formula processing
  - _Requirements: 1.2, 1.3, 8.1_

- [x] 4. Implement notification service for Slack integration
  - Create NotificationService class with Slack webhook integration
  - Implement message formatting for different notification types (start, progress, success, failure)
  - Add Secrets Manager integration for webhook URL storage
  - Write unit tests for notification formatting and delivery
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 6.2_

- [x] 5. Build Lambda orchestrator function
  - Create Lambda function handler for EventBridge scheduled events
  - Implement orchestration logic to fetch formulas and estimate download size
  - Add routing logic to decide between Lambda sync and ECS sync based on size threshold
  - Implement error handling and initial Slack notifications
  - Create unit tests for orchestration logic and routing decisions
  - _Requirements: 1.1, 1.2, 8.1, 8.4_

- [x] 6. Implement Lambda sync worker for small downloads
  - Create Lambda function for downloading bottles under 20GB threshold
  - Implement bottle download logic with SHA validation against hash file
  - Add S3 upload functionality with date-based folder structure
  - Implement hash file updates and completion notifications
  - Create unit tests for download logic and S3 integration
  - _Requirements: 1.3, 2.1, 2.2, 3.1, 3.2, 4.2_

- [x] 7. Build ECS sync worker for large downloads
  - Create containerized Python application for ECS Fargate tasks
  - Implement large-scale bottle download logic with progress tracking
  - Add support for EFS or ephemeral storage for temporary files
  - Implement batch processing and graceful handling of network interruptions
  - Create unit tests for ECS-specific download logic
  - _Requirements: 8.1, 8.2, 8.3, 4.2_

- [x] 8. Create Terraform S3 module
  - Write Terraform configuration for S3 bucket creation with versioning
  - Implement bucket policies and lifecycle rules for cost optimization
  - Add IAM policies for Lambda and ECS access to the bucket
  - Include outputs for bucket name and ARN for other modules
  - _Requirements: 2.3, 5.1, 6.1_

- [x] 9. Create Terraform IAM module
  - Define IAM roles for Lambda orchestrator and sync functions
  - Create IAM roles for ECS task execution with minimal required permissions
  - Implement policies for S3 access, Secrets Manager, and CloudWatch logging
  - Add trust relationships and permission boundaries
  - _Requirements: 5.2, 6.1_

- [x] 10. Create Terraform Lambda module
  - Write Terraform configuration for Lambda function deployment
  - Implement Lambda layer for shared dependencies (boto3, requests)
  - Add environment variable configuration and timeout settings
  - Include CloudWatch log group creation and retention policies
  - _Requirements: 5.1, 5.2_

- [x] 11. Create Terraform ECS module
  - Write Terraform configuration for ECS cluster and Fargate service
  - Implement ECS task definition with appropriate CPU, memory, and storage
  - Add EFS file system configuration for temporary storage
  - Include CloudWatch log configuration for ECS tasks
  - _Requirements: 5.1, 8.2, 8.5_

- [x] 12. Create Terraform EventBridge module
  - Write Terraform configuration for EventBridge scheduled rules
  - Implement weekly cron expression (Sunday at 03:00 UTC)
  - Add Lambda function targets and necessary permissions
  - Include rule state management and error handling
  - _Requirements: 1.1, 5.1, 8.4_

- [x] 13. Create Terraform notifications module
  - Write Terraform configuration for Secrets Manager secret creation
  - Implement IAM policies for Lambda and ECS access to secrets
  - Add optional SNS topic configuration for additional notifications
  - Include secret rotation configuration
  - _Requirements: 4.4, 5.1, 6.2_

- [x] 14. Create Terraform network module
  - Write Terraform configuration for VPC and subnet setup
  - Implement security groups for ECS tasks with minimal required access
  - Add NAT Gateway configuration for outbound internet access
  - Include network ACLs and route table configuration
  - _Requirements: 5.1, 6.1_

- [x] 15. Implement error handling and recovery mechanisms
  - Add retry logic with exponential backoff for network operations
  - Implement partial sync recovery to resume from last successful bottle
  - Add hash file corruption detection and rebuild functionality
  - Create comprehensive error logging and CloudWatch metrics
  - Write unit tests for error scenarios and recovery logic
  - _Requirements: 6.3, 4.3_

- [x] 16. Create integration tests for end-to-end workflows
  - Write integration tests for Lambda-based sync workflow
  - Create integration tests for ECS-based sync workflow
  - Implement tests for error handling and recovery scenarios
  - Add tests for cross-service communication (Lambda to ECS)
  - _Requirements: 1.1, 1.2, 1.3, 8.1, 8.3_

- [x] 17. Implement monitoring and observability
  - Add CloudWatch custom metrics for sync progress and errors
  - Implement structured logging for all components
  - Add X-Ray tracing for Lambda functions
  - Create CloudWatch alarms for automated failure alerting
  - _Requirements: 6.3, 4.3_

- [x] 18. Create main Terraform configuration and deployment scripts
  - Write root Terraform configuration that combines all modules
  - Implement variable definitions and default values
  - Add terraform.tfvars.example with configuration examples
  - Create deployment scripts for different environments
  - _Requirements: 5.1, 9.1_

- [x] 19. Write comprehensive documentation
  - Create README.md with deployment and usage instructions
  - Document all Terraform modules with input/output specifications
  - Add troubleshooting guide and common issues section
  - Include examples of Slack notification formats and S3 structure
  - _Requirements: 9.1, 9.2, 9.4_

- [x] 20. Implement external hash file support
  - Add functionality to load pre-supplied bottles_hash.json from S3 or deployment config
  - Implement validation and migration logic for external hash files
  - Add configuration options for specifying external hash file location
  - Create unit tests for external hash file loading and validation
  - _Requirements: 7.1, 7.2, 7.3, 7.4_