#!/bin/bash
# Main deployment wrapper script
# Provides a unified interface for all deployment operations

set -euo pipefail

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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
Usage: $0 COMMAND [OPTIONS]

Unified deployment interface for Homebrew Bottles Sync System

COMMANDS:
    deploy      Deploy to environment
    destroy     Destroy environment
    plan        Plan deployment
    rollback    Rollback deployment
    status      Show deployment status
    history     Show deployment history

EXAMPLES:
    $0 deploy -e dev                    Deploy to development
    $0 plan -e staging                  Plan staging deployment
    $0 rollback -e prod -c abc123       Rollback production to commit abc123
    $0 status                           Show all environment status
    $0 status -e dev                    Show development status only
    $0 history -e staging               Show staging deployment history

For detailed help on each command, use:
    $0 COMMAND --help

EOF
}

# Main function
main() {
    if [[ $# -eq 0 ]]; then
        usage
        exit 1
    fi

    local command="$1"
    shift

    case "$command" in
        deploy|destroy|plan)
            exec "${SCRIPT_DIR}/deploy-environment.sh" -a "$command" "$@"
            ;;
        rollback)
            exec "${SCRIPT_DIR}/rollback-deployment.sh" "$@"
            ;;
        status)
            exec "${SCRIPT_DIR}/deployment-status.sh" "$@"
            ;;
        history)
            exec "${SCRIPT_DIR}/deployment-status.sh" --history "$@"
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            log_error "Unknown command: $command"
            usage
            exit 1
            ;;
    esac
}

# Run main function
main "$@"