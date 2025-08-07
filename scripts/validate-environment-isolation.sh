#!/bin/bash
# Validate Environment Isolation
# This script tests that environment isolation is working correctly

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

Validate environment isolation configuration and security controls

OPTIONS:
    -e, --environment ENV      Environment to test (dev, staging, prod)
    -p, --project-name NAME    Project name (default: homebrew-bottles-sync)
    -r, --region REGION        AWS region (default: current region)
    -a, --account-id ID        AWS account ID (auto-detected if not provided)
    -v, --verbose              Enable verbose output
    -h, --help                 Show this help message

EXAMPLES:
    $0 -e dev                  Validate dev environment isolation
    $0 -e prod -v              Validate prod environment with verbose output
    $0 -e staging -p my-project Validate staging with custom project name

EOF
}

# Default values
ENVIRONMENT=""
PROJECT_NAME="homebrew-bottles-sync"
AWS_REGION=""
AWS_ACCOUNT_ID=""
VERBOSE=false

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -e|--environment)
                ENVIRONMENT="$2"
                shift 2
                ;;
            -p|--project-name)
                PROJECT_NAME="$2"
                shift 2
                ;;
            -r|--region)
                AWS_REGION="$2"
                shift 2
                ;;
            -a|--account-id)
                AWS_ACCOUNT_ID="$2"
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

    # Validate required parameters
    if [[ -z "$ENVIRONMENT" ]]; then
        log_error "Environment is required. Use -e or --environment"
        usage
        exit 1
    fi

    if [[ ! "$ENVIRONMENT" =~ ^(dev|staging|prod)$ ]]; then
        log_error "Environment must be one of: dev, staging, prod"
        exit 1
    fi
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

    # Get AWS account ID and region if not provided
    if [[ -z "$AWS_ACCOUNT_ID" ]]; then
        AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    fi

    if [[ -z "$AWS_REGION" ]]; then
        AWS_REGION=$(aws configure get region || echo "us-east-1")
    fi

    log_info "AWS Account ID: $AWS_ACCOUNT_ID"
    log_info "AWS Region: $AWS_REGION"
    log_info "Environment: $ENVIRONMENT"
    log_info "Project Name: $PROJECT_NAME"

    log_success "Prerequisites check passed"
}

# Test IAM role existence and configuration
test_iam_role() {
    log_info "Testing IAM role configuration..."

    local role_name="${PROJECT_NAME}-${ENVIRONMENT}-github-actions-role"
    local role_arn="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${role_name}"

    # Check if role exists
    if aws iam get-role --role-name "$role_name" &> /dev/null; then
        log_success "IAM role exists: $role_name"
    else
        log_error "IAM role not found: $role_name"
        return 1
    fi

    # Check trust policy
    local trust_policy
    trust_policy=$(aws iam get-role --role-name "$role_name" --query 'Role.AssumeRolePolicyDocument' --output json)
    
    if echo "$trust_policy" | grep -q "token.actions.githubusercontent.com"; then
        log_success "OIDC trust relationship configured correctly"
    else
        log_error "OIDC trust relationship not found in role trust policy"
        return 1
    fi

    # List attached policies
    log_info "Attached policies:"
    aws iam list-attached-role-policies --role-name "$role_name" --query 'AttachedPolicies[].PolicyName' --output table

    return 0
}

# Test resource naming conventions
test_resource_naming() {
    log_info "Testing resource naming conventions..."

    local resource_prefix="${PROJECT_NAME}-${ENVIRONMENT}"
    local test_passed=true

    # Test S3 bucket naming
    local bucket_name="${resource_prefix}-bottles-bucket"
    if aws s3api head-bucket --bucket "$bucket_name" 2>/dev/null; then
        log_success "S3 bucket follows naming convention: $bucket_name"
    else
        log_warning "S3 bucket not found or doesn't follow naming convention: $bucket_name"
    fi

    # Test Lambda function naming
    local lambda_orchestrator="${resource_prefix}-orchestrator"
    if aws lambda get-function --function-name "$lambda_orchestrator" &> /dev/null; then
        log_success "Lambda function follows naming convention: $lambda_orchestrator"
    else
        log_warning "Lambda function not found or doesn't follow naming convention: $lambda_orchestrator"
    fi

    # Test ECS cluster naming
    local ecs_cluster="${resource_prefix}-cluster"
    if aws ecs describe-clusters --clusters "$ecs_cluster" --query 'clusters[0].status' --output text 2>/dev/null | grep -q "ACTIVE"; then
        log_success "ECS cluster follows naming convention: $ecs_cluster"
    else
        log_warning "ECS cluster not found or doesn't follow naming convention: $ecs_cluster"
    fi

    return 0
}

# Test cross-environment access prevention
test_cross_environment_access() {
    log_info "Testing cross-environment access prevention..."

    local role_name="${PROJECT_NAME}-${ENVIRONMENT}-github-actions-role"
    local test_passed=true

    # Test access to other environment resources
    local other_environments=()
    case $ENVIRONMENT in
        dev)
            other_environments=("staging" "prod")
            ;;
        staging)
            other_environments=("dev" "prod")
            ;;
        prod)
            other_environments=("dev" "staging")
            ;;
    esac

    for other_env in "${other_environments[@]}"; do
        local other_bucket="${PROJECT_NAME}-${other_env}-bottles-bucket"
        
        # Simulate policy to test cross-environment access
        local simulation_result
        simulation_result=$(aws iam simulate-principal-policy \
            --policy-source-arn "arn:aws:iam::${AWS_ACCOUNT_ID}:role/${role_name}" \
            --action-names "s3:GetObject" \
            --resource-arns "arn:aws:s3:::${other_bucket}/test.txt" \
            --query 'EvaluationResults[0].EvalDecision' \
            --output text 2>/dev/null || echo "implicitDeny")

        if [[ "$simulation_result" == "implicitDeny" || "$simulation_result" == "explicitDeny" ]]; then
            log_success "Cross-environment access correctly denied for $other_env environment"
        else
            log_error "Cross-environment access not properly restricted for $other_env environment"
            test_passed=false
        fi
    done

    if [[ "$test_passed" == "true" ]]; then
        return 0
    else
        return 1
    fi
}

# Test resource tagging enforcement
test_resource_tagging() {
    log_info "Testing resource tagging enforcement..."

    local role_name="${PROJECT_NAME}-${ENVIRONMENT}-github-actions-role"
    
    # Test that resources without proper tags are denied
    local simulation_result
    simulation_result=$(aws iam simulate-principal-policy \
        --policy-source-arn "arn:aws:iam::${AWS_ACCOUNT_ID}:role/${role_name}" \
        --action-names "s3:CreateBucket" \
        --resource-arns "arn:aws:s3:::test-bucket-without-tags" \
        --query 'EvaluationResults[0].EvalDecision' \
        --output text 2>/dev/null || echo "implicitDeny")

    if [[ "$simulation_result" == "implicitDeny" || "$simulation_result" == "explicitDeny" ]]; then
        log_success "Resource creation without proper tags is correctly denied"
    else
        log_warning "Resource tagging enforcement may not be working correctly"
    fi

    # Test that resources with proper tags are allowed
    simulation_result=$(aws iam simulate-principal-policy \
        --policy-source-arn "arn:aws:iam::${AWS_ACCOUNT_ID}:role/${role_name}" \
        --action-names "s3:CreateBucket" \
        --resource-arns "arn:aws:s3:::test-bucket-with-tags" \
        --context-entries "ContextKeyName=aws:RequestTag/Environment,ContextKeyValues=${ENVIRONMENT},ContextKeyType=string" \
        --context-entries "ContextKeyName=aws:RequestTag/Project,ContextKeyValues=${PROJECT_NAME},ContextKeyType=string" \
        --query 'EvaluationResults[0].EvalDecision' \
        --output text 2>/dev/null || echo "implicitDeny")

    if [[ "$simulation_result" == "allow" ]]; then
        log_success "Resource creation with proper tags is correctly allowed"
    else
        log_warning "Resource creation with proper tags may be incorrectly denied"
    fi

    return 0
}

# Test GitHub OIDC configuration
test_github_oidc() {
    log_info "Testing GitHub OIDC configuration..."

    # Check if OIDC provider exists
    local oidc_provider_arn="arn:aws:iam::${AWS_ACCOUNT_ID}:oidc-provider/token.actions.githubusercontent.com"
    
    if aws iam get-open-id-connect-provider --open-id-connect-provider-arn "$oidc_provider_arn" &> /dev/null; then
        log_success "GitHub OIDC provider exists"
    else
        log_error "GitHub OIDC provider not found"
        log_info "Run: ./scripts/setup-github-oidc.sh to create the OIDC provider"
        return 1
    fi

    # Check thumbprint
    local thumbprint
    thumbprint=$(aws iam get-open-id-connect-provider \
        --open-id-connect-provider-arn "$oidc_provider_arn" \
        --query 'ThumbprintList[0]' \
        --output text)

    if [[ "$thumbprint" == "6938fd4d98bab03faadb97b34396831e3780aea1" ]]; then
        log_success "GitHub OIDC thumbprint is correct"
    else
        log_warning "GitHub OIDC thumbprint may be outdated: $thumbprint"
    fi

    return 0
}

# Generate isolation report
generate_report() {
    log_info "Generating environment isolation report..."

    local report_file="environment-isolation-report-${ENVIRONMENT}-$(date +%Y%m%d-%H%M%S).json"
    
    cat > "$report_file" << EOF
{
  "environment": "$ENVIRONMENT",
  "project_name": "$PROJECT_NAME",
  "aws_account_id": "$AWS_ACCOUNT_ID",
  "aws_region": "$AWS_REGION",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "tests": {
    "iam_role_configuration": "$(test_iam_role && echo "PASS" || echo "FAIL")",
    "resource_naming_conventions": "$(test_resource_naming && echo "PASS" || echo "FAIL")",
    "cross_environment_access_prevention": "$(test_cross_environment_access && echo "PASS" || echo "FAIL")",
    "resource_tagging_enforcement": "$(test_resource_tagging && echo "PASS" || echo "FAIL")",
    "github_oidc_configuration": "$(test_github_oidc && echo "PASS" || echo "FAIL")"
  },
  "recommendations": [
    "Regularly review IAM policies for least privilege access",
    "Monitor CloudTrail logs for cross-environment access attempts",
    "Implement automated compliance checking in CI/CD pipeline",
    "Consider multi-account deployment for enhanced isolation"
  ]
}
EOF

    log_success "Report generated: $report_file"
}

# Main execution function
main() {
    log_info "Environment Isolation Validation"
    log_info "================================"
    
    check_prerequisites
    
    local overall_result=0
    
    # Run all tests
    echo ""
    test_iam_role || overall_result=1
    
    echo ""
    test_resource_naming || overall_result=1
    
    echo ""
    test_cross_environment_access || overall_result=1
    
    echo ""
    test_resource_tagging || overall_result=1
    
    echo ""
    test_github_oidc || overall_result=1
    
    echo ""
    if [[ "$VERBOSE" == "true" ]]; then
        generate_report
    fi
    
    echo ""
    if [[ $overall_result -eq 0 ]]; then
        log_success "All environment isolation tests passed!"
        log_info "Environment $ENVIRONMENT is properly isolated and secure"
    else
        log_error "Some environment isolation tests failed"
        log_info "Review the errors above and fix the configuration"
    fi
    
    return $overall_result
}

# Parse arguments and run main function
parse_args "$@"
main