#!/bin/bash
# Setup script for Homebrew Bottles Sync System configuration

set -e

echo "🚀 Setting up Homebrew Bottles Sync System configuration..."

# Check if config.yaml exists
if [ ! -f "config.yaml" ]; then
    echo "❌ config.yaml not found. Please create it first."
    echo "   You can copy and modify the example configuration."
    exit 1
fi

echo "✅ Found config.yaml"

# Validate configuration
echo "🔍 Validating configuration..."
if python3 scripts/config_processor.py --validate; then
    echo "✅ Configuration validation passed"
else
    echo "❌ Configuration validation failed"
    echo "   Please fix the errors above and run this script again."
    exit 1
fi

# Generate terraform.tfvars files
echo "📝 Generating terraform.tfvars files..."
if python3 scripts/config_processor.py --generate; then
    echo "✅ Generated terraform.tfvars files for all environments"
else
    echo "❌ Failed to generate terraform.tfvars files"
    exit 1
fi

# Create terraform directories if they don't exist
echo "📁 Setting up terraform directory structure..."
mkdir -p terraform/environments/{dev,staging,prod}

echo "🎉 Configuration setup complete!"
echo ""
echo "Next steps:"
echo "1. Review the generated terraform/*.tfvars files"
echo "2. Set up your GitHub secrets for AWS OIDC authentication"
echo "3. Run terraform init and plan to verify your infrastructure"
echo ""
echo "Generated files:"
echo "  - terraform/dev.tfvars"
echo "  - terraform/staging.tfvars" 
echo "  - terraform/prod.tfvars"