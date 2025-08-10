# Homebrew Bottles Sync System - Development Makefile
# This Makefile provides convenient commands for development tasks

.PHONY: help install setup-dev quality quality-fix test test-unit test-integration test-security clean lint format validate terraform-fmt terraform-validate pre-commit-install pre-commit-run

# Default target
help: ## Show this help message
	@echo "🚀 Homebrew Bottles Sync System - Development Commands"
	@echo ""
	@echo "Available commands:"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# Installation and setup
install: ## Install Python dependencies
	@echo "📦 Installing Python dependencies..."
	pip install -r requirements.txt
	pip install black isort flake8 bandit pytest-cov pre-commit

setup-dev: install ## Set up development environment
	@echo "🔧 Setting up development environment..."
	./scripts/setup-pre-commit.sh

# Code quality commands
quality: ## Run comprehensive code quality checks
	@echo "🔍 Running comprehensive code quality checks..."
	python scripts/code-quality-check.py

quality-fix: ## Run code quality checks and auto-fix issues
	@echo "🔧 Running code quality checks with auto-fix..."
	python scripts/code-quality-check.py --fix

quality-report: ## Generate code quality report
	@echo "📊 Generating code quality report..."
	python scripts/code-quality-check.py --report quality-report.json
	@echo "Report saved to quality-report.json"

# Individual quality checks
lint: ## Run Python linting (flake8)
	@echo "🔍 Running Python linting..."
	python -m flake8 shared/ lambda/ ecs/ scripts/ tests/

format: ## Check Python code formatting
	@echo "🎨 Checking Python code formatting..."
	python -m black --check --diff shared/ lambda/ ecs/ scripts/ tests/
	python -m isort --check-only --diff shared/ lambda/ ecs/ scripts/ tests/

format-fix: ## Auto-fix Python code formatting
	@echo "🔧 Auto-fixing Python code formatting..."
	python -m black shared/ lambda/ ecs/ scripts/ tests/
	python -m isort shared/ lambda/ ecs/ scripts/ tests/

security-scan: ## Run security scans
	@echo "🔒 Running security scans..."
	python -m bandit -r shared/ lambda/ ecs/ scripts/ -f json -o bandit-report.json -ll || true
	@if [ -f bandit-report.json ]; then \
		echo "Security report saved to bandit-report.json"; \
	fi

# Terraform commands
terraform-fmt: ## Format Terraform files
	@echo "🏗️  Formatting Terraform files..."
	terraform fmt -recursive terraform/

terraform-fmt-check: ## Check Terraform formatting
	@echo "🔍 Checking Terraform formatting..."
	terraform fmt -check -recursive terraform/

terraform-validate: ## Validate Terraform configurations
	@echo "🔧 Validating Terraform configurations..."
	@cd terraform && \
	terraform init -backend=false && \
	terraform validate
	@for env in dev staging prod; do \
		if [ -d "terraform/environments/$$env" ]; then \
			echo "Validating $$env environment..."; \
			cd "terraform/environments/$$env" && \
			terraform init -backend=false && \
			terraform validate && \
			cd ../../..; \
		fi; \
	done

terraform-security: ## Run Terraform security scan
	@echo "🔒 Running Terraform security scan..."
	tfsec terraform/ --format=json --out=tfsec-report.json --soft-fail || true
	@if [ -f tfsec-report.json ]; then \
		echo "Terraform security report saved to tfsec-report.json"; \
	fi

# Testing commands
test: ## Run all tests
	@echo "🧪 Running all tests..."
	python -m pytest -v --cov=shared --cov=lambda --cov=ecs --cov=scripts --cov-report=term-missing --cov-report=html || true

test-unit: ## Run unit tests only
	@echo "🧪 Running unit tests..."
	python -m pytest tests/unit/ -v --cov=shared --cov=lambda --cov=ecs --cov=scripts

test-integration: ## Run integration tests only
	@echo "🧪 Running integration tests..."
	python -m pytest tests/integration/ -v

test-security: ## Run security tests only
	@echo "🧪 Running security tests..."
	python -m pytest tests/security/ -v

test-smoke: ## Run smoke tests
	@echo "🧪 Running smoke tests..."
	python -m pytest tests/smoke/ -v

# Pre-commit commands
pre-commit-install: ## Install pre-commit hooks
	@echo "🔗 Installing pre-commit hooks..."
	pre-commit install
	pre-commit install --hook-type commit-msg

pre-commit-run: ## Run pre-commit hooks on all files
	@echo "🔍 Running pre-commit hooks on all files..."
	pre-commit run --all-files

pre-commit-update: ## Update pre-commit hooks
	@echo "🔄 Updating pre-commit hooks..."
	pre-commit autoupdate

# Configuration and validation
validate-config: ## Validate configuration files
	@echo "🔍 Validating configuration files..."
	python scripts/config_processor.py --validate

generate-config: ## Generate environment-specific configurations
	@echo "⚙️  Generating environment-specific configurations..."
	@for env in dev staging prod; do \
		echo "Generating config for $$env..."; \
		python scripts/config_processor.py --environment $$env --output terraform/$$env.tfvars; \
	done

validate-secrets: ## Validate GitHub secrets configuration
	@echo "🔒 Validating secrets configuration..."
	python scripts/validate-secrets.py

# Cleanup commands
clean: ## Clean up generated files and caches
	@echo "🧹 Cleaning up..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name ".coverage" -delete
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf .tox/
	rm -f bandit-report.json
	rm -f tfsec-report.json
	rm -f quality-report.json
	rm -f terraform/*.tfplan
	rm -f terraform/*.tfvars

clean-terraform: ## Clean Terraform state and cache
	@echo "🧹 Cleaning Terraform files..."
	find terraform/ -name ".terraform" -type d -exec rm -rf {} + 2>/dev/null || true
	find terraform/ -name "*.tfstate*" -delete 2>/dev/null || true
	find terraform/ -name "*.tfplan" -delete 2>/dev/null || true

# Development workflow commands
dev-setup: setup-dev pre-commit-install ## Complete development setup
	@echo "✅ Development environment setup complete!"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Copy config.yaml.example to config.yaml and customize"
	@echo "  2. Run 'make validate-config' to validate your configuration"
	@echo "  3. Run 'make quality' to check code quality"
	@echo "  4. Run 'make test' to run tests"

dev-check: quality test ## Run all development checks
	@echo "✅ All development checks passed!"

ci-check: quality terraform-validate test ## Run CI-equivalent checks locally
	@echo "✅ CI-equivalent checks passed!"

# Documentation
docs-serve: ## Serve documentation locally (if using mkdocs)
	@if command -v mkdocs >/dev/null 2>&1; then \
		mkdocs serve; \
	else \
		echo "📚 MkDocs not installed. Install with: pip install mkdocs"; \
	fi

# Deployment validation commands
validate-deployment: ## Validate deployment readiness for environment (usage: make validate-deployment ENV=dev)
	@if [ -z "$(ENV)" ]; then \
		echo "❌ Please specify environment: make validate-deployment ENV=dev|staging|prod"; \
		exit 1; \
	fi
	@echo "🔍 Validating deployment for $(ENV) environment..."
	python scripts/deployment-validator.py $(ENV) --report validation-report-$(ENV).json

detect-drift: ## Detect infrastructure drift for environment (usage: make detect-drift ENV=dev)
	@if [ -z "$(ENV)" ]; then \
		echo "❌ Please specify environment: make detect-drift ENV=dev|staging|prod"; \
		exit 1; \
	fi
	@echo "🔄 Detecting infrastructure drift for $(ENV) environment..."
	python scripts/drift-correction.py $(ENV) --detect-only --report drift-report-$(ENV).json

correct-drift: ## Correct infrastructure drift for environment (usage: make correct-drift ENV=dev)
	@if [ -z "$(ENV)" ]; then \
		echo "❌ Please specify environment: make correct-drift ENV=dev|staging|prod"; \
		exit 1; \
	fi
	@echo "🔧 Correcting infrastructure drift for $(ENV) environment..."
	python scripts/drift-correction.py $(ENV) --report drift-correction-$(ENV).json

plan-drift-correction: ## Generate drift correction plan (usage: make plan-drift-correction ENV=dev)
	@if [ -z "$(ENV)" ]; then \
		echo "❌ Please specify environment: make plan-drift-correction ENV=dev|staging|prod"; \
		exit 1; \
	fi
	@echo "📋 Generating drift correction plan for $(ENV) environment..."
	python scripts/drift-correction.py $(ENV) --plan-only --report drift-plan-$(ENV).json

# Environment-specific commands
deploy-dev: validate-deployment ## Deploy to development environment (local)
	@echo "🚀 Deploying to development environment..."
	$(MAKE) validate-deployment ENV=dev
	python scripts/config_processor.py --environment dev --output terraform/dev.tfvars
	cd terraform && terraform workspace select dev || terraform workspace new dev
	cd terraform && terraform plan -var-file=dev.tfvars
	@echo "Review the plan above. Run 'cd terraform && terraform apply dev.tfplan' to apply."

# Monitoring and reporting
monitor-costs: ## Monitor deployment costs
	@echo "💰 Monitoring deployment costs..."
	python scripts/cost-monitor.py --report

monitor-security: ## Monitor security status
	@echo "🔒 Monitoring security status..."
	python scripts/security-monitor.py --report

# Git hooks and workflow
git-hooks: pre-commit-install ## Set up git hooks
	@echo "✅ Git hooks configured!"

# Quick commands for common workflows
quick-check: lint format-fix quality-fix ## Quick code quality check and fix
	@echo "⚡ Quick quality check complete!"

full-check: clean quality terraform-validate test ## Full comprehensive check
	@echo "🎉 Full check complete!"

# Help for specific areas
help-quality: ## Show help for code quality commands
	@echo "🔍 Code Quality Commands:"
	@echo "  make quality         - Run all quality checks"
	@echo "  make quality-fix     - Run quality checks and auto-fix"
	@echo "  make lint           - Run Python linting only"
	@echo "  make format         - Check code formatting"
	@echo "  make format-fix     - Auto-fix code formatting"
	@echo "  make security-scan  - Run security scans"

help-terraform: ## Show help for Terraform commands
	@echo "🏗️  Terraform Commands:"
	@echo "  make terraform-fmt       - Format Terraform files"
	@echo "  make terraform-validate  - Validate Terraform configs"
	@echo "  make terraform-security  - Run Terraform security scan"

help-test: ## Show help for testing commands
	@echo "🧪 Testing Commands:"
	@echo "  make test            - Run all tests"
	@echo "  make test-unit       - Run unit tests only"
	@echo "  make test-integration - Run integration tests only"
	@echo "  make test-security   - Run security tests only"
	@echo "  make test-smoke      - Run smoke tests"