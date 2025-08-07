#!/bin/bash
# Rollback deployment script
# Handles rollback to previous successful deployment

set -euo pipefail

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Default values
ENVIRONMENT=""
TARGET_COMMIT=""
AUTO_APPROVE=false
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

Rollback deployment to a previous successful version

REQUIRED:
    -e, --environment ENVIRONMENT    Target environment (dev, staging, prod)

OPTIONS:
    -c, --commit COMMIT             Target commit SHA to rollback to
    -y, --auto-approve             Auto-approve rollback
    -d, --dry-run                  Show what would be rolled back
    -l, --list-candidates          List available rollback candidates
    -h, --help                     Show this help message

EXAMPLES:
    $0 -e dev -l                   List rollback candidates for dev
    $0 -e staging -c abc123        Rollback staging to commit abc123
    $0 -e prod -c def456 -y        Rollback prod with auto-approve

EOF
}

# Parse command line arguments
parse_args() {
    local list_candidates=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            -e|--environment)
                ENVIRONMENT="$2"
                shift 2
                ;;
            -c|--commit)
                TARGET_COMMIT="$2"
                shift 2
                ;;
            -y|--auto-approve)
                AUTO_APPROVE=true
                shift
                ;;
            -d|--dry-run)
                DRY_RUN=true
                shift
                ;;
            -l|--list-candidates)
                list_candidates=true
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

    # Handle list candidates
    if [[ "$list_candidates" == "true" ]]; then
        list_rollback_candidates
        exit 0
    fi

    # Validate target commit if not listing candidates
    if [[ -z "$TARGET_COMMIT" ]]; then
        log_error "Target commit is required for rollback"
        log_info "Use -l to list available rollback candidates"
        exit 1
    fi
}

# List rollback candidates
list_rollback_candidates() {
    log_info "Available rollback candidates for $ENVIRONMENT:"
    
    python3 "${SCRIPT_DIR}/deployment_tracker.py" rollback-candidates --environment "$ENVIRONMENT" | \
    jq -r '.[] | "\(.timestamp) | \(.commit_sha[0:8]) | \(.user) | \(.terraform_version)"' | \
    while IFS='|' read -r timestamp commit user tf_version; do
        echo "  $(echo $timestamp | cut -d'T' -f1) $(echo $timestamp | cut -d'T' -f2 | cut -d'.' -f1) | $commit | $user | TF $tf_version"
    done
}

# Validate rollback target
validate_rollback_target() {
    log_info "Validating rollback target..."

    # Check if target commit exists in git history
    if ! git rev-parse --verify "$TARGET_COMMIT" >/dev/null 2>&1; then
        log_error "Target commit $TARGET_COMMIT does not exist in git history"
        exit 1
    fi

    # Check if target commit is a valid rollback candidate
    local candidates=$(python3 "${SCRIPT_DIR}/deployment_tracker.py" rollback-candidates --environment "$ENVIRONMENT")
    if ! echo "$candidates" | jq -e ".[] | select(.commit_sha == \"$TARGET_COMMIT\")" >/dev/null; then
        log_error "Target commit $TARGET_COMMIT is not a valid rollback candidate"
        log_info "Use -l to list available rollback candidates"
        exit 1
    fi

    log_success "Rollback target validated"
}# Perf
orm rollback
perform_rollback() {
    log_info "Starting rollback to commit $TARGET_COMMIT..."

    # Get current commit for potential rollback
    local current_commit=$(git rev-parse HEAD)
    log_info "Current commit: $current_commit"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "DRY RUN: Would rollback from $current_commit to $TARGET_COMMIT"
        log_info "DRY RUN: Would checkout commit $TARGET_COMMIT"
        log_info "DRY RUN: Would run deployment for $ENVIRONMENT"
        return 0
    fi

    # Confirm rollback for production
    if [[ "$ENVIRONMENT" == "prod" && "$AUTO_APPROVE" != "true" ]]; then
        log_warning "You are about to rollback the PRODUCTION environment"
        log_warning "Current commit: $current_commit"
        log_warning "Target commit: $TARGET_COMMIT"
        read -p "Are you sure you want to proceed? (type 'yes' to confirm): " confirm
        if [[ "$confirm" != "yes" ]]; then
            log_info "Rollback cancelled"
            exit 0
        fi
    fi

    # Create rollback record
    python3 "${SCRIPT_DIR}/deployment_tracker.py" create \
        --environment "$ENVIRONMENT" \
        --action "rollback" \
        --status "started" \
        --rollback-version "$TARGET_COMMIT"

    # Stash any local changes
    if ! git diff --quiet; then
        log_info "Stashing local changes..."
        git stash push -m "Pre-rollback stash $(date)"
    fi

    # Checkout target commit
    log_info "Checking out target commit: $TARGET_COMMIT"
    if ! git checkout "$TARGET_COMMIT"; then
        log_error "Failed to checkout target commit"
        python3 "${SCRIPT_DIR}/deployment_tracker.py" create \
            --environment "$ENVIRONMENT" \
            --action "rollback" \
            --status "failed" \
            --error "Failed to checkout target commit"
        exit 1
    fi

    # Run deployment
    log_info "Running deployment for rollback..."
    local deploy_args="-e $ENVIRONMENT -a deploy"
    if [[ "$AUTO_APPROVE" == "true" ]]; then
        deploy_args="$deploy_args -y"
    fi

    if "${SCRIPT_DIR}/deploy-environment.sh" $deploy_args; then
        log_success "Rollback completed successfully"
        python3 "${SCRIPT_DIR}/deployment_tracker.py" create \
            --environment "$ENVIRONMENT" \
            --action "rollback" \
            --status "success" \
            --rollback-version "$TARGET_COMMIT"
        
        # Send notification
        if [[ -f "${SCRIPT_DIR}/notify_deployment.py" ]]; then
            python3 "${SCRIPT_DIR}/notify_deployment.py" \
                --environment "$ENVIRONMENT" \
                --action "rollback" \
                --status "success" \
                --message "Successfully rolled back to commit $TARGET_COMMIT" \
                --commit "$TARGET_COMMIT" \
                --user "$(whoami)"
        fi
    else
        log_error "Rollback deployment failed"
        python3 "${SCRIPT_DIR}/deployment_tracker.py" create \
            --environment "$ENVIRONMENT" \
            --action "rollback" \
            --status "failed" \
            --error "Deployment failed during rollback"
        
        # Attempt to return to original commit
        log_info "Attempting to return to original commit: $current_commit"
        git checkout "$current_commit" || log_warning "Failed to return to original commit"
        
        exit 1
    fi
}

# Main execution function
main() {
    log_info "Starting rollback process..."
    log_info "Environment: $ENVIRONMENT"
    log_info "Target commit: $TARGET_COMMIT"
    log_info "Auto-approve: $AUTO_APPROVE"
    log_info "Dry run: $DRY_RUN"

    # Validate rollback target
    validate_rollback_target

    # Perform rollback
    perform_rollback

    log_success "Rollback process completed"
}

# Parse arguments and run main function
parse_args "$@"
main