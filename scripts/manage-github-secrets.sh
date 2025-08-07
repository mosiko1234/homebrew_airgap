#!/bin/bash
# GitHub Secrets Management Script
# This script helps manage GitHub repository secrets for CI/CD

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
Usage: $0 [COMMAND] [OPTIONS]

Manage GitHub repository secrets for CI/CD

COMMANDS:
    validate        Validate that all required secrets are configured
    list           List all configured secrets
    template       Generate secrets template
    rotate         Help with secrets rotation
    setup          Interactive setup of secrets

OPTIONS:
    -r, --repo REPO        GitHub repository in format 'owner/repo'
    -t, --token TOKEN      GitHub personal access token
    -e, --environment ENV  Specific environment (dev, staging, prod)
    -f, --file FILE        Configuration file path
    -v, --verbose          Enable verbose output
    -h, --help             Show this help message

EXAMPLES:
    $0 validate -r myorg/myrepo
    $0 template > secrets.env
    $0 setup -r myorg/myrepo -t ghp_xxx
    $0 rotate -e prod

REQUIRED SECRETS:
    AWS_ROLE_ARN_DEV       - IAM role ARN for dev environment
    AWS_ROLE_ARN_STAGING   - IAM role ARN for staging environment  
    AWS_ROLE_ARN_PROD      - IAM role ARN for prod environment
    SLACK_WEBHOOK_URL      - Slack webhook for notifications
    NOTIFICATION_EMAIL     - Email for critical alerts
    TERRAFORM_STATE_BUCKET - S3 bucket for Terraform state
    TERRAFORM_LOCK_TABLE   - DynamoDB table for state locking

EOF
}

# Default values
GITHUB_REPO=""
GITHUB_TOKEN=""
ENVIRONMENT=""
CONFIG_FILE=""
VERBOSE=false
COMMAND=""

# Required secrets configuration
declare -A REQUIRED_SECRETS=(
    ["AWS_ROLE_ARN_DEV"]="IAM role ARN for development environment deployments"
    ["AWS_ROLE_ARN_STAGING"]="IAM role ARN for staging environment deployments"
    ["AWS_ROLE_ARN_PROD"]="IAM role ARN for production environment deployments"
    ["SLACK_WEBHOOK_URL"]="Slack webhook URL for deployment notifications"
    ["NOTIFICATION_EMAIL"]="Email address for critical deployment alerts"
    ["TERRAFORM_STATE_BUCKET"]="S3 bucket name for Terraform state storage"
    ["TERRAFORM_LOCK_TABLE"]="DynamoDB table name for Terraform state locking"
)

# Optional secrets
declare -A OPTIONAL_SECRETS=(
    ["DOCKER_REGISTRY_URL"]="Custom Docker registry URL (defaults to ECR)"
    ["CUSTOM_DOMAIN"]="Custom domain for the application"
    ["MONITORING_API_KEY"]="API key for external monitoring service"
)

# Parse command line arguments
parse_args() {
    if [[ $# -eq 0 ]]; then
        usage
        exit 1
    fi
    
    COMMAND="$1"
    shift
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            -r|--repo)
                GITHUB_REPO="$2"
                shift 2
                ;;
            -t|--token)
                GITHUB_TOKEN="$2"
                shift 2
                ;;
            -e|--environment)
                ENVIRONMENT="$2"
                shift 2
                ;;
            -f|--file)
                CONFIG_FILE="$2"
                shift 2
                ;;
            -v|--verbose)
                VERBOSE=true
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

    # Check if gh CLI is installed
    if ! command -v gh &> /dev/null; then
        log_error "GitHub CLI (gh) is not installed. Please install it first:"
        echo "  brew install gh"
        echo "  # or"
        echo "  curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg"
        exit 1
    fi

    # Check if jq is installed
    if ! command -v jq &> /dev/null; then
        log_error "jq is not installed. Please install it first:"
        echo "  brew install jq"
        exit 1
    fi

    # Check GitHub authentication
    if [[ -n "$GITHUB_TOKEN" ]]; then
        export GH_TOKEN="$GITHUB_TOKEN"
    fi

    if ! gh auth status &> /dev/null; then
        log_error "GitHub CLI not authenticated. Please run:"
        echo "  gh auth login"
        echo "  # or set GITHUB_TOKEN environment variable"
        exit 1
    fi

    log_success "Prerequisites check passed"
}

# Validate secrets configuration
validate_secrets() {
    log_info "Validating GitHub secrets configuration..."
    
    if [[ -z "$GITHUB_REPO" ]]; then
        log_error "GitHub repository not specified. Use -r option."
        exit 1
    fi
    
    local missing_secrets=()
    local configured_secrets=()
    
    # Get list of configured secrets
    local secrets_list
    if ! secrets_list=$(gh secret list --repo "$GITHUB_REPO" --json name --jq '.[].name' 2>/dev/null); then
        log_error "Failed to list secrets for repository: $GITHUB_REPO"
        log_error "Make sure you have admin access to the repository"
        exit 1
    fi
    
    # Check required secrets
    for secret_name in "${!REQUIRED_SECRETS[@]}"; do
        if echo "$secrets_list" | grep -q "^${secret_name}$"; then
            configured_secrets+=("$secret_name")
            if [[ "$VERBOSE" == "true" ]]; then
                log_success "✅ $secret_name: ${REQUIRED_SECRETS[$secret_name]}"
            fi
        else
            missing_secrets+=("$secret_name")
            log_error "❌ Missing: $secret_name - ${REQUIRED_SECRETS[$secret_name]}"
        fi
    done
    
    # Check optional secrets
    for secret_name in "${!OPTIONAL_SECRETS[@]}"; do
        if echo "$secrets_list" | grep -q "^${secret_name}$"; then
            configured_secrets+=("$secret_name")
            if [[ "$VERBOSE" == "true" ]]; then
                log_info "ℹ️  $secret_name: ${OPTIONAL_SECRETS[$secret_name]}"
            fi
        fi
    done
    
    echo ""
    echo "=========================================="
    echo "Secrets Validation Report"
    echo "=========================================="
    echo "Repository: $GITHUB_REPO"
    echo "Timestamp: $(date)"
    echo ""
    echo "Required secrets: ${#REQUIRED_SECRETS[@]}"
    echo "Configured: ${#configured_secrets[@]}"
    echo "Missing: ${#missing_secrets[@]}"
    echo ""
    
    if [[ ${#missing_secrets[@]} -eq 0 ]]; then
        log_success "✅ All required secrets are configured!"
        return 0
    else
        log_error "❌ Missing ${#missing_secrets[@]} required secrets"
        echo ""
        echo "Missing secrets:"
        for secret in "${missing_secrets[@]}"; do
            echo "  - $secret: ${REQUIRED_SECRETS[$secret]}"
        done
        echo ""
        echo "To add missing secrets, run:"
        echo "  $0 setup -r $GITHUB_REPO"
        return 1
    fi
}

# List all secrets
list_secrets() {
    log_info "Listing GitHub secrets..."
    
    if [[ -z "$GITHUB_REPO" ]]; then
        log_error "GitHub repository not specified. Use -r option."
        exit 1
    fi
    
    local secrets_info
    if ! secrets_info=$(gh secret list --repo "$GITHUB_REPO" --json name,updatedAt 2>/dev/null); then
        log_error "Failed to list secrets for repository: $GITHUB_REPO"
        exit 1
    fi
    
    echo ""
    echo "=========================================="
    echo "GitHub Secrets for $GITHUB_REPO"
    echo "=========================================="
    
    if [[ $(echo "$secrets_info" | jq length) -eq 0 ]]; then
        log_warning "No secrets configured"
        return 0
    fi
    
    echo "$secrets_info" | jq -r '.[] | "\(.name) (updated: \(.updatedAt))"' | while read -r line; do
        local secret_name
        secret_name=$(echo "$line" | cut -d' ' -f1)
        
        if [[ -n "${REQUIRED_SECRETS[$secret_name]:-}" ]]; then
            echo "✅ $line - ${REQUIRED_SECRETS[$secret_name]}"
        elif [[ -n "${OPTIONAL_SECRETS[$secret_name]:-}" ]]; then
            echo "ℹ️  $line - ${OPTIONAL_SECRETS[$secret_name]}"
        else
            echo "❓ $line - Unknown secret"
        fi
    done
    
    echo "=========================================="
}

# Generate secrets template
generate_template() {
    log_info "Generating secrets template..."
    
    cat << 'EOF'
# GitHub Secrets Template for Homebrew Bottles Sync
# Copy this file and fill in the values, then use the setup command

# AWS IAM Role ARNs (get these from Terraform output after deploying OIDC module)
AWS_ROLE_ARN_DEV=arn:aws:iam::ACCOUNT_ID:role/homebrew-bottles-sync-dev-github-actions-role
AWS_ROLE_ARN_STAGING=arn:aws:iam::ACCOUNT_ID:role/homebrew-bottles-sync-staging-github-actions-role
AWS_ROLE_ARN_PROD=arn:aws:iam::ACCOUNT_ID:role/homebrew-bottles-sync-prod-github-actions-role

# Notification Configuration
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK
NOTIFICATION_EMAIL=devops@yourcompany.com

# Terraform State Configuration
TERRAFORM_STATE_BUCKET=your-terraform-state-bucket
TERRAFORM_LOCK_TABLE=your-terraform-lock-table

# Optional Secrets
# DOCKER_REGISTRY_URL=your-custom-registry.com
# CUSTOM_DOMAIN=your-domain.com
# MONITORING_API_KEY=your-monitoring-api-key

# Instructions:
# 1. Fill in the values above
# 2. Run: ./scripts/manage-github-secrets.sh setup -r owner/repo -f this-file
# 3. Or set them manually in GitHub repository settings
EOF
}

# Interactive setup
interactive_setup() {
    log_info "Interactive GitHub secrets setup..."
    
    if [[ -z "$GITHUB_REPO" ]]; then
        read -p "Enter GitHub repository (owner/repo): " GITHUB_REPO
    fi
    
    if [[ -z "$GITHUB_REPO" ]]; then
        log_error "GitHub repository is required"
        exit 1
    fi
    
    log_info "Setting up secrets for repository: $GITHUB_REPO"
    echo ""
    
    # Check if we can access the repository
    if ! gh repo view "$GITHUB_REPO" &> /dev/null; then
        log_error "Cannot access repository: $GITHUB_REPO"
        log_error "Make sure the repository exists and you have access"
        exit 1
    fi
    
    # Setup required secrets
    for secret_name in "${!REQUIRED_SECRETS[@]}"; do
        echo ""
        log_info "Setting up: $secret_name"
        echo "Description: ${REQUIRED_SECRETS[$secret_name]}"
        
        # Check if secret already exists
        if gh secret list --repo "$GITHUB_REPO" --json name --jq '.[].name' | grep -q "^${secret_name}$"; then
            read -p "Secret $secret_name already exists. Update it? (y/N): " update_secret
            if [[ "$update_secret" != "y" && "$update_secret" != "Y" ]]; then
                log_info "Skipping $secret_name"
                continue
            fi
        fi
        
        # Get secret value
        read -s -p "Enter value for $secret_name: " secret_value
        echo ""
        
        if [[ -z "$secret_value" ]]; then
            log_warning "Empty value provided, skipping $secret_name"
            continue
        fi
        
        # Set the secret
        if echo "$secret_value" | gh secret set "$secret_name" --repo "$GITHUB_REPO"; then
            log_success "✅ Set $secret_name"
        else
            log_error "❌ Failed to set $secret_name"
        fi
    done
    
    # Ask about optional secrets
    echo ""
    read -p "Do you want to configure optional secrets? (y/N): " setup_optional
    if [[ "$setup_optional" == "y" || "$setup_optional" == "Y" ]]; then
        for secret_name in "${!OPTIONAL_SECRETS[@]}"; do
            echo ""
            log_info "Optional: $secret_name"
            echo "Description: ${OPTIONAL_SECRETS[$secret_name]}"
            
            read -p "Configure $secret_name? (y/N): " configure_secret
            if [[ "$configure_secret" != "y" && "$configure_secret" != "Y" ]]; then
                continue
            fi
            
            read -s -p "Enter value for $secret_name: " secret_value
            echo ""
            
            if [[ -n "$secret_value" ]]; then
                if echo "$secret_value" | gh secret set "$secret_name" --repo "$GITHUB_REPO"; then
                    log_success "✅ Set $secret_name"
                else
                    log_error "❌ Failed to set $secret_name"
                fi
            fi
        done
    fi
    
    echo ""
    log_success "Secrets setup completed!"
    log_info "Run validation to verify: $0 validate -r $GITHUB_REPO"
}

# Setup from file
setup_from_file() {
    log_info "Setting up secrets from file: $CONFIG_FILE"
    
    if [[ ! -f "$CONFIG_FILE" ]]; then
        log_error "Configuration file not found: $CONFIG_FILE"
        exit 1
    fi
    
    if [[ -z "$GITHUB_REPO" ]]; then
        log_error "GitHub repository not specified. Use -r option."
        exit 1
    fi
    
    # Source the configuration file
    set -a  # automatically export all variables
    source "$CONFIG_FILE"
    set +a
    
    # Set required secrets
    for secret_name in "${!REQUIRED_SECRETS[@]}"; do
        local secret_value="${!secret_name:-}"
        
        if [[ -n "$secret_value" ]]; then
            log_info "Setting $secret_name..."
            if echo "$secret_value" | gh secret set "$secret_name" --repo "$GITHUB_REPO"; then
                log_success "✅ Set $secret_name"
            else
                log_error "❌ Failed to set $secret_name"
            fi
        else
            log_warning "⚠️  $secret_name not found in configuration file"
        fi
    done
    
    # Set optional secrets
    for secret_name in "${!OPTIONAL_SECRETS[@]}"; do
        local secret_value="${!secret_name:-}"
        
        if [[ -n "$secret_value" ]]; then
            log_info "Setting optional $secret_name..."
            if echo "$secret_value" | gh secret set "$secret_name" --repo "$GITHUB_REPO"; then
                log_success "✅ Set $secret_name"
            else
                log_error "❌ Failed to set $secret_name"
            fi
        fi
    done
    
    log_success "Secrets setup from file completed!"
}

# Secrets rotation helper
rotation_helper() {
    log_info "Secrets rotation helper..."
    
    cat << 'EOF'
========================================
Secrets Rotation Guide
========================================

Regular rotation of secrets is important for security. Here's how to rotate each type:

1. AWS IAM Role ARNs:
   - These don't need regular rotation as they use OIDC
   - Only update if you recreate the IAM roles
   - Get new ARNs from Terraform output

2. Slack Webhook URL:
   - Generate new webhook in Slack app settings
   - Update the secret immediately
   - Test with a deployment notification

3. Notification Email:
   - Update to new email address
   - Verify the new email can receive alerts

4. Terraform State Configuration:
   - Only change if you migrate state storage
   - Ensure new bucket/table exists before updating

Rotation Commands:
  # Update a specific secret
  gh secret set SECRET_NAME --repo OWNER/REPO

  # Validate after rotation
  ./scripts/manage-github-secrets.sh validate -r OWNER/REPO

  # Test the updated configuration
  # Trigger a deployment to verify secrets work

Rotation Schedule Recommendations:
  - AWS Role ARNs: Only when recreated
  - Slack Webhook: Every 6 months
  - Email: As needed
  - Terraform Config: Only when migrating

EOF

    if [[ -n "$ENVIRONMENT" ]]; then
        echo ""
        log_info "Environment-specific rotation for: $ENVIRONMENT"
        
        case "$ENVIRONMENT" in
            "dev")
                echo "Development environment secrets can be rotated more frequently for testing"
                ;;
            "staging")
                echo "Staging environment should match production rotation schedule"
                ;;
            "prod")
                echo "Production secrets require careful coordination and testing"
                echo "Always test rotation in staging first"
                ;;
        esac
    fi
}

# Main execution function
main() {
    case "$COMMAND" in
        "validate")
            check_prerequisites
            validate_secrets
            ;;
        "list")
            check_prerequisites
            list_secrets
            ;;
        "template")
            generate_template
            ;;
        "setup")
            check_prerequisites
            if [[ -n "$CONFIG_FILE" ]]; then
                setup_from_file
            else
                interactive_setup
            fi
            ;;
        "rotate")
            rotation_helper
            ;;
        *)
            log_error "Unknown command: $COMMAND"
            usage
            exit 1
            ;;
    esac
}

# Parse arguments and run main function
parse_args "$@"
main