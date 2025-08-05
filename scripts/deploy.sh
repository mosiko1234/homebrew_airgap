#!/bin/bash

# Homebrew Bottles Sync System - Deployment Script
# This script handles deployment of the infrastructure across different environments

set -euo pipefail

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TERRAFORM_DIR="$PROJECT_ROOT/terraform"

# Default values
ENVIRONMENT="prod"
AWS_REGION="us-east-1"
AUTO_APPROVE=false
DESTROY=false
PLAN_ONLY=false
INIT_ONLY=false
VALIDATE_ONLY=false

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
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

# Usage function
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Deploy Homebrew Bottles Sync System infrastructure

OPTIONS:
    -e, --environment ENV    Environment to deploy (dev, staging, prod) [default: prod]
    -r, --region REGION      AWS region [default: us-east-1]
    -a, --auto-approve       Auto-approve Terraform apply (skip confirmation)
    -d, --destroy           Destroy infrastructure instead of creating
    -p, --plan-only         Only run terraform plan
    -i, --init-only         Only run terraform init
    -v, --validate-only     Only run terraform validate
    -h, --help              Show this help message

EXAMPLES:
    # Deploy to production
    $0 -e prod -r us-east-1

    # Deploy to development with auto-approve
    $0 -e dev -r us-west-2 -a

    # Plan deployment to staging
    $0 -e staging -p

    # Destroy production infrastructure
    $0 -e prod -d

    # Initialize Terraform only
    $0 -i

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -r|--region)
            AWS_REGION="$2"
            shift 2
            ;;
        -a|--auto-approve)
            AUTO_APPROVE=true
            shift
            ;;
        -d|--destroy)
            DESTROY=true
            shift
            ;;
        -p|--plan-only)
            PLAN_ONLY=true
            shift
            ;;
        -i|--init-only)
            INIT_ONLY=true
            shift
            ;;
        -v|--validate-only)
            VALIDATE_ONLY=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Validate environment
if [[ ! "$ENVIRONMENT" =~ ^(dev|staging|prod)$ ]]; then
    log_error "Invalid environment: $ENVIRONMENT. Must be one of: dev, staging, prod"
    exit 1
fi

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if terraform is installed
    if ! command -v terraform &> /dev/null; then
        log_error "Terraform is not installed. Please install Terraform first."
        exit 1
    fi
    
    # Check if AWS CLI is installed
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI is not installed. Please install AWS CLI first."
        exit 1
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS credentials not configured. Please run 'aws configure' first."
        exit 1
    fi
    
    # Check if terraform directory exists
    if [[ ! -d "$TERRAFORM_DIR" ]]; then
        log_error "Terraform directory not found: $TERRAFORM_DIR"
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Initialize Terraform
terraform_init() {
    log_info "Initializing Terraform..."
    cd "$TERRAFORM_DIR"
    
    terraform init \
        -backend-config="key=homebrew-bottles-sync/${ENVIRONMENT}/terraform.tfstate" \
        -backend-config="region=${AWS_REGION}"
    
    log_success "Terraform initialized"
}

# Validate Terraform configuration
terraform_validate() {
    log_info "Validating Terraform configuration..."
    cd "$TERRAFORM_DIR"
    
    terraform validate
    
    log_success "Terraform configuration is valid"
}

# Create Terraform plan
terraform_plan() {
    log_info "Creating Terraform plan..."
    cd "$TERRAFORM_DIR"
    
    local var_file="terraform.tfvars"
    local env_var_file="${ENVIRONMENT}.tfvars"
    
    # Check for environment-specific tfvars file
    if [[ -f "$env_var_file" ]]; then
        log_info "Using environment-specific variables file: $env_var_file"
        var_file="$env_var_file"
    elif [[ -f "$var_file" ]]; then
        log_info "Using default variables file: $var_file"
    else
        log_warning "No terraform.tfvars file found. Using default values."
        var_file=""
    fi
    
    local plan_args=()
    if [[ -n "$var_file" ]]; then
        plan_args+=("-var-file=$var_file")
    fi
    
    # Add environment and region overrides
    plan_args+=("-var=environment=$ENVIRONMENT")
    plan_args+=("-var=aws_region=$AWS_REGION")
    
    if [[ "$DESTROY" == "true" ]]; then
        terraform plan -destroy "${plan_args[@]}" -out="destroy.tfplan"
        log_success "Destroy plan created: destroy.tfplan"
    else
        terraform plan "${plan_args[@]}" -out="terraform.tfplan"
        log_success "Plan created: terraform.tfplan"
    fi
}

# Apply Terraform configuration
terraform_apply() {
    log_info "Applying Terraform configuration..."
    cd "$TERRAFORM_DIR"
    
    local plan_file="terraform.tfplan"
    if [[ "$DESTROY" == "true" ]]; then
        plan_file="destroy.tfplan"
    fi
    
    if [[ ! -f "$plan_file" ]]; then
        log_error "Plan file not found: $plan_file. Run plan first."
        exit 1
    fi
    
    local apply_args=("$plan_file")
    if [[ "$AUTO_APPROVE" == "true" ]]; then
        log_warning "Auto-approve enabled. Applying without confirmation."
    else
        log_info "Review the plan above and confirm to proceed."
        read -p "Do you want to apply this plan? (yes/no): " -r
        if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
            log_info "Deployment cancelled by user."
            exit 0
        fi
    fi
    
    terraform apply "${apply_args[@]}"
    
    if [[ "$DESTROY" == "true" ]]; then
        log_success "Infrastructure destroyed successfully"
    else
        log_success "Infrastructure deployed successfully"
    fi
}

# Show Terraform outputs
show_outputs() {
    if [[ "$DESTROY" == "true" ]]; then
        return
    fi
    
    log_info "Deployment outputs:"
    cd "$TERRAFORM_DIR"
    terraform output
}

# Cleanup function
cleanup() {
    cd "$TERRAFORM_DIR"
    if [[ -f "terraform.tfplan" ]]; then
        rm -f "terraform.tfplan"
        log_info "Cleaned up terraform.tfplan"
    fi
    if [[ -f "destroy.tfplan" ]]; then
        rm -f "destroy.tfplan"
        log_info "Cleaned up destroy.tfplan"
    fi
}

# Main execution
main() {
    log_info "Starting deployment for environment: $ENVIRONMENT in region: $AWS_REGION"
    
    # Set trap for cleanup
    trap cleanup EXIT
    
    check_prerequisites
    
    if [[ "$INIT_ONLY" == "true" ]]; then
        terraform_init
        return
    fi
    
    if [[ "$VALIDATE_ONLY" == "true" ]]; then
        terraform_init
        terraform_validate
        return
    fi
    
    terraform_init
    terraform_validate
    
    if [[ "$PLAN_ONLY" == "true" ]]; then
        terraform_plan
        return
    fi
    
    terraform_plan
    terraform_apply
    show_outputs
    
    if [[ "$DESTROY" == "true" ]]; then
        log_success "Destruction completed for environment: $ENVIRONMENT"
    else
        log_success "Deployment completed for environment: $ENVIRONMENT"
        log_info "You can view the CloudWatch dashboard and monitor the system."
        log_info "Check the outputs above for important resource information."
    fi
}

# Run main function
main "$@"