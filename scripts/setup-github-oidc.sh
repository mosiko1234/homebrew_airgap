#!/bin/bash
# Setup GitHub OIDC Provider in AWS
# This script creates the OIDC identity provider for GitHub Actions

set -euo pipefail

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

Setup GitHub OIDC Provider in AWS for secure CI/CD authentication

OPTIONS:
    -r, --region REGION        AWS region (default: us-east-1)
    -a, --account-id ID        AWS account ID (auto-detected if not provided)
    -c, --check-only           Only check if OIDC provider exists
    -d, --delete               Delete the OIDC provider
    -h, --help                 Show this help message

EXAMPLES:
    $0                         Create OIDC provider in default region
    $0 -r us-west-2           Create OIDC provider in us-west-2
    $0 -c                     Check if OIDC provider exists
    $0 -d                     Delete OIDC provider

EOF
}

# Default values
AWS_REGION="us-east-1"
AWS_ACCOUNT_ID=""
CHECK_ONLY=false
DELETE_PROVIDER=false

# GitHub OIDC configuration
GITHUB_OIDC_URL="https://token.actions.githubusercontent.com"
GITHUB_THUMBPRINT="6938fd4d98bab03faadb97b34396831e3780aea1"

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -r|--region)
                AWS_REGION="$2"
                shift 2
                ;;
            -a|--account-id)
                AWS_ACCOUNT_ID="$2"
                shift 2
                ;;
            -c|--check-only)
                CHECK_ONLY=true
                shift
                ;;
            -d|--delete)
                DELETE_PROVIDER=true
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
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check if AWS CLI is installed
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI is not installed or not in PATH"
        exit 1
    fi

    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS credentials not configured or invalid"
        exit 1
    fi

    # Get AWS account ID if not provided
    if [[ -z "$AWS_ACCOUNT_ID" ]]; then
        AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
        log_info "Detected AWS Account ID: $AWS_ACCOUNT_ID"
    fi

    log_success "Prerequisites check passed"
}

# Check if OIDC provider exists
check_oidc_provider() {
    log_info "Checking if GitHub OIDC provider exists..."

    local provider_arn="arn:aws:iam::${AWS_ACCOUNT_ID}:oidc-provider/token.actions.githubusercontent.com"
    
    if aws iam get-open-id-connect-provider --open-id-connect-provider-arn "$provider_arn" &> /dev/null; then
        log_success "GitHub OIDC provider already exists: $provider_arn"
        return 0
    else
        log_info "GitHub OIDC provider does not exist"
        return 1
    fi
}

# Create OIDC provider
create_oidc_provider() {
    log_info "Creating GitHub OIDC provider..."

    local provider_arn
    provider_arn=$(aws iam create-open-id-connect-provider \
        --url "$GITHUB_OIDC_URL" \
        --thumbprint-list "$GITHUB_THUMBPRINT" \
        --client-id-list "sts.amazonaws.com" \
        --query 'OpenIDConnectProviderArn' \
        --output text)

    if [[ $? -eq 0 ]]; then
        log_success "GitHub OIDC provider created: $provider_arn"
        
        # Add tags to the provider
        aws iam tag-open-id-connect-provider \
            --open-id-connect-provider-arn "$provider_arn" \
            --tags Key=Purpose,Value=github-actions Key=ManagedBy,Value=homebrew-bottles-sync
        
        log_info "OIDC provider tagged successfully"
        return 0
    else
        log_error "Failed to create GitHub OIDC provider"
        return 1
    fi
}

# Delete OIDC provider
delete_oidc_provider() {
    log_warning "Deleting GitHub OIDC provider..."

    local provider_arn="arn:aws:iam::${AWS_ACCOUNT_ID}:oidc-provider/token.actions.githubusercontent.com"
    
    read -p "Are you sure you want to delete the GitHub OIDC provider? (type 'yes' to confirm): " confirm
    if [[ "$confirm" != "yes" ]]; then
        log_info "Deletion cancelled"
        return 0
    fi

    if aws iam delete-open-id-connect-provider --open-id-connect-provider-arn "$provider_arn"; then
        log_success "GitHub OIDC provider deleted: $provider_arn"
        return 0
    else
        log_error "Failed to delete GitHub OIDC provider"
        return 1
    fi
}

# Display setup instructions
display_setup_instructions() {
    log_info "GitHub OIDC Provider Setup Complete!"
    echo ""
    echo -e "${BLUE}Next Steps:${NC}"
    echo "1. Deploy the GitHub OIDC Terraform module to create IAM roles:"
    echo "   cd terraform && terraform init"
    echo "   terraform apply -target=module.github_oidc"
    echo ""
    echo "2. Update your GitHub repository settings:"
    echo "   - Go to Settings > Secrets and variables > Actions"
    echo "   - Add environment-specific secrets:"
    echo ""
    echo -e "${YELLOW}Development Environment:${NC}"
    echo "   AWS_ROLE_ARN_DEV: arn:aws:iam::${AWS_ACCOUNT_ID}:role/homebrew-bottles-sync-dev-github-actions-role"
    echo ""
    echo -e "${YELLOW}Staging Environment:${NC}"
    echo "   AWS_ROLE_ARN_STAGING: arn:aws:iam::${AWS_ACCOUNT_ID}:role/homebrew-bottles-sync-staging-github-actions-role"
    echo ""
    echo -e "${YELLOW}Production Environment:${NC}"
    echo "   AWS_ROLE_ARN_PROD: arn:aws:iam::${AWS_ACCOUNT_ID}:role/homebrew-bottles-sync-prod-github-actions-role"
    echo ""
    echo "3. Configure additional secrets:"
    echo "   SLACK_WEBHOOK_URL: Your Slack webhook URL for notifications"
    echo "   NOTIFICATION_EMAIL: Email address for critical alerts"
    echo ""
    echo "4. Update your GitHub Actions workflows to use OIDC authentication:"
    echo "   - Add 'id-token: write' permission to workflow jobs"
    echo "   - Use aws-actions/configure-aws-credentials@v4 with role-to-assume"
    echo ""
    echo "5. Deploy the environments:"
    echo "   ./scripts/deploy.sh deploy -e dev"
    echo "   ./scripts/deploy.sh deploy -e staging"
    echo "   ./scripts/deploy.sh deploy -e prod"
    echo ""
}

# Main execution function
main() {
    log_info "GitHub OIDC Provider Setup"
    log_info "AWS Region: $AWS_REGION"
    
    # Set AWS region
    export AWS_DEFAULT_REGION="$AWS_REGION"
    
    # Check prerequisites
    check_prerequisites
    
    if [[ "$DELETE_PROVIDER" == "true" ]]; then
        delete_oidc_provider
        return $?
    fi
    
    if [[ "$CHECK_ONLY" == "true" ]]; then
        check_oidc_provider
        return $?
    fi
    
    # Check if provider already exists
    if check_oidc_provider; then
        log_info "OIDC provider already configured"
        display_setup_instructions
        return 0
    fi
    
    # Create OIDC provider
    if create_oidc_provider; then
        display_setup_instructions
        return 0
    else
        log_error "Failed to setup GitHub OIDC provider"
        return 1
    fi
}

# Parse arguments and run main function
parse_args "$@"
main