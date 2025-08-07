#!/usr/bin/env python3
"""
GitHub Secrets Validation Script
This script validates that all required secrets are properly configured and accessible
"""

import os
import sys
import json
import subprocess
import argparse
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

class SecretType(Enum):
    REQUIRED = "required"
    OPTIONAL = "optional"
    ENVIRONMENT_SPECIFIC = "environment_specific"

@dataclass
class SecretDefinition:
    name: str
    description: str
    secret_type: SecretType
    validation_pattern: Optional[str] = None
    environment: Optional[str] = None

class SecretsValidator:
    """Validates GitHub repository secrets configuration"""
    
    def __init__(self, repository: str, verbose: bool = False):
        self.repository = repository
        self.verbose = verbose
        self.secrets_definitions = self._define_secrets()
        
    def _define_secrets(self) -> List[SecretDefinition]:
        """Define all required and optional secrets"""
        return [
            # AWS IAM Role ARNs
            SecretDefinition(
                name="AWS_ROLE_ARN_DEV",
                description="IAM role ARN for development environment",
                secret_type=SecretType.REQUIRED,
                validation_pattern=r"^arn:aws:iam::\d{12}:role/.+",
                environment="dev"
            ),
            SecretDefinition(
                name="AWS_ROLE_ARN_STAGING",
                description="IAM role ARN for staging environment",
                secret_type=SecretType.REQUIRED,
                validation_pattern=r"^arn:aws:iam::\d{12}:role/.+",
                environment="staging"
            ),
            SecretDefinition(
                name="AWS_ROLE_ARN_PROD",
                description="IAM role ARN for production environment",
                secret_type=SecretType.REQUIRED,
                validation_pattern=r"^arn:aws:iam::\d{12}:role/.+",
                environment="prod"
            ),
            
            # Notification Configuration
            SecretDefinition(
                name="SLACK_WEBHOOK_URL",
                description="Slack webhook URL for notifications",
                secret_type=SecretType.REQUIRED,
                validation_pattern=r"^https://hooks\.slack\.com/services/.+"
            ),
            SecretDefinition(
                name="NOTIFICATION_EMAIL",
                description="Email address for critical alerts",
                secret_type=SecretType.REQUIRED,
                validation_pattern=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
            ),
            
            # Terraform State Configuration
            SecretDefinition(
                name="TERRAFORM_STATE_BUCKET",
                description="S3 bucket for Terraform state",
                secret_type=SecretType.REQUIRED,
                validation_pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$"
            ),
            SecretDefinition(
                name="TERRAFORM_LOCK_TABLE",
                description="DynamoDB table for Terraform state locking",
                secret_type=SecretType.REQUIRED,
                validation_pattern=r"^[a-zA-Z0-9_.-]+$"
            ),
            
            # Optional Secrets
            SecretDefinition(
                name="DOCKER_REGISTRY_URL",
                description="Custom Docker registry URL",
                secret_type=SecretType.OPTIONAL,
                validation_pattern=r"^https?://.+"
            ),
            SecretDefinition(
                name="CUSTOM_DOMAIN",
                description="Custom domain for the application",
                secret_type=SecretType.OPTIONAL,
                validation_pattern=r"^[a-zA-Z0-9][a-zA-Z0-9-]*[a-zA-Z0-9]*\..*$"
            ),
            SecretDefinition(
                name="MONITORING_API_KEY",
                description="API key for external monitoring service",
                secret_type=SecretType.OPTIONAL
            ),
        ]
    
    def _run_command(self, command: List[str]) -> Tuple[bool, str, str]:
        """Run a shell command and return success status, stdout, stderr"""
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.returncode == 0, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return False, "", "Command timed out"
        except Exception as e:
            return False, "", str(e)
    
    def _check_gh_cli(self) -> bool:
        """Check if GitHub CLI is installed and authenticated"""
        success, _, _ = self._run_command(["gh", "--version"])
        if not success:
            print("❌ GitHub CLI (gh) is not installed")
            return False
            
        success, _, _ = self._run_command(["gh", "auth", "status"])
        if not success:
            print("❌ GitHub CLI is not authenticated")
            return False
            
        return True
    
    def _get_repository_secrets(self) -> Optional[List[str]]:
        """Get list of configured secrets from GitHub repository"""
        success, stdout, stderr = self._run_command([
            "gh", "secret", "list", "--repo", self.repository, "--json", "name", "--jq", ".[].name"
        ])
        
        if not success:
            print(f"❌ Failed to list secrets: {stderr}")
            return None
            
        return [line.strip() for line in stdout.strip().split('\n') if line.strip()]
    
    def _validate_secret_format(self, secret_name: str, secret_definition: SecretDefinition) -> bool:
        """Validate secret format (this is a placeholder since we can't read secret values)"""
        # In a real implementation, you might validate the format during secret setting
        # For now, we just check if the secret exists
        return True
    
    def validate_secrets(self, environment: Optional[str] = None) -> Tuple[bool, Dict]:
        """Validate all secrets configuration"""
        if not self._check_gh_cli():
            return False, {"error": "GitHub CLI not available"}
        
        configured_secrets = self._get_repository_secrets()
        if configured_secrets is None:
            return False, {"error": "Failed to retrieve secrets list"}
        
        results = {
            "repository": self.repository,
            "total_secrets": len(configured_secrets),
            "required_secrets": [],
            "optional_secrets": [],
            "missing_secrets": [],
            "unknown_secrets": [],
            "validation_errors": []
        }
        
        # Track all defined secret names
        defined_secret_names = {secret.name for secret in self.secrets_definitions}
        
        # Check each defined secret
        for secret_def in self.secrets_definitions:
            # Skip environment-specific secrets if filtering
            if environment and secret_def.environment and secret_def.environment != environment:
                continue
                
            is_configured = secret_def.name in configured_secrets
            
            secret_info = {
                "name": secret_def.name,
                "description": secret_def.description,
                "configured": is_configured,
                "environment": secret_def.environment,
                "valid_format": True  # Placeholder
            }
            
            if secret_def.secret_type == SecretType.REQUIRED:
                results["required_secrets"].append(secret_info)
                if not is_configured:
                    results["missing_secrets"].append(secret_def.name)
            else:
                results["optional_secrets"].append(secret_info)
            
            # Validate format if configured
            if is_configured and secret_def.validation_pattern:
                # Note: We can't actually validate the secret value since it's encrypted
                # This would need to be done during secret setting or in the workflow
                pass
        
        # Check for unknown secrets
        for secret_name in configured_secrets:
            if secret_name not in defined_secret_names:
                results["unknown_secrets"].append(secret_name)
        
        # Determine overall success
        success = len(results["missing_secrets"]) == 0
        
        return success, results
    
    def print_validation_report(self, results: Dict) -> None:
        """Print a formatted validation report"""
        print("\n" + "="*50)
        print("GitHub Secrets Validation Report")
        print("="*50)
        print(f"Repository: {results['repository']}")
        print(f"Total configured secrets: {results['total_secrets']}")
        print(f"Missing required secrets: {len(results['missing_secrets'])}")
        print(f"Unknown secrets: {len(results['unknown_secrets'])}")
        print()
        
        # Required secrets
        print("Required Secrets:")
        for secret in results["required_secrets"]:
            status = "✅" if secret["configured"] else "❌"
            env_info = f" ({secret['environment']})" if secret["environment"] else ""
            print(f"  {status} {secret['name']}{env_info}")
            if self.verbose:
                print(f"      {secret['description']}")
        
        # Optional secrets
        if results["optional_secrets"]:
            print("\nOptional Secrets:")
            for secret in results["optional_secrets"]:
                status = "✅" if secret["configured"] else "⚪"
                env_info = f" ({secret['environment']})" if secret["environment"] else ""
                print(f"  {status} {secret['name']}{env_info}")
                if self.verbose:
                    print(f"      {secret['description']}")
        
        # Missing secrets
        if results["missing_secrets"]:
            print(f"\n❌ Missing Required Secrets ({len(results['missing_secrets'])}):")
            for secret_name in results["missing_secrets"]:
                secret_def = next((s for s in self.secrets_definitions if s.name == secret_name), None)
                if secret_def:
                    print(f"  - {secret_name}: {secret_def.description}")
        
        # Unknown secrets
        if results["unknown_secrets"]:
            print(f"\n❓ Unknown Secrets ({len(results['unknown_secrets'])}):")
            for secret_name in results["unknown_secrets"]:
                print(f"  - {secret_name}")
            print("  Consider removing unused secrets or updating the validation script")
        
        # Validation errors
        if results["validation_errors"]:
            print(f"\n⚠️  Validation Errors ({len(results['validation_errors'])}):")
            for error in results["validation_errors"]:
                print(f"  - {error}")
        
        print("\n" + "="*50)
        
        if results["missing_secrets"]:
            print("❌ Validation FAILED - Missing required secrets")
            print("\nTo fix missing secrets:")
            print(f"  ./scripts/manage-github-secrets.sh setup -r {results['repository']}")
        else:
            print("✅ Validation PASSED - All required secrets configured")
    
    def generate_secrets_template(self) -> str:
        """Generate a template file for secrets configuration"""
        template = "# GitHub Secrets Configuration Template\n"
        template += "# Fill in the values and use with: ./scripts/manage-github-secrets.sh setup -f this-file\n\n"
        
        # Group by type
        required_secrets = [s for s in self.secrets_definitions if s.secret_type == SecretType.REQUIRED]
        optional_secrets = [s for s in self.secrets_definitions if s.secret_type == SecretType.OPTIONAL]
        
        template += "# Required Secrets\n"
        for secret in required_secrets:
            template += f"# {secret.description}\n"
            if secret.environment:
                template += f"{secret.name}=arn:aws:iam::ACCOUNT_ID:role/homebrew-bottles-sync-{secret.environment}-github-actions-role\n"
            elif "SLACK" in secret.name:
                template += f"{secret.name}=https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK\n"
            elif "EMAIL" in secret.name:
                template += f"{secret.name}=devops@yourcompany.com\n"
            elif "BUCKET" in secret.name:
                template += f"{secret.name}=your-terraform-state-bucket\n"
            elif "TABLE" in secret.name:
                template += f"{secret.name}=your-terraform-lock-table\n"
            else:
                template += f"{secret.name}=YOUR_VALUE_HERE\n"
            template += "\n"
        
        template += "# Optional Secrets (uncomment and fill if needed)\n"
        for secret in optional_secrets:
            template += f"# {secret.description}\n"
            template += f"# {secret.name}=YOUR_VALUE_HERE\n\n"
        
        return template

def main():
    parser = argparse.ArgumentParser(description="Validate GitHub repository secrets")
    parser.add_argument("-r", "--repository", required=True, help="GitHub repository (owner/repo)")
    parser.add_argument("-e", "--environment", choices=["dev", "staging", "prod"], help="Validate specific environment")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--template", action="store_true", help="Generate secrets template")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    
    args = parser.parse_args()
    
    validator = SecretsValidator(args.repository, args.verbose)
    
    if args.template:
        print(validator.generate_secrets_template())
        return 0
    
    success, results = validator.validate_secrets(args.environment)
    
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        validator.print_validation_report(results)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())