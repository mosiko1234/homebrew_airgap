#!/bin/bash

# Development environment deployment script
# This script deploys the Homebrew Bottles Sync System to the development environment

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Deploy to development environment with development-specific settings
"$SCRIPT_DIR/deploy.sh" \
    --environment dev \
    --region us-west-2 \
    "$@"