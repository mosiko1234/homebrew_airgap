#!/bin/bash

# Terraform validation script
# This script validates the Terraform configuration and checks for common issues

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TERRAFORM_DIR="$PROJECT_ROOT/terraform"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    if ! command -v terraform &> /dev/null; then
        log_error "Terraform is not installed"
        return 1
    fi
    
    if [[ ! -d "$TERRAFORM_DIR" ]]; then
        log_error "Terraform directory not found: $TERRAFORM_DIR"
        return 1
    fi
    
    log_success "Prerequisites check passed"
}

# Validate Terraform syntax
validate_syntax() {
    log_info "Validating Terraform syntax..."
    cd "$TERRAFORM_DIR"
    
    if terraform validate; then
        log_success "Terraform syntax validation passed"
    else
        log_error "Terraform syntax validation failed"
        return 1
    fi
}

# Check for required files
check_required_files() {
    log_info "Checking for required files..."
    
    local required_files=(
        "main.tf"
        "variables.tf"
        "outputs.tf"
        "terraform.tfvars.example"
    )
    
    local missing_files=()
    
    for file in "${required_files[@]}"; do
        if [[ ! -f "$TERRAFORM_DIR/$file" ]]; then
            missing_files+=("$file")
        fi
    done
    
    if [[ ${#missing_files[@]} -gt 0 ]]; then
        log_error "Missing required files: ${missing_files[*]}"
        return 1
    fi
    
    log_success "All required files present"
}

# Check module structure
check_modules() {
    log_info "Checking module structure..."
    
    local required_modules=(
        "modules/network"
        "modules/s3"
        "modules/iam"
        "modules/lambda"
        "modules/ecs"
        "modules/eventbridge"
        "modules/notifications"
        "modules/monitoring"
    )
    
    local missing_modules=()
    
    for module in "${required_modules[@]}"; do
        if [[ ! -d "$TERRAFORM_DIR/$module" ]]; then
            missing_modules+=("$module")
        fi
    done
    
    if [[ ${#missing_modules[@]} -gt 0 ]]; then
        log_error "Missing required modules: ${missing_modules[*]}"
        return 1
    fi
    
    log_success "All required modules present"
}

# Format check
format_check() {
    log_info "Checking Terraform formatting..."
    cd "$TERRAFORM_DIR"
    
    if terraform fmt -check -recursive; then
        log_success "Terraform formatting is correct"
    else
        log_warning "Terraform formatting issues found. Run 'terraform fmt -recursive' to fix."
        return 1
    fi
}

# Security check (basic)
security_check() {
    log_info "Running basic security checks..."
    
    # Check for hardcoded secrets
    if grep -r "AKIA\|password\|secret" "$TERRAFORM_DIR" --exclude-dir=.terraform --exclude="*.tfvars*" | grep -v "description\|variable\|output"; then
        log_error "Potential hardcoded secrets found"
        return 1
    fi
    
    log_success "Basic security checks passed"
}

# Check deployment scripts
check_deployment_scripts() {
    log_info "Checking deployment scripts..."
    
    local required_scripts=(
        "scripts/deploy.sh"
        "scripts/build-lambda-packages.sh"
        "scripts/deploy-dev.sh"
        "scripts/deploy-staging.sh"
        "scripts/deploy-prod.sh"
    )
    
    local missing_scripts=()
    
    for script in "${required_scripts[@]}"; do
        if [[ ! -f "$PROJECT_ROOT/$script" ]]; then
            missing_scripts+=("$script")
        elif [[ ! -x "$PROJECT_ROOT/$script" ]]; then
            log_warning "Script not executable: $script"
            chmod +x "$PROJECT_ROOT/$script"
        fi
    done
    
    if [[ ${#missing_scripts[@]} -gt 0 ]]; then
        log_error "Missing required scripts: ${missing_scripts[*]}"
        return 1
    fi
    
    log_success "All deployment scripts present and executable"
}

# Main validation function
main() {
    log_info "Starting Terraform configuration validation..."
    
    local checks=(
        "check_prerequisites"
        "check_required_files"
        "check_modules"
        "check_deployment_scripts"
        "validate_syntax"
        "format_check"
        "security_check"
    )
    
    local failed_checks=()
    
    for check in "${checks[@]}"; do
        if ! $check; then
            failed_checks+=("$check")
        fi
    done
    
    if [[ ${#failed_checks[@]} -gt 0 ]]; then
        log_error "Validation failed. Failed checks: ${failed_checks[*]}"
        exit 1
    fi
    
    log_success "All validation checks passed!"
    log_info "Your Terraform configuration is ready for deployment."
    log_info "Next steps:"
    log_info "1. Build Lambda packages: ./scripts/build-lambda-packages.sh"
    log_info "2. Configure variables: cp terraform/terraform.tfvars.example terraform/terraform.tfvars"
    log_info "3. Deploy infrastructure: ./scripts/deploy.sh"
}

main "$@"