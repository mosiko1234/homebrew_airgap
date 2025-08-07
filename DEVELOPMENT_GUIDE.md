# Homebrew Bottles Sync System - Development Guide

This guide provides comprehensive instructions for local development, testing procedures, contribution guidelines, and code quality standards for the Homebrew Bottles Sync System.

## Table of Contents

1. [Local Development Setup](#local-development-setup)
2. [Development Workflow](#development-workflow)
3. [Testing Procedures](#testing-procedures)
4. [Code Quality Standards](#code-quality-standards)
5. [Contribution Guidelines](#contribution-guidelines)
6. [Code Review Process](#code-review-process)
7. [Debugging and Troubleshooting](#debugging-and-troubleshooting)
8. [Performance Guidelines](#performance-guidelines)

## Local Development Setup

### Prerequisites

Before starting development, ensure you have the following tools installed:

#### Required Tools

```bash
# Python 3.11+ with pip
python3 --version  # Should be 3.11 or higher
pip3 --version

# Node.js and npm (for some tooling)
node --version     # v18+ recommended
npm --version

# Docker for containerization
docker --version
docker-compose --version

# AWS CLI for cloud interactions
aws --version      # v2.x required

# Terraform for infrastructure
terraform --version # v1.0+ required

# Git for version control
git --version

# Additional development tools
jq --version       # JSON processing
curl --version     # HTTP requests
```

#### Development Environment Setup

```bash
# Clone the repository
git clone <repository-url>
cd homebrew-bottles-sync

# Create and activate Python virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install

# Set up local configuration
cp config.yaml.example config.yaml
cp .env.example .env

# Initialize Terraform (for local testing)
cd terraform
terraform init -backend=false
cd ..
```#
## Local Configuration

#### Environment Variables

Create a `.env` file for local development:

```bash
# .env file for local development
AWS_PROFILE=homebrew-sync-dev
AWS_REGION=us-west-2
ENVIRONMENT=local

# Local testing configuration
LOCAL_TESTING=true
MOCK_AWS_SERVICES=true
LOG_LEVEL=DEBUG

# Slack webhook for testing (optional)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/TEST/WEBHOOK

# Local S3 endpoint (for testing with LocalStack)
S3_ENDPOINT_URL=http://localhost:4566

# Database configuration (if applicable)
DATABASE_URL=sqlite:///local_test.db
```

#### Local Configuration File

Customize `config.yaml` for local development:

```yaml
# Local development configuration
project:
  name: "homebrew-bottles-sync-local"
  description: "Local development instance"
  version: "dev"

environments:
  local:
    aws_region: "us-west-2"
    size_threshold_gb: 1  # Smaller threshold for testing
    schedule_expression: "rate(1 hour)"  # More frequent for testing
    enable_fargate_spot: true
    auto_shutdown: false
    
    # Local testing overrides
    mock_homebrew_api: true
    use_test_data: true
    skip_s3_upload: false  # Set to true to skip actual uploads

resources:
  lambda:
    orchestrator_memory: 256  # Smaller for local testing
    sync_memory: 512
    timeout: 300
    
  ecs:
    task_cpu: 256
    task_memory: 512
    ephemeral_storage: 20

notifications:
  slack:
    enabled: true
    channel: "#dev-testing"
  email:
    enabled: false  # Disable email for local testing
```

### Local Testing Infrastructure

#### Using LocalStack for AWS Services

```bash
# Install LocalStack
pip install localstack

# Start LocalStack services
docker-compose -f docker-compose.localstack.yml up -d

# Verify LocalStack is running
curl http://localhost:4566/health
```

#### LocalStack Configuration

Create `docker-compose.localstack.yml`:

```yaml
version: '3.8'

services:
  localstack:
    container_name: homebrew-sync-localstack
    image: localstack/localstack:latest
    ports:
      - "4566:4566"
      - "4571:4571"
    environment:
      - SERVICES=s3,lambda,ecs,events,secretsmanager,iam,logs
      - DEBUG=1
      - DATA_DIR=/tmp/localstack/data
      - LAMBDA_EXECUTOR=docker
      - DOCKER_HOST=unix:///var/run/docker.sock
    volumes:
      - "/tmp/localstack:/tmp/localstack"
      - "/var/run/docker.sock:/var/run/docker.sock"
    networks:
      - homebrew-sync-local

networks:
  homebrew-sync-local:
    driver: bridge
```

#### Local AWS Configuration

```bash
# Configure AWS CLI for LocalStack
aws configure set aws_access_key_id test
aws configure set aws_secret_access_key test
aws configure set region us-west-2
aws configure set output json

# Create local S3 bucket
aws --endpoint-url=http://localhost:4566 s3 mb s3://homebrew-bottles-local

# Create local secrets
aws --endpoint-url=http://localhost:4566 secretsmanager create-secret \
  --name "homebrew-sync/slack-webhook" \
  --secret-string "http://localhost:3000/webhook"
```

### Development Tools Setup

#### IDE Configuration

##### VS Code Settings

Create `.vscode/settings.json`:

```json
{
  "python.defaultInterpreterPath": "./venv/bin/python",
  "python.linting.enabled": true,
  "python.linting.flake8Enabled": true,
  "python.linting.pylintEnabled": false,
  "python.formatting.provider": "black",
  "python.formatting.blackArgs": ["--line-length", "88"],
  "python.sortImports.args": ["--profile", "black"],
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.organizeImports": true
  },
  "files.exclude": {
    "**/__pycache__": true,
    "**/*.pyc": true,
    ".pytest_cache": true,
    ".coverage": true,
    "htmlcov": true
  },
  "terraform.experimentalFeatures.validateOnSave": true,
  "terraform.experimentalFeatures.prefillRequiredFields": true
}
```

##### VS Code Extensions

Create `.vscode/extensions.json`:

```json
{
  "recommendations": [
    "ms-python.python",
    "ms-python.flake8",
    "ms-python.black-formatter",
    "ms-python.isort",
    "hashicorp.terraform",
    "ms-vscode.vscode-json",
    "redhat.vscode-yaml",
    "ms-vscode.vscode-docker",
    "github.vscode-pull-request-github"
  ]
}
```

#### Pre-commit Configuration

Create `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
      - id: check-merge-conflict
      - id: check-added-large-files
      - id: check-case-conflict
      - id: check-executables-have-shebangs

  - repo: https://github.com/psf/black
    rev: 23.7.0
    hooks:
      - id: black
        language_version: python3
        args: [--line-length=88]

  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort
        args: [--profile=black]

  - repo: https://github.com/pycqa/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
        args: [--max-line-length=88, --extend-ignore=E203,W503]

  - repo: https://github.com/pycqa/bandit
    rev: 1.7.5
    hooks:
      - id: bandit
        args: [-r, ., -f, json, -o, bandit-report.json]
        exclude: ^tests/

  - repo: https://github.com/antonbabenko/pre-commit-terraform
    rev: v1.81.0
    hooks:
      - id: terraform_fmt
      - id: terraform_validate
      - id: terraform_docs
      - id: terraform_tflint

  - repo: https://github.com/adrienverge/yamllint
    rev: v1.32.0
    hooks:
      - id: yamllint
        args: [-c=.yamllint.yml]
```

## Development Workflow

### Git Workflow

We follow a modified GitFlow workflow with the following branches:

#### Branch Structure

```
main (production)
├── develop (integration)
├── feature/feature-name (feature development)
├── hotfix/issue-description (production fixes)
└── release/version-number (release preparation)
```

#### Branch Naming Conventions

```bash
# Feature branches
feature/add-external-hash-support
feature/improve-error-handling
feature/optimize-lambda-performance

# Bug fix branches
bugfix/fix-s3-upload-timeout
bugfix/correct-hash-validation

# Hotfix branches (for production issues)
hotfix/fix-critical-sync-failure
hotfix/security-patch-dependencies

# Release branches
release/v1.2.0
release/v1.2.1
```

#### Development Process

1. **Start New Feature**
   ```bash
   # Create and switch to feature branch
   git checkout develop
   git pull origin develop
   git checkout -b feature/your-feature-name
   ```

2. **Development Cycle**
   ```bash
   # Make changes and commit frequently
   git add .
   git commit -m "feat: add new functionality for X"
   
   # Push to remote regularly
   git push origin feature/your-feature-name
   ```

3. **Prepare for Review**
   ```bash
   # Rebase on latest develop
   git checkout develop
   git pull origin develop
   git checkout feature/your-feature-name
   git rebase develop
   
   # Run tests and quality checks
   make test
   make lint
   make security-scan
   
   # Push final changes
   git push origin feature/your-feature-name --force-with-lease
   ```

4. **Create Pull Request**
   - Use the PR template
   - Include comprehensive description
   - Add relevant labels and reviewers
   - Link related issues

### Commit Message Standards

We follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

#### Commit Message Format

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

#### Commit Types

```bash
# Feature additions
feat: add support for external hash files
feat(lambda): implement retry logic for failed downloads

# Bug fixes
fix: resolve S3 upload timeout issue
fix(ecs): correct memory allocation for large tasks

# Documentation
docs: update API documentation
docs(readme): add troubleshooting section

# Code style/formatting
style: format code with black
style(terraform): fix indentation in modules

# Refactoring
refactor: simplify hash file processing logic
refactor(monitoring): extract metrics publishing to separate module

# Performance improvements
perf: optimize Lambda cold start time
perf(s3): implement multipart upload for large files

# Tests
test: add unit tests for orchestrator function
test(integration): add end-to-end workflow tests

# Build/CI changes
build: update dependencies to latest versions
ci: add security scanning to pipeline

# Chores (maintenance)
chore: update pre-commit hooks
chore(deps): bump boto3 to latest version
```

### Local Development Commands

Create a `Makefile` for common development tasks:

```makefile
# Makefile for development tasks

.PHONY: help install test lint format security-scan clean build deploy-local

help:  ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install dependencies
	pip install -r requirements.txt
	pip install -r requirements-dev.txt
	pre-commit install

test:  ## Run all tests
	python -m pytest tests/ -v --cov=. --cov-report=html --cov-report=term

test-unit:  ## Run unit tests only
	python -m pytest tests/unit/ -v

test-integration:  ## Run integration tests only
	python -m pytest tests/integration/ -v

test-security:  ## Run security tests only
	python -m pytest tests/security/ -v

lint:  ## Run linting checks
	flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
	flake8 . --count --exit-zero --max-complexity=10 --max-line-length=88 --statistics

format:  ## Format code
	black .
	isort . --profile black

security-scan:  ## Run security scans
	bandit -r . -f json -o bandit-report.json
	safety check
	pip-audit

type-check:  ## Run type checking
	mypy . --ignore-missing-imports

validate-config:  ## Validate configuration
	python scripts/config_processor.py --validate

generate-config:  ## Generate terraform.tfvars files
	python scripts/config_processor.py --generate

terraform-validate:  ## Validate Terraform configuration
	cd terraform && terraform init -backend=false && terraform validate

terraform-plan-local:  ## Plan Terraform for local environment
	cd terraform && terraform plan -var-file=local.tfvars

build-lambda:  ## Build Lambda packages
	./scripts/build-lambda-packages.sh

build-container:  ## Build ECS container
	docker build -t homebrew-bottles-sync:local ./ecs/sync/

start-localstack:  ## Start LocalStack for local testing
	docker-compose -f docker-compose.localstack.yml up -d

stop-localstack:  ## Stop LocalStack
	docker-compose -f docker-compose.localstack.yml down

deploy-local:  ## Deploy to local environment
	./scripts/deploy-local.sh

clean:  ## Clean up build artifacts
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/

docs:  ## Generate documentation
	cd docs && make html

serve-docs:  ## Serve documentation locally
	cd docs/_build/html && python -m http.server 8000
```

## Testing Procedures

### Testing Strategy

Our testing strategy follows the testing pyramid:

```
    /\
   /  \     E2E Tests (5%)
  /____\    Integration Tests (15%)
 /      \   Unit Tests (80%)
/__________\
```

### Unit Testing

#### Test Structure

```
tests/
├── unit/
│   ├── __init__.py
│   ├── test_lambda_orchestrator.py
│   ├── test_lambda_sync_worker.py
│   ├── test_config_processor.py
│   ├── test_homebrew_api.py
│   ├── test_s3_service.py
│   ├── test_notification_service.py
│   └── test_models.py
├── integration/
│   ├── __init__.py
│   ├── test_aws_services.py
│   ├── test_end_to_end_workflows.py
│   └── test_terraform_modules.py
├── security/
│   ├── __init__.py
│   ├── test_iam_policies.py
│   ├── test_secrets_management.py
│   └── test_network_security.py
└── fixtures/
    ├── mock_data.json
    ├── test_bottles.tar.gz
    └── sample_configs.yaml
```

#### Running Tests

```bash
# Run all tests
make test

# Run specific test categories
make test-unit
make test-integration
make test-security

# Run tests with coverage
python -m pytest tests/ --cov=. --cov-report=html --cov-report=term

# Run tests in parallel
python -m pytest tests/ -n auto

# Run tests with specific markers
python -m pytest tests/ -m "not slow"

# Run tests for specific module
python -m pytest tests/unit/test_lambda_orchestrator.py -v

# Run tests with debugging
python -m pytest tests/ -v -s --pdb
```

#### Test Configuration

Create `pytest.ini`:

```ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    -v
    --strict-markers
    --strict-config
    --tb=short
    --cov-report=term-missing
    --cov-fail-under=80
markers =
    unit: Unit tests
    integration: Integration tests
    security: Security tests
    performance: Performance tests
    slow: Slow running tests
    aws: Tests that require AWS services
filterwarnings =
    ignore::DeprecationWarning
    ignore::PendingDeprecationWarning
```

## Code Quality Standards

### Python Code Standards

#### Style Guide

We follow [PEP 8](https://pep8.org/) with some modifications:

- **Line Length**: 88 characters (Black default)
- **Indentation**: 4 spaces
- **Quotes**: Double quotes for strings, single quotes for string literals in code
- **Imports**: Organized using isort with Black profile

#### Type Hints

Use type hints for all function signatures:

```python
from typing import Dict, List, Optional, Union, Tuple, Any
from dataclasses import dataclass
from datetime import datetime

@dataclass
class BottleMetadata:
    """Metadata for a Homebrew bottle."""
    name: str
    version: str
    platform: str
    url: str
    sha256: str
    size: int
    downloaded_at: Optional[datetime] = None

def download_bottle(
    url: str, 
    timeout: int = 30
) -> Tuple[bytes, Dict[str, str]]:
    """Download a bottle from the given URL.
    
    Args:
        url: URL to download the bottle from
        timeout: Request timeout in seconds
        
    Returns:
        Tuple of (bottle_content, response_headers)
        
    Raises:
        requests.RequestException: If download fails
    """
    pass
```

### Terraform Code Standards

#### File Organization

```
terraform/
├── main.tf                 # Main configuration
├── variables.tf           # Input variables
├── outputs.tf            # Output values
├── versions.tf           # Provider versions
├── locals.tf             # Local values
├── data.tf               # Data sources
├── modules/
│   ├── network/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   └── README.md
│   └── compute/
│       ├── main.tf
│       ├── variables.tf
│       ├── outputs.tf
│       └── README.md
└── environments/
    ├── dev/
    │   ├── main.tf
    │   ├── terraform.tfvars
    │   └── backend.hcl
    ├── staging/
    └── prod/
```

## Contribution Guidelines

### Getting Started

1. **Fork the Repository**
   ```bash
   # Fork on GitHub, then clone your fork
   git clone https://github.com/YOUR_USERNAME/homebrew-bottles-sync.git
   cd homebrew-bottles-sync
   
   # Add upstream remote
   git remote add upstream https://github.com/ORIGINAL_OWNER/homebrew-bottles-sync.git
   ```

2. **Set Up Development Environment**
   ```bash
   # Follow the local development setup
   make install
   
   # Verify setup
   make test
   make lint
   ```

3. **Create Feature Branch**
   ```bash
   git checkout develop
   git pull upstream develop
   git checkout -b feature/your-feature-name
   ```

### Contribution Process

#### 1. Planning Phase

- **Create Issue**: Create a GitHub issue describing the feature/bug
- **Discussion**: Discuss the approach with maintainers
- **Design Document**: For large features, create a design document

#### 2. Development Phase

- **Write Tests First**: Follow TDD approach when possible
- **Implement Feature**: Write clean, well-documented code
- **Update Documentation**: Update relevant documentation
- **Test Thoroughly**: Run all test suites

#### 3. Review Phase

- **Self Review**: Review your own changes
- **Create Pull Request**: Use the PR template
- **Address Feedback**: Respond to review comments
- **Final Testing**: Ensure all checks pass

### Pull Request Guidelines

#### PR Template

```markdown
## Description

Brief description of the changes in this PR.

## Type of Change

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Performance improvement
- [ ] Code refactoring

## Testing

- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Security tests pass
- [ ] Manual testing completed

## Checklist

- [ ] My code follows the style guidelines of this project
- [ ] I have performed a self-review of my own code
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] I have made corresponding changes to the documentation
- [ ] My changes generate no new warnings
- [ ] I have added tests that prove my fix is effective or that my feature works
- [ ] New and existing unit tests pass locally with my changes
- [ ] Any dependent changes have been merged and published

## Related Issues

Closes #123
Related to #456

## Additional Notes

Any additional information that reviewers should know.
```

## Code Review Process

### Review Criteria

1. **Functionality**
   - Does the code work as intended?
   - Are edge cases handled?
   - Is error handling appropriate?

2. **Code Quality**
   - Is the code readable and maintainable?
   - Are naming conventions followed?
   - Is the code properly structured?

3. **Testing**
   - Are there adequate tests?
   - Do tests cover edge cases?
   - Are tests maintainable?

4. **Security**
   - Are there any security vulnerabilities?
   - Are secrets handled properly?
   - Are permissions appropriate?

5. **Performance**
   - Are there any performance issues?
   - Is resource usage reasonable?
   - Are there opportunities for optimization?

### Release Process

#### Version Numbering

We follow [Semantic Versioning](https://semver.org/):

- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

Examples:
- `1.0.0` → `1.0.1` (bug fix)
- `1.0.1` → `1.1.0` (new feature)
- `1.1.0` → `2.0.0` (breaking change)

#### Release Workflow

1. **Create Release Branch**
   ```bash
   git checkout develop
   git pull origin develop
   git checkout -b release/v1.2.0
   ```

2. **Prepare Release**
   ```bash
   # Update version numbers
   # Update CHANGELOG.md
   # Run final tests
   make test
   ```

3. **Create Release PR**
   ```bash
   # Create PR from release branch to main
   # Get approval from maintainers
   ```

4. **Deploy and Tag**
   ```bash
   # Merge to main
   git checkout main
   git pull origin main
   git tag v1.2.0
   git push origin v1.2.0
   
   # Merge back to develop
   git checkout develop
   git merge main
   git push origin develop
   ```

This comprehensive development guide provides all the necessary information for contributors to effectively work on the Homebrew Bottles Sync System while maintaining high code quality and security standards.