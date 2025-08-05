#!/bin/bash

# Production environment deployment script
# This script deploys the Homebrew Bottles Sync System to the production environment

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Deploy to production environment
"$SCRIPT_DIR/deploy.sh" \
    --environment prod \
    --region us-east-1 \
    "$@"