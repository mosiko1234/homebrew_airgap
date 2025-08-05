#!/bin/bash

# Staging environment deployment script
# This script deploys the Homebrew Bottles Sync System to the staging environment

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Deploy to staging environment
"$SCRIPT_DIR/deploy.sh" \
    --environment staging \
    --region us-east-1 \
    "$@"