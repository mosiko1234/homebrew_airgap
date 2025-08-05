#!/bin/bash

# Script to package Lambda functions for deployment
# This script creates ZIP files for the orchestrator and sync worker functions

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

echo "Packaging Lambda functions..."
echo "Project root: $PROJECT_ROOT"
echo "Script directory: $SCRIPT_DIR"

# Clean up existing ZIP files
rm -f "$SCRIPT_DIR/lambda-orchestrator.zip"
rm -f "$SCRIPT_DIR/lambda-sync.zip"

# Package orchestrator function
echo "Packaging orchestrator function..."
cd "$PROJECT_ROOT/lambda/orchestrator"
zip -r "$SCRIPT_DIR/lambda-orchestrator.zip" . \
    -x "__pycache__/*" "*.pyc" "*.pyo" "*.pyd" ".DS_Store" "*.so" "*.dylib"

# Package sync worker function
echo "Packaging sync worker function..."
cd "$PROJECT_ROOT/lambda/sync"
zip -r "$SCRIPT_DIR/lambda-sync.zip" . \
    -x "__pycache__/*" "*.pyc" "*.pyo" "*.pyd" ".DS_Store" "*.so" "*.dylib"

# Get file sizes
ORCHESTRATOR_SIZE=$(du -h "$SCRIPT_DIR/lambda-orchestrator.zip" | cut -f1)
SYNC_SIZE=$(du -h "$SCRIPT_DIR/lambda-sync.zip" | cut -f1)

echo "Lambda functions packaged successfully:"
echo "  - Orchestrator: $SCRIPT_DIR/lambda-orchestrator.zip ($ORCHESTRATOR_SIZE)"
echo "  - Sync Worker: $SCRIPT_DIR/lambda-sync.zip ($SYNC_SIZE)"