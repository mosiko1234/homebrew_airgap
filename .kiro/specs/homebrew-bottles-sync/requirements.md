# Requirements Document

## Introduction

The Homebrew Bottles Sync System is an AWS-based automated solution that downloads and mirrors Homebrew bottles for the three most recent macOS versions on a weekly schedule. The system uses Terraform for infrastructure management, AWS Lambda for orchestration, S3 for storage, and provides Slack notifications for monitoring. The solution prevents duplicate downloads through hash tracking and organizes bottles in a date-based folder structure.

## Requirements

### Requirement 1

**User Story:** As a DevOps engineer, I want an automated system that downloads Homebrew bottles weekly, so that I can maintain an up-to-date mirror without manual intervention.

#### Acceptance Criteria

1. WHEN the system runs THEN it SHALL execute on a weekly schedule (Sunday at 03:00 UTC)
2. WHEN the system starts THEN it SHALL fetch the complete formula list from https://formulae.brew.sh/api/formula.json
3. WHEN processing formulas THEN the system SHALL only target bottles for arm64_sonoma, arm64_ventura, and monterey macOS versions
4. WHEN the sync completes successfully THEN the system SHALL send a Slack notification with download statistics

### Requirement 2

**User Story:** As a system administrator, I want bottles stored in an organized S3 structure with date-based folders, so that I can easily locate and manage historical downloads.

#### Acceptance Criteria

1. WHEN storing bottles THEN the system SHALL use the folder structure s3://homebrew-bottle-mirror/YYYY-MM-DD/
2. WHEN organizing files THEN the system SHALL maintain the original bottle filename format (e.g., curl-8.0.0.arm64_ventura.bottle.tar.gz)
3. WHEN accessing storage THEN the system SHALL use S3 with optional versioning enabled
4. WHEN managing storage THEN the system SHALL maintain a bottles_hash.json file at the bucket root

### Requirement 3

**User Story:** As a cost-conscious administrator, I want the system to avoid downloading duplicate bottles, so that I can minimize storage costs and transfer time.

#### Acceptance Criteria

1. WHEN checking for duplicates THEN the system SHALL compare bottle SHA values against bottles_hash.json
2. WHEN a bottle SHA exists in the hash file THEN the system SHALL skip downloading that bottle
3. WHEN downloading new bottles THEN the system SHALL update bottles_hash.json with new SHA values
4. WHEN the hash file doesn't exist THEN the system SHALL create it and proceed with all downloads

### Requirement 4

**User Story:** As a DevOps team member, I want real-time notifications about sync status, so that I can monitor system health and respond to failures quickly.

#### Acceptance Criteria

1. WHEN sync starts THEN the system SHALL send a Slack notification indicating sync initiation
2. WHEN sync completes successfully THEN the system SHALL send a notification with count of new bottles and total size downloaded
3. WHEN sync fails THEN the system SHALL send an error notification with specific failure details
4. WHEN sending notifications THEN the system SHALL use Slack webhook integration

### Requirement 5

**User Story:** As a cloud architect, I want the infrastructure deployed through modular Terraform code, so that I can maintain, version, and reuse components across environments.

#### Acceptance Criteria

1. WHEN deploying infrastructure THEN the system SHALL use separate Terraform modules for network, s3, lambda, iam, eventbridge, and notifications
2. WHEN configuring Lambda THEN the system SHALL use Python 3.x with boto3 and requests libraries
3. WHEN setting up scheduling THEN the system SHALL use Amazon EventBridge with cron expressions
4. WHEN managing permissions THEN the system SHALL implement IAM roles with least privilege access

### Requirement 6

**User Story:** As a security engineer, I want the system to follow AWS security best practices, so that I can ensure data protection and access control.

#### Acceptance Criteria

1. WHEN configuring IAM THEN the system SHALL grant only minimum required permissions to Lambda functions
2. WHEN storing sensitive data THEN the system SHALL optionally use AWS Secrets Manager for Slack webhook URLs
3. WHEN executing Lambda THEN the system SHALL have appropriate timeout, memory, and execution limits
4. WHEN accessing S3 THEN the system SHALL use scoped access policies restricted to the specific bucket

### Requirement 7

**User Story:** As a system integrator, I want to provide an existing bottles_hash.json file to the system, so that the initial sync will skip already-downloaded packages and reduce transfer load.

#### Acceptance Criteria

1. WHEN the system initializes THEN it SHALL check for an externally provided bottles_hash.json (e.g., in S3 or as part of deployment config)
2. WHEN the file exists THEN it SHALL load and use it to skip already-downloaded bottles
3. WHEN the file is missing THEN it SHALL proceed with a full download and generate a new hash file
4. WHEN loading external hash file THEN it SHALL validate the file format and handle corrupted data gracefully

### Requirement 8

**User Story:** As a DevOps engineer, I want the sync job to run on ECS with sufficient CPU, memory, and disk space, so that I can handle large Homebrew bottle downloads efficiently.

#### Acceptance Criteria

1. WHEN the estimated download size exceeds a predefined threshold (e.g. 20GB) THEN the sync job SHALL run in ECS instead of Lambda
2. WHEN using ECS THEN the system SHALL support mounting a temporary working directory (ephemeral or EFS)
3. WHEN sync completes THEN the ECS task SHALL upload bottles to S3 and update the hash file as usual
4. WHEN scheduling ECS THEN the system SHALL use EventBridge to trigger ECS tasks
5. WHEN running on ECS THEN the system SHALL configure appropriate CPU, memory, and storage resources for large-scale downloads

### Requirement 9

**User Story:** As a developer, I want comprehensive documentation and deployment instructions, so that I can understand, deploy, and maintain the system effectively.

#### Acceptance Criteria

1. WHEN delivering the solution THEN it SHALL include a README with deployment instructions
2. WHEN providing code THEN it SHALL include all Terraform modules with proper documentation
3. WHEN delivering ECS and Lambda code THEN it SHALL include Python source with clear comments and error handling
4. WHEN documenting usage THEN it SHALL include examples of Slack notification formats and S3 structure