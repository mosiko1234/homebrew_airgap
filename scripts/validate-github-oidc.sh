#!/bin/bash
# Validate GitHub OIDC Provider and IAM Roles Setup
# This script validates the OIDC configuration and IAM roles

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

Validate GitHub OIDC Provider and IAM Roles Setup

OPTIONS:
    -r, --region REGION        AWS region (default: us-east-1)
    -a, --account-id ID        AWS account ID (auto-detected if not provided)
    -g, --github-repo REPO     GitHub repository in format 'owner/repo'
    -e, --environment ENV      Specific environment to validate (dev, staging, prod)
    -v, --verbose              Enable verbose output
    -h, --help                 Show this help message

EXAMPLES:
    $0                                    Validate all environments
    $0 -e dev                            Validate only dev environment
    $0 -g myorg/myrepo -e staging        Validate staging for specific repo
    $0 -v                                Validate with verbose output

EOF
}

# Default values
AWS_REGION="us-east-1"
AWS_ACCOUNT_ID=""
GITHUB_REPO=""
ENVIRONMENT=""
VERBOSE=false
PROJECT_NAME="homebrew-bottles-sync"

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
            -g|--github-repo)
                GITHUB_REPO="$2"
                shift 2
                ;;
            -e|--environment)
                ENVIRONMENT="$2"
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

    # Check if AWS CLI is installed
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI is not installed or not in PATH"
        exit 1
    fi

    # Check if jq is installed
    if ! command -v jq &> /dev/null; then
        log_error "jq is not installed or not in PATH"
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

# Validate OIDC provider
validate_oidc_provider() {
    log_info "Validating GitHub OIDC provider..."

    local provider_arn="arn:aws:iam::${AWS_ACCOUNT_ID}:oidc-provider/token.actions.githubusercontent.com"
    
    if aws iam get-open-id-connect-provider --open-id-connect-provider-arn "$provider_arn" &> /dev/null; then
        log_success "GitHub OIDC provider exists: $provider_arn"
        
        # Validate thumbprints
        local thumbprints
        thumbprints=$(aws iam get-open-id-connect-provider \
            --open-id-connect-provider-arn "$provider_arn" \
            --query 'ThumbprintList' --output json)
        
        if echo "$thumbprints" | jq -e '.[] | select(. == "6938fd4d98bab03faadb97b34396831e3780aea1")' > /dev/null; then
            log_success "OIDC provider has correct thumbprint"
        else
            log_warning "OIDC provider may have outdated thumbprint"
        fi
        
        return 0
    else
        log_error "GitHub OIDC provider does not exist: $provider_arn"
        return 1
    fi
}

# Validate IAM role
validate_iam_role() {
    local env_name="$1"
    local role_name="${PROJECT_NAME}-${env_name}-github-actions-role"
    
    log_info "Validating IAM role for $env_name environment..."
    
    # Check if role exists
    if aws iam get-role --role-name "$role_name" &> /dev/null; then
        log_success "IAM role exists: $role_name"
        
        # Validate trust policy
        local trust_policy
        trust_policy=$(aws iam get-role --role-name "$role_name" --query 'Role.AssumeRolePolicyDocument' --output json)
        
        # Check if OIDC provider is in trust policy
        if echo "$trust_policy" | jq -e '.Statement[].Principal.Federated | select(contains("token.actions.githubusercontent.com"))' > /dev/null; then
            log_success "Role has correct OIDC trust policy"
        else
            log_error "Role trust policy does not include OIDC provider"
            return 1
        fi
        
        # Check GitHub repository condition if provided
        if [[ -n "$GITHUB_REPO" ]]; then
            if echo "$trust_policy" | jq -e --arg repo "$GITHUB_REPO" '.Statement[].Condition.StringLike."token.actions.githubusercontent.com:sub"[] | select(contains($repo))' > /dev/null; then
                log_success "Role trust policy includes repository: $GITHUB_REPO"
            else
                log_warning "Role trust policy may not include repository: $GITHUB_REPO"
            fi
        fi
        
        # Validate attached policies
        local attached_policies
        attached_policies=$(aws iam list-attached-role-policies --role-name "$role_name" --query 'AttachedPolicies[].PolicyName' --output json)
        
        if echo "$attached_policies" | jq -e --arg policy "${PROJECT_NAME}-${env_name}-deployment-policy" '.[] | select(. == $policy)' > /dev/null; then
            log_success "Deployment policy is attached to role"
        else
            log_warning "Deployment policy may not be attached to role"
        fi
        
        if echo "$attached_policies" | jq -e --arg policy "${PROJECT_NAME}-${env_name}-isolation-policy" '.[] | select(. == $policy)' > /dev/null; then
            log_success "Isolation policy is attached to role"
        else
            log_warning "Isolation policy may not be attached to role"
        fi
        
        # Check permission boundary
        local permission_boundary
        permission_boundary=$(aws iam get-role --role-name "$role_name" --query 'Role.PermissionsBoundary.PermissionsBoundaryArn' --output text 2>/dev/null || echo "None")
        
        if [[ "$permission_boundary" != "None" ]]; then
            log_success "Role has permission boundary: $permission_boundary"
        else
            log_warning "Role does not have permission boundary (recommended for security)"
        fi
        
        return 0
    else
        log_error "IAM role does not exist: $role_name"
        return 1
    fi
}

# Test role assumption (simulation)
test_role_assumption() {
    local env_name="$1"
    local role_arn="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${PROJECT_NAME}-${env_name}-github-actions-role"
    
    log_info "Testing role assumption for $env_name environment..."
    
    # This is a simulation - we can't actually test OIDC assumption without GitHub Actions context
    # But we can validate the role's assumable conditions
    
    local trust_policy
    trust_policy=$(aws iam get-role --role-name "${PROJECT_NAME}-${env_name}-github-actions-role" --query 'Role.AssumeRolePolicyDocument' --output json)
    
    # Check for required conditions
    if echo "$trust_policy" | jq -e '.Statement[].Condition.StringEquals."token.actions.githubusercontent.com:aud"' > /dev/null; then
        log_success "Role has correct audience condition"
    else
        log_error "Role missing audience condition"
        return 1
    fi
    
    if echo "$trust_policy" | jq -e '.Statement[].Condition.StringLike."token.actions.githubusercontent.com:sub"' > /dev/null; then
        log_success "Role has subject condition for repository access"
    else
        log_error "Role missing subject condition"
        return 1
    fi
    
    log_success "Role assumption configuration appears correct"
    return 0
}

# Validate environment isolation
validate_environment_isolation() {
    local env_name="$1"
    
    log_info "Validating environment isolation for $env_name..."
    
    local isolation_policy_name="${PROJECT_NAME}-${env_name}-isolation-policy"
    
    if aws iam get-policy --policy-arn "arn:aws:iam::${AWS_ACCOUNT_ID}:policy/github-actions/${isolation_policy_name}" &> /dev/null; then
        log_success "Environment isolation policy exists"
        
        # Check policy content
        local policy_version
        policy_version=$(aws iam get-policy --policy-arn "arn:aws:iam::${AWS_ACCOUNT_ID}:policy/github-actions/${isolation_policy_name}" --query 'Policy.DefaultVersionId' --output text)
        
        local policy_document
        policy_document=$(aws iam get-policy-version \
            --policy-arn "arn:aws:iam::${AWS_ACCOUNT_ID}:policy/github-actions/${isolation_policy_name}" \
            --version-id "$policy_version" \
            --query 'PolicyVersion.Document' --output json)
        
        if echo "$policy_document" | jq -e '.Statement[] | select(.Effect == "Deny")' > /dev/null; then
            log_success "Isolation policy contains deny statements"
        else
            log_warning "Isolation policy may not have proper deny statements"
        fi
        
        return 0
    else
        log_error "Environment isolation policy does not exist"
        return 1
    fi
}

# Generate validation report
generate_report() {
    local environments=("dev" "staging" "prod")
    local total_checks=0
    local passed_checks=0
    local failed_checks=0
    
    log_info "Generating validation report..."
    
    echo ""
    echo "=========================================="
    echo "GitHub OIDC Validation Report"
    echo "=========================================="
    echo "Account ID: $AWS_ACCOUNT_ID"
    echo "Region: $AWS_REGION"
    echo "Project: $PROJECT_NAME"
    if [[ -n "$GITHUB_REPO" ]]; then
        echo "GitHub Repository: $GITHUB_REPO"
    fi
    echo "Timestamp: $(date)"
    echo ""
    
    # OIDC Provider validation
    echo "OIDC Provider:"
    ((total_checks++))
    if validate_oidc_provider; then
        echo "  ✅ Provider exists and configured correctly"
        ((passed_checks++))
    else
        echo "  ❌ Provider missing or misconfigured"
        ((failed_checks++))
    fi
    echo ""
    
    # Environment-specific validations
    for env in "${environments[@]}"; do
        if [[ -n "$ENVIRONMENT" && "$env" != "$ENVIRONMENT" ]]; then
            continue
        fi
        
        echo "Environment: $env"
        
        # IAM Role validation
        ((total_checks++))
        if validate_iam_role "$env"; then
            echo "  ✅ IAM role configured correctly"
            ((passed_checks++))
        else
            echo "  ❌ IAM role missing or misconfigured"
            ((failed_checks++))
        fi
        
        # Role assumption test
        ((total_checks++))
        if test_role_assumption "$env"; then
            echo "  ✅ Role assumption configuration correct"
            ((passed_checks++))
        else
            echo "  ❌ Role assumption configuration issues"
            ((failed_checks++))
        fi
        
        # Environment isolation
        ((total_checks++))
        if validate_environment_isolation "$env"; then
            echo "  ✅ Environment isolation configured"
            ((passed_checks++))
        else
            echo "  ❌ Environment isolation missing or misconfigured"
            ((failed_checks++))
        fi
        
        echo ""
    done
    
    echo "=========================================="
    echo "Summary:"
    echo "  Total checks: $total_checks"
    echo "  Passed: $passed_checks"
    echo "  Failed: $failed_checks"
    
    if [[ $failed_checks -eq 0 ]]; then
        echo "  Status: ✅ ALL CHECKS PASSED"
        echo "=========================================="
        return 0
    else
        echo "  Status: ❌ SOME CHECKS FAILED"
        echo "=========================================="
        return 1
    fi
}

# Main execution function
main() {
    log_info "GitHub OIDC Validation"
    log_info "AWS Region: $AWS_REGION"
    
    # Set AWS region
    export AWS_DEFAULT_REGION="$AWS_REGION"
    
    # Check prerequisites
    check_prerequisites
    
    # Generate validation report
    if generate_report; then
        log_success "All validations passed!"
        return 0
    else
        log_error "Some validations failed. Please review the report above."
        return 1
    fi
}

# Parse arguments and run main function
parse_args "$@"
main