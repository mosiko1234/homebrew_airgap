#!/bin/bash
# Deployment Status Dashboard
# Provides a comprehensive view of deployment status across all environments

set -euo pipefail

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Status icons
SUCCESS_ICON="✅"
FAILED_ICON="❌"
WARNING_ICON="⚠️"
INFO_ICON="ℹ️"
ROCKET_ICON="🚀"

# Print header
print_header() {
    echo -e "${BOLD}${BLUE}"
    echo "╔══════════════════════════════════════════════════════════════════════════════╗"
    echo "║                    Homebrew Bottles Sync - Deployment Status                ║"
    echo "╚══════════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# Print environment status
print_environment_status() {
    local env="$1"
    local status_json="$2"
    
    local status=$(echo "$status_json" | jq -r '.status // "unknown"')
    local last_deployment=$(echo "$status_json" | jq -r '.last_deployment // "never"')
    local commit_sha=$(echo "$status_json" | jq -r '.commit_sha // "unknown"')
    local user=$(echo "$status_json" | jq -r '.user // "unknown"')
    local action=$(echo "$status_json" | jq -r '.action // "unknown"')
    
    # Format environment name
    local env_display
    case "$env" in
        "dev")
            env_display="${YELLOW}Development${NC}"
            ;;
        "staging")
            env_display="${BLUE}Staging${NC}"
            ;;
        "prod")
            env_display="${GREEN}Production${NC}"
            ;;
        *)
            env_display="$env"
            ;;
    esac
    
    # Format status with icon and color
    local status_display
    case "$status" in
        "success")
            status_display="${GREEN}${SUCCESS_ICON} Success${NC}"
            ;;
        "failed")
            status_display="${RED}${FAILED_ICON} Failed${NC}"
            ;;
        "started")
            status_display="${YELLOW}${ROCKET_ICON} In Progress${NC}"
            ;;
        "destroyed")
            status_display="${RED}${WARNING_ICON} Destroyed${NC}"
            ;;
        "rolled_back")
            status_display="${CYAN}${INFO_ICON} Rolled Back${NC}"
            ;;
        *)
            status_display="${YELLOW}${WARNING_ICON} Unknown${NC}"
            ;;
    esac
    
    # Format timestamp
    local time_display="never"
    if [[ "$last_deployment" != "never" ]]; then
        # Convert ISO timestamp to readable format
        if command -v date >/dev/null 2>&1; then
            time_display=$(date -d "$last_deployment" "+%Y-%m-%d %H:%M:%S UTC" 2>/dev/null || echo "$last_deployment")
        else
            time_display="$last_deployment"
        fi
    fi
    
    # Format commit SHA
    local commit_display="unknown"
    if [[ "$commit_sha" != "unknown" && ${#commit_sha} -ge 8 ]]; then
        commit_display="${commit_sha:0:8}"
    fi
    
    echo -e "${BOLD}Environment:${NC} $env_display"
    echo -e "  Status:      $status_display"
    echo -e "  Last Action: ${action}"
    echo -e "  Deployed:    ${time_display}"
    echo -e "  Commit:      ${commit_display}"
    echo -e "  User:        ${user}"
    echo ""
}

# Print deployment history
print_deployment_history() {
    local env="$1"
    local limit="${2:-5}"
    
    echo -e "${BOLD}Recent Deployments for ${env}:${NC}"
    echo "┌─────────────────────┬──────────┬─────────┬──────────┬─────────────┐"
    echo "│ Timestamp           │ Status   │ Action  │ Commit   │ User        │"
    echo "├─────────────────────┼──────────┼─────────┼──────────┼─────────────┤"
    
    python3 "${SCRIPT_DIR}/deployment_tracker.py" history --environment "$env" --limit "$limit" | \
    jq -r '.[] | "\(.timestamp) \(.status) \(.action) \(.commit_sha[0:8]) \(.user)"' | \
    while read -r timestamp status action commit user; do
        # Format timestamp
        local time_display
        if command -v date >/dev/null 2>&1; then
            time_display=$(date -d "$timestamp" "+%m-%d %H:%M" 2>/dev/null || echo "${timestamp:5:11}")
        else
            time_display="${timestamp:5:11}"
        fi
        
        # Format status with color
        local status_colored
        case "$status" in
            "success")
                status_colored="${GREEN}success${NC} "
                ;;
            "failed")
                status_colored="${RED}failed${NC}  "
                ;;
            "started")
                status_colored="${YELLOW}started${NC} "
                ;;
            *)
                status_colored="$status"
                ;;
        esac
        
        printf "│ %-19s │ %-8s │ %-7s │ %-8s │ %-11s │\n" \
               "$time_display" "$status_colored" "$action" "$commit" "$user"
    done
    
    echo "└─────────────────────┴──────────┴─────────┴──────────┴─────────────┘"
    echo ""
}

# Print summary statistics
print_summary() {
    local report="$1"
    
    echo -e "${BOLD}Summary:${NC}"
    
    local total_envs=0
    local healthy_envs=0
    local failed_envs=0
    
    for env in dev staging prod; do
        local env_status=$(echo "$report" | jq -r ".environments.${env}.status // \"unknown\"")
        total_envs=$((total_envs + 1))
        
        case "$env_status" in
            "success")
                healthy_envs=$((healthy_envs + 1))
                ;;
            "failed")
                failed_envs=$((failed_envs + 1))
                ;;
        esac
    done
    
    echo -e "  Total Environments: ${total_envs}"
    echo -e "  Healthy:           ${GREEN}${healthy_envs}${NC}"
    echo -e "  Failed:            ${RED}${failed_envs}${NC}"
    echo -e "  Other:             $((total_envs - healthy_envs - failed_envs))"
    echo ""
}

# Main function
main() {
    local show_history=false
    local environment=""
    local history_limit=5
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--history)
                show_history=true
                shift
                ;;
            -e|--environment)
                environment="$2"
                shift 2
                ;;
            -l|--limit)
                history_limit="$2"
                shift 2
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  -h, --history           Show deployment history"
                echo "  -e, --environment ENV   Show specific environment only"
                echo "  -l, --limit N          Limit history entries (default: 5)"
                echo "  --help                 Show this help message"
                exit 0
                ;;
            *)
                echo "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    # Check if deployment tracker is available
    if [[ ! -f "${SCRIPT_DIR}/deployment_tracker.py" ]]; then
        echo -e "${RED}Error: deployment_tracker.py not found${NC}"
        exit 1
    fi
    
    # Check if jq is available
    if ! command -v jq >/dev/null 2>&1; then
        echo -e "${RED}Error: jq is required but not installed${NC}"
        exit 1
    fi
    
    # Print header
    print_header
    
    # Get deployment report
    local report=$(python3 "${SCRIPT_DIR}/deployment_tracker.py" report)
    
    if [[ -n "$environment" ]]; then
        # Show specific environment
        local env_status=$(echo "$report" | jq ".environments.${environment}")
        if [[ "$env_status" == "null" ]]; then
            echo -e "${RED}Error: Environment '$environment' not found${NC}"
            exit 1
        fi
        
        print_environment_status "$environment" "$env_status"
        
        if [[ "$show_history" == "true" ]]; then
            print_deployment_history "$environment" "$history_limit"
        fi
    else
        # Show all environments
        print_summary "$report"
        
        for env in dev staging prod; do
            local env_status=$(echo "$report" | jq ".environments.${env}")
            print_environment_status "$env" "$env_status"
        done
        
        if [[ "$show_history" == "true" ]]; then
            for env in dev staging prod; do
                print_deployment_history "$env" "$history_limit"
            done
        fi
    fi
    
    echo -e "${CYAN}${INFO_ICON} Use --help for more options${NC}"
}

# Run main function
main "$@"