#!/bin/bash

# Build script for Lambda layer with shared dependencies
# This script creates a Lambda layer ZIP file containing boto3, requests, and shared modules

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
BUILD_DIR="$SCRIPT_DIR/build"
LAYER_DIR="$BUILD_DIR/python"
ZIP_FILE="$SCRIPT_DIR/lambda-layer.zip"

echo "Building Lambda layer..."
echo "Project root: $PROJECT_ROOT"
echo "Build directory: $BUILD_DIR"

# Clean up previous build
rm -rf "$BUILD_DIR"
rm -f "$ZIP_FILE"

# Create build directory structure
mkdir -p "$LAYER_DIR"

# Install Python dependencies
echo "Installing Python dependencies..."
pip install --target "$LAYER_DIR" \
    boto3>=1.34.0 \
    requests>=2.31.0 \
    --no-deps \
    --platform linux_x86_64 \
    --implementation cp \
    --python-version 3.11 \
    --only-binary=:all: \
    --upgrade

# Copy shared modules to the layer
echo "Copying shared modules..."
if [ -d "$PROJECT_ROOT/shared" ]; then
    cp -r "$PROJECT_ROOT/shared" "$LAYER_DIR/"
    echo "Copied shared modules from $PROJECT_ROOT/shared"
else
    echo "Warning: Shared modules directory not found at $PROJECT_ROOT/shared"
fi

# Remove unnecessary files to reduce layer size
echo "Cleaning up unnecessary files..."
find "$LAYER_DIR" -type f -name "*.pyc" -delete
find "$LAYER_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$LAYER_DIR" -type f -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true
find "$LAYER_DIR" -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true

# Create ZIP file
echo "Creating ZIP file..."
cd "$BUILD_DIR"
zip -r "../lambda-layer.zip" python/ -q

# Get file size
LAYER_SIZE=$(du -h "$ZIP_FILE" | cut -f1)
echo "Lambda layer created: $ZIP_FILE ($LAYER_SIZE)"

# Clean up build directory
rm -rf "$BUILD_DIR"

echo "Lambda layer build complete!"