#!/bin/bash
# Environment-specific deployment orchestration script
# Handles deployment to dev, staging, or production environments

set -euo pipefail

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TERRAFORM_DIR="${PROJECT_ROOT}/terraform"

# Default values
ENVIRONMENT=""
ACTION="deploy"
AUTO_APPROVE=false
SKIP_VALIDATION=false
ROLLBACK_VERSION=""
DRY_RUN=false

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
Usage: $0 -e ENVIRONMENT [OPTIONS]

Environment-specific deployment orchestration script

REQUIRED:
    -e, --environment ENVIRONMENT    Target environment (dev, staging, prod)

OPTIONS:
    -a, --action ACTION             Action to perform (deploy, destroy, plan, rollback)
    -y, --auto-approve             Auto-approve Terraform changes
    -s, --skip-validation          Skip configuration validation
    -r, --rollback VERSION         Rollback to specific version (for rollback action)
    -d, --dry-run                  Perform dry run without making changes
    -h, --help                     Show this help message

EXAMPLES:
    $0 -e dev                      Deploy to development environment
    $0 -e staging -a plan          Plan staging deployment
    $0 -e prod -y                  Deploy to production with auto-approve
    $0 -e dev -a rollback -r v1.2.3  Rollback dev to version v1.2.3

EOF
}# Pars
e command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -e|--environment)
                ENVIRONMENT="$2"
                shift 2
                ;;
            -a|--action)
                ACTION="$2"
                shift 2
                ;;
            -y|--auto-approve)
                AUTO_APPROVE=true
                shift
                ;;
            -s|--skip-validation)
                SKIP_VALIDATION=true
                shift
                ;;
            -r|--rollback)
                ROLLBACK_VERSION="$2"
                shift 2
                ;;
            -d|--dry-run)
                DRY_RUN=true
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

    # Validate required arguments
    if [[ -z "$ENVIRONMENT" ]]; then
        log_error "Environment is required"
        usage
        exit 1
    fi

    # Validate environment
    if [[ ! "$ENVIRONMENT" =~ ^(dev|staging|prod)$ ]]; then
        log_error "Invalid environment: $ENVIRONMENT. Must be dev, staging, or prod"
        exit 1
    fi

    # Validate action
    if [[ ! "$ACTION" =~ ^(deploy|destroy|plan|rollback)$ ]]; then
        log_error "Invalid action: $ACTION. Must be deploy, destroy, plan, or rollback"
        exit 1
    fi

    # Validate rollback version if action is rollback
    if [[ "$ACTION" == "rollback" && -z "$ROLLBACK_VERSION" ]]; then
        log_error "Rollback version is required for rollback action"
        exit 1
    fi
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check if terraform is installed
    if ! command -v terraform &> /dev/null; then
        log_error "Terraform is not installed or not in PATH"
        exit 1
    fi

    # Check if aws CLI is installed
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI is not installed or not in PATH"
        exit 1
    fi

    # Check if jq is installed
    if ! command -v jq &> /dev/null; then
        log_error "jq is not installed or not in PATH"
        exit 1
    fi

    # Check if environment directory exists
    local env_dir="${TERRAFORM_DIR}/environments/${ENVIRONMENT}"
    if [[ ! -d "$env_dir" ]]; then
        log_error "Environment directory does not exist: $env_dir"
        exit 1
    fi

    # Check if terraform.tfvars exists
    local tfvars_file="${env_dir}/terraform.tfvars"
    if [[ ! -f "$tfvars_file" ]]; then
        log_error "terraform.tfvars file does not exist: $tfvars_file"
        exit 1
    fi

    log_success "Prerequisites check passed"
}# Valid
ate configuration
validate_configuration() {
    if [[ "$SKIP_VALIDATION" == "true" ]]; then
        log_warning "Skipping configuration validation"
        return 0
    fi

    log_info "Validating configuration..."

    # Run config processor validation
    if ! python3 "${SCRIPT_DIR}/config_processor.py" --validate; then
        log_error "Configuration validation failed"
        exit 1
    fi

    log_success "Configuration validation passed"
}

# Initialize Terraform
init_terraform() {
    log_info "Initializing Terraform for $ENVIRONMENT environment..."

    local env_dir="${TERRAFORM_DIR}/environments/${ENVIRONMENT}"
    cd "$env_dir"

    # Check if backend configuration exists
    local backend_config="${env_dir}/backend.hcl"
    if [[ -f "$backend_config" ]]; then
        log_info "Using backend configuration: $backend_config"
        terraform init -backend-config="$backend_config"
    else
        log_warning "No backend configuration found, using local state"
        terraform init
    fi

    log_success "Terraform initialized"
}

# Plan deployment
plan_deployment() {
    log_info "Planning deployment for $ENVIRONMENT environment..."

    local env_dir="${TERRAFORM_DIR}/environments/${ENVIRONMENT}"
    cd "$env_dir"

    local plan_file="${env_dir}/terraform.plan"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "Dry run mode - showing plan without saving"
        terraform plan -var-file="terraform.tfvars"
    else
        terraform plan -var-file="terraform.tfvars" -out="$plan_file"
        log_success "Plan saved to: $plan_file"
    fi
}

# Apply deployment
apply_deployment() {
    log_info "Applying deployment for $ENVIRONMENT environment..."

    local env_dir="${TERRAFORM_DIR}/environments/${ENVIRONMENT}"
    cd "$env_dir"

    local plan_file="${env_dir}/terraform.plan"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "Dry run mode - skipping apply"
        return 0
    fi

    # Create deployment record
    create_deployment_record "started"

    if [[ "$AUTO_APPROVE" == "true" ]]; then
        if [[ -f "$plan_file" ]]; then
            terraform apply "$plan_file"
        else
            terraform apply -var-file="terraform.tfvars" -auto-approve
        fi
    else
        if [[ -f "$plan_file" ]]; then
            terraform apply "$plan_file"
        else
            terraform apply -var-file="terraform.tfvars"
        fi
    fi

    # Update deployment record
    if [[ $? -eq 0 ]]; then
        create_deployment_record "success"
        log_success "Deployment completed successfully"
    else
        create_deployment_record "failed"
        log_error "Deployment failed"
        exit 1
    fi
}# Des
troy deployment
destroy_deployment() {
    log_warning "Destroying deployment for $ENVIRONMENT environment..."

    if [[ "$ENVIRONMENT" == "prod" ]]; then
        log_error "Production environment destruction requires manual confirmation"
        read -p "Are you sure you want to destroy the production environment? (type 'yes' to confirm): " confirm
        if [[ "$confirm" != "yes" ]]; then
            log_info "Destruction cancelled"
            exit 0
        fi
    fi

    local env_dir="${TERRAFORM_DIR}/environments/${ENVIRONMENT}"
    cd "$env_dir"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "Dry run mode - showing destroy plan"
        terraform plan -destroy -var-file="terraform.tfvars"
        return 0
    fi

    # Create deployment record
    create_deployment_record "destroy_started"

    if [[ "$AUTO_APPROVE" == "true" ]]; then
        terraform destroy -var-file="terraform.tfvars" -auto-approve
    else
        terraform destroy -var-file="terraform.tfvars"
    fi

    # Update deployment record
    if [[ $? -eq 0 ]]; then
        create_deployment_record "destroyed"
        log_success "Deployment destroyed successfully"
    else
        create_deployment_record "destroy_failed"
        log_error "Deployment destruction failed"
        exit 1
    fi
}

# Rollback deployment
rollback_deployment() {
    log_info "Rolling back $ENVIRONMENT environment to version $ROLLBACK_VERSION..."

    # This is a placeholder for rollback functionality
    # In a real implementation, this would:
    # 1. Check if the rollback version exists
    # 2. Retrieve the Terraform state for that version
    # 3. Apply the previous configuration
    # 4. Update deployment records

    log_warning "Rollback functionality is not yet implemented"
    log_info "Manual rollback steps:"
    log_info "1. Checkout the desired version: git checkout $ROLLBACK_VERSION"
    log_info "2. Run deployment: $0 -e $ENVIRONMENT -a deploy"
    
    exit 1
}

# Create deployment record
create_deployment_record() {
    local status="$1"
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    local commit_sha=$(git rev-parse HEAD 2>/dev/null || echo "unknown")
    local user=$(whoami)

    local record_dir="${PROJECT_ROOT}/.deployment-records"
    mkdir -p "$record_dir"

    local record_file="${record_dir}/${ENVIRONMENT}-$(date +%Y%m%d-%H%M%S).json"

    cat > "$record_file" << EOF
{
  "environment": "$ENVIRONMENT",
  "action": "$ACTION",
  "status": "$status",
  "timestamp": "$timestamp",
  "commit_sha": "$commit_sha",
  "user": "$user",
  "terraform_version": "$(terraform version -json | jq -r '.terraform_version')",
  "rollback_version": "$ROLLBACK_VERSION"
}
EOF

    log_info "Deployment record created: $record_file"
}# S
end deployment notification
send_notification() {
    local status="$1"
    local message="$2"

    # Check if notification script exists
    local notify_script="${SCRIPT_DIR}/notify_deployment.py"
    if [[ -f "$notify_script" ]]; then
        python3 "$notify_script" \
            --environment "$ENVIRONMENT" \
            --action "$ACTION" \
            --status "$status" \
            --message "$message" \
            --commit "$(git rev-parse HEAD 2>/dev/null || echo 'unknown')" \
            --user "$(whoami)"
    else
        log_warning "Notification script not found: $notify_script"
    fi
}

# Main execution function
main() {
    log_info "Starting deployment orchestration..."
    log_info "Environment: $ENVIRONMENT"
    log_info "Action: $ACTION"
    log_info "Auto-approve: $AUTO_APPROVE"
    log_info "Dry run: $DRY_RUN"

    # Parse arguments and validate
    check_prerequisites
    validate_configuration

    # Change to environment directory
    local env_dir="${TERRAFORM_DIR}/environments/${ENVIRONMENT}"
    cd "$env_dir"

    # Initialize Terraform
    init_terraform

    # Execute the requested action
    case "$ACTION" in
        plan)
            plan_deployment
            send_notification "planned" "Deployment plan completed for $ENVIRONMENT"
            ;;
        deploy)
            plan_deployment
            apply_deployment
            send_notification "success" "Deployment completed successfully for $ENVIRONMENT"
            ;;
        destroy)
            destroy_deployment
            send_notification "destroyed" "Environment $ENVIRONMENT destroyed"
            ;;
        rollback)
            rollback_deployment
            send_notification "rolled_back" "Environment $ENVIRONMENT rolled back to $ROLLBACK_VERSION"
            ;;
        *)
            log_error "Unknown action: $ACTION"
            exit 1
            ;;
    esac

    log_success "Deployment orchestration completed"
}

# Parse arguments and run main function
parse_args "$@"
main