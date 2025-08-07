#!/bin/bash
"""
Pre-commit Setup Script

This script sets up pre-commit hooks for the project to ensure code quality
before commits are made.
"""

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo -e "${BLUE}🚀 Setting up pre-commit hooks for code quality...${NC}\n"

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to install pre-commit
install_pre_commit() {
    echo -e "${YELLOW}📦 Installing pre-commit...${NC}"
    
    if command_exists pip; then
        pip install pre-commit
    elif command_exists pip3; then
        pip3 install pre-commit
    elif command_exists brew; then
        brew install pre-commit
    else
        echo -e "${RED}❌ Could not install pre-commit. Please install it manually:${NC}"
        echo "  pip install pre-commit"
        echo "  or"
        echo "  brew install pre-commit"
        exit 1
    fi
}

# Function to install Python dependencies
install_python_deps() {
    echo -e "${YELLOW}🐍 Installing Python code quality tools...${NC}"
    
    local pip_cmd="pip"
    if command_exists pip3; then
        pip_cmd="pip3"
    fi
    
    $pip_cmd install black isort flake8 bandit pytest-cov
}

# Function to install Terraform tools
install_terraform_tools() {
    echo -e "${YELLOW}🏗️  Installing Terraform tools...${NC}"
    
    # Install terraform if not present
    if ! command_exists terraform; then
        if command_exists brew; then
            brew install terraform
        else
            echo -e "${YELLOW}⚠️  Terraform not found. Please install it manually.${NC}"
        fi
    fi
    
    # Install tflint
    if ! command_exists tflint; then
        echo "Installing TFLint..."
        curl -s https://raw.githubusercontent.com/terraform-linters/tflint/master/install_linux.sh | bash
    fi
    
    # Install tfsec
    if ! command_exists tfsec; then
        echo "Installing TFSec..."
        if [[ "$OSTYPE" == "darwin"* ]]; then
            brew install tfsec
        else
            curl -s https://raw.githubusercontent.com/aquasecurity/tfsec/master/scripts/install_linux.sh | bash
        fi
    fi
}

# Function to setup pre-commit hooks
setup_pre_commit_hooks() {
    echo -e "${YELLOW}🔗 Setting up pre-commit hooks...${NC}"
    
    cd "$PROJECT_ROOT"
    
    # Install pre-commit hooks
    pre-commit install
    
    # Install commit-msg hook for conventional commits
    pre-commit install --hook-type commit-msg
    
    # Run pre-commit on all files to ensure everything works
    echo -e "${YELLOW}🧪 Running pre-commit on all files (this may take a while)...${NC}"
    pre-commit run --all-files || {
        echo -e "${YELLOW}⚠️  Some pre-commit checks failed. This is normal for the first run.${NC}"
        echo -e "${YELLOW}   The hooks will auto-fix many issues. Run 'git add .' and commit again.${NC}"
    }
}

# Function to create secrets baseline
create_secrets_baseline() {
    echo -e "${YELLOW}🔒 Creating secrets detection baseline...${NC}"
    
    cd "$PROJECT_ROOT"
    
    if command_exists detect-secrets; then
        detect-secrets scan --baseline .secrets.baseline
        echo -e "${GREEN}✅ Secrets baseline created${NC}"
    else
        echo -e "${YELLOW}⚠️  detect-secrets not found. Installing...${NC}"
        pip install detect-secrets
        detect-secrets scan --baseline .secrets.baseline
    fi
}

# Function to create development configuration
create_dev_config() {
    echo -e "${YELLOW}⚙️  Creating development configuration files...${NC}"
    
    cd "$PROJECT_ROOT"
    
    # Create .editorconfig if it doesn't exist
    if [[ ! -f .editorconfig ]]; then
        cat > .editorconfig << 'EOF'
root = true

[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
trim_trailing_whitespace = true
indent_style = space
indent_size = 2

[*.py]
indent_size = 4
max_line_length = 88

[*.{tf,tfvars}]
indent_size = 2

[*.{yml,yaml}]
indent_size = 2

[*.sh]
indent_size = 2

[Makefile]
indent_style = tab
EOF
        echo -e "${GREEN}✅ Created .editorconfig${NC}"
    fi
    
    # Create .gitattributes if it doesn't exist
    if [[ ! -f .gitattributes ]]; then
        cat > .gitattributes << 'EOF'
# Auto detect text files and perform LF normalization
* text=auto

# Python files
*.py text diff=python

# Terraform files
*.tf text
*.tfvars text

# YAML files
*.yml text
*.yaml text

# Shell scripts
*.sh text eol=lf

# Documentation
*.md text

# Binary files
*.png binary
*.jpg binary
*.jpeg binary
*.gif binary
*.ico binary
*.zip binary
*.tar.gz binary
EOF
        echo -e "${GREEN}✅ Created .gitattributes${NC}"
    fi
}

# Function to show usage instructions
show_usage_instructions() {
    echo -e "\n${GREEN}🎉 Pre-commit setup complete!${NC}\n"
    
    echo -e "${BLUE}📋 What was set up:${NC}"
    echo "  ✅ Pre-commit hooks installed"
    echo "  ✅ Python code quality tools (black, isort, flake8, bandit)"
    echo "  ✅ Terraform tools (tflint, tfsec)"
    echo "  ✅ General file checks (YAML, JSON, trailing whitespace)"
    echo "  ✅ Security scanning (secrets detection)"
    echo ""
    
    echo -e "${BLUE}🔧 How to use:${NC}"
    echo "  • Pre-commit hooks will run automatically on every commit"
    echo "  • To run hooks manually: pre-commit run --all-files"
    echo "  • To run specific hook: pre-commit run <hook-name>"
    echo "  • To skip hooks (not recommended): git commit --no-verify"
    echo ""
    
    echo -e "${BLUE}🛠️  Manual quality checks:${NC}"
    echo "  • Run comprehensive check: python scripts/code-quality-check.py"
    echo "  • Auto-fix formatting: python scripts/code-quality-check.py --fix"
    echo "  • Generate report: python scripts/code-quality-check.py --report report.json"
    echo ""
    
    echo -e "${BLUE}📚 Available pre-commit hooks:${NC}"
    echo "  • black: Python code formatting"
    echo "  • isort: Python import sorting"
    echo "  • flake8: Python linting"
    echo "  • bandit: Python security scanning"
    echo "  • terraform_fmt: Terraform formatting"
    echo "  • terraform_validate: Terraform validation"
    echo "  • tfsec: Terraform security scanning"
    echo "  • check-yaml: YAML validation"
    echo "  • detect-secrets: Secrets detection"
    echo ""
    
    echo -e "${YELLOW}💡 Tips:${NC}"
    echo "  • Configure your IDE to use black and isort for automatic formatting"
    echo "  • Run 'pre-commit autoupdate' periodically to update hook versions"
    echo "  • Check .pre-commit-config.yaml for all available hooks and configuration"
}

# Main execution
main() {
    echo -e "${BLUE}🔍 Checking system requirements...${NC}"
    
    # Check if pre-commit is installed
    if ! command_exists pre-commit; then
        install_pre_commit
    else
        echo -e "${GREEN}✅ pre-commit is already installed${NC}"
    fi
    
    # Install Python dependencies
    install_python_deps
    
    # Install Terraform tools
    install_terraform_tools
    
    # Setup pre-commit hooks
    setup_pre_commit_hooks
    
    # Create secrets baseline
    create_secrets_baseline
    
    # Create development configuration
    create_dev_config
    
    # Show usage instructions
    show_usage_instructions
}

# Run main function
main "$@"