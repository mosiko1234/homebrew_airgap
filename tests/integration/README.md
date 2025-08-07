# Integration Testing System

This directory contains comprehensive integration tests for the Homebrew Bottles Sync System CI/CD pipeline.

## Overview

The integration testing system provides three main categories of tests:

1. **AWS Service Integration Tests** (`test_aws_services.py`)
2. **Terraform Module Validation Tests** (`test_terraform_modules.py`)
3. **End-to-End Workflow Tests** (`test_end_to_end_workflows.py`)

## Test Categories

### AWS Service Integration Tests

Tests AWS service interactions with mocking:

- **S3Service Integration**: Bucket operations, atomic operations, error handling
- **Lambda Service Integration**: Function invocation, orchestrator routing logic
- **ECS Service Integration**: Task execution, cluster management
- **Secrets Manager Integration**: Secure webhook URL retrieval
- **Cross-Service Integration**: Lambda-S3 integration, error propagation
- **Performance and Scaling**: Large hash file operations, concurrent access

### Terraform Module Validation Tests

Tests Terraform module syntax and configuration:

- **S3 Module**: Validation, planning with valid inputs, outputs verification
- **Lambda Module**: Validation, planning, IAM role creation
- **ECS Module**: Validation, task definition creation
- **Network Module**: VPC, subnet, and gateway configuration
- **IAM Module**: Security policies and role creation
- **Monitoring Module**: CloudWatch alarms and log groups
- **Security Scanning**: tfsec integration, format compliance

### End-to-End Workflow Tests

Tests complete workflows from trigger to completion:

- **Complete Deployment Workflow**: Configuration processing, GitHub Actions simulation
- **Full Sync Workflow**: Orchestrator to Lambda/ECS completion
- **Error Recovery Workflows**: Deployment failure rollback, data corruption recovery
- **Monitoring and Alerting**: Deployment monitoring, cost monitoring
- **Security Workflows**: Secrets rotation, security scanning

## Running Tests

### Using the Test Runner

```bash
# Run all integration tests
python3 tests/run_integration_tests.py

# Run specific categories
python3 tests/run_integration_tests.py --categories aws terraform workflows

# Run with verbose output
python3 tests/run_integration_tests.py --categories aws --verbose

# Run with coverage
python3 tests/run_integration_tests.py --coverage
```

### Using pytest directly

```bash
# Run AWS service tests
python3 -m pytest tests/integration/test_aws_services.py -v

# Run Terraform module tests
python3 -m pytest tests/integration/test_terraform_modules.py -v

# Run end-to-end workflow tests
python3 -m pytest tests/integration/test_end_to_end_workflows.py -v

# Run specific test
python3 -m pytest tests/integration/test_aws_services.py::TestS3ServiceIntegration::test_s3_bucket_operations -v
```

## Dependencies

### Required Dependencies

- `pytest`: Test framework
- `boto3`: AWS SDK (for AWS service tests)
- `requests`: HTTP library (for API tests)

### Optional Dependencies

- `moto`: AWS service mocking (for full AWS integration tests)
- `aiohttp`: Async HTTP client (for ECS async tests)
- `aiofiles`: Async file operations (for ECS tests)
- `terraform`: Infrastructure as Code tool (for Terraform validation tests)
- `tfsec`: Terraform security scanner (for security tests)

### Installing Dependencies

```bash
# Install required dependencies
pip install pytest boto3 requests

# Install optional dependencies for full test coverage
pip install moto aiohttp aiofiles

# Install Terraform (macOS with Homebrew)
brew install terraform tfsec
```

## Test Structure

### AWS Service Tests

```python
class TestS3ServiceIntegration:
    @mock_s3
    def test_s3_bucket_operations(self):
        # Test S3 bucket creation and operations
        
class TestLambdaServiceIntegration:
    def test_lambda_orchestrator_routing_logic(self):
        # Test Lambda orchestrator routing
```

### Terraform Module Tests

```python
class TestS3Module:
    def test_s3_module_validation(self):
        # Test Terraform module syntax validation
        
    def test_s3_module_plan_with_valid_inputs(self):
        # Test Terraform planning with valid inputs
```

### End-to-End Workflow Tests

```python
class TestCompleteDeploymentWorkflow:
    def test_configuration_processing_workflow(self):
        # Test complete configuration processing
        
    def test_github_actions_workflow_simulation(self):
        # Test GitHub Actions workflow simulation
```

## Mock Strategy

The integration tests use a comprehensive mocking strategy:

1. **AWS Services**: Use `moto` library for AWS service mocking
2. **External APIs**: Mock HTTP requests with `unittest.mock`
3. **File System**: Use temporary directories for file operations
4. **Environment Variables**: Mock environment variables for configuration

## Error Handling

Tests include comprehensive error handling scenarios:

- Network failures and timeouts
- AWS service errors (bucket not found, function not found)
- Configuration validation errors
- Data corruption and recovery
- Resource exhaustion scenarios

## Performance Testing

Performance tests verify:

- Large hash file operations (1000+ bottles)
- Concurrent access patterns
- Memory usage optimization
- Execution time thresholds

## Security Testing

Security tests include:

- Terraform security scanning with tfsec
- Secrets management validation
- IAM policy verification
- Network security configuration

## Continuous Integration

The integration tests are designed to run in CI/CD environments:

- Graceful handling of missing dependencies
- Environment-specific configuration
- Detailed test reporting
- Coverage metrics

## Troubleshooting

### Common Issues

1. **Missing Dependencies**: Tests will skip gracefully if optional dependencies are missing
2. **AWS Credentials**: Tests use mocking, so no real AWS credentials are needed
3. **Terraform Not Found**: Terraform validation tests will skip if terraform is not installed
4. **Import Errors**: Tests handle import errors for optional modules

### Debug Mode

Run tests with verbose output and full tracebacks:

```bash
python3 -m pytest tests/integration/ -v -s --tb=long
```

### Test Coverage

Generate coverage reports:

```bash
python3 -m pytest tests/integration/ --cov=shared --cov=lambda --cov=ecs --cov-report=html
```

## Contributing

When adding new integration tests:

1. Follow the existing test structure and naming conventions
2. Include comprehensive mocking for external dependencies
3. Add appropriate error handling and edge cases
4. Update this README with new test categories
5. Ensure tests can run without external dependencies when possible

## Requirements Verification

This integration testing system fulfills the following requirements:

- **Requirement 3.3**: Comprehensive automated testing including integration tests with mocked AWS services
- **Requirement 3.5**: Detailed test failure information and fix instructions
- **Requirement 1.1**: Pipeline validation through end-to-end workflow testing
- **Requirement 2.4**: Configuration validation testing
- **Requirement 5.5**: Security testing and validation

The system provides robust integration testing capabilities that ensure the CI/CD pipeline components work correctly together while maintaining fast execution through comprehensive mocking strategies.