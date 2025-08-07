#!/usr/bin/env python3
"""
Deployment Validation Script

This script performs comprehensive validation before deployment including:
- Configuration validation
- Infrastructure drift detection
- Resource validation
- Security compliance checks
- Cost estimation
"""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import yaml
import boto3
from botocore.exceptions import ClientError, NoCredentialsError


class DeploymentValidator:
    """Handles comprehensive deployment validation."""
    
    def __init__(self, project_root: Path, environment: str):
        self.project_root = project_root
        self.environment = environment
        self.validation_results = {
            "config_validation": {"passed": False, "errors": []},
            "terraform_validation": {"passed": False, "errors": []},
            "drift_detection": {"passed": False, "errors": [], "drift_detected": False},
            "security_validation": {"passed": False, "errors": []},
            "cost_estimation": {"passed": False, "errors": [], "estimated_cost": 0},
            "resource_validation": {"passed": False, "errors": []},
        }
        self.aws_session = None
        
    def _run_command(self, command: List[str], cwd: Path = None, capture_output: bool = True) -> Tuple[int, str, str]:
        """Run a command and return exit code, stdout, stderr."""
        try:
            result = subprocess.run(
                command,
                cwd=cwd or self.project_root,
                capture_output=capture_output,
                text=True,
                timeout=300
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return 1, "", "Command timed out after 300 seconds"
        except Exception as e:
            return 1, "", str(e)
    
    def _get_aws_session(self) -> Optional[boto3.Session]:
        """Get AWS session for the environment."""
        if self.aws_session:
            return self.aws_session
            
        try:
            # Try to create session with current credentials
            session = boto3.Session()
            # Test credentials by making a simple call
            sts = session.client('sts')
            sts.get_caller_identity()
            self.aws_session = session
            return session
        except (NoCredentialsError, ClientError) as e:
            print(f"⚠️  AWS credentials not available: {e}")
            return None
    
    def validate_configuration(self) -> bool:
        """Validate project configuration."""
        print("🔍 Validating configuration...")
        
        try:
            # Check if config.yaml exists
            config_path = self.project_root / "config.yaml"
            if not config_path.exists():
                self.validation_results["config_validation"]["errors"].append(
                    "config.yaml not found"
                )
                return False
            
            # Validate configuration using config processor
            exit_code, stdout, stderr = self._run_command([
                "python", "scripts/config_processor.py", 
                "--validate", "--environment", self.environment
            ])
            
            if exit_code != 0:
                self.validation_results["config_validation"]["errors"].append(
                    f"Configuration validation failed: {stderr}"
                )
                return False
            
            # Generate terraform vars to ensure they're valid
            exit_code, stdout, stderr = self._run_command([
                "python", "scripts/config_processor.py",
                "--environment", self.environment,
                "--output", f"terraform/{self.environment}.tfvars"
            ])
            
            if exit_code != 0:
                self.validation_results["config_validation"]["errors"].append(
                    f"Failed to generate terraform vars: {stderr}"
                )
                return False
            
            self.validation_results["config_validation"]["passed"] = True
            print("✅ Configuration validation passed")
            return True
            
        except Exception as e:
            self.validation_results["config_validation"]["errors"].append(str(e))
            print(f"❌ Configuration validation failed: {e}")
            return False
    
    def validate_terraform(self) -> bool:
        """Validate Terraform configuration."""
        print("🏗️  Validating Terraform configuration...")
        
        try:
            terraform_dir = self.project_root / "terraform"
            
            # Initialize terraform
            exit_code, stdout, stderr = self._run_command([
                "terraform", "init", "-backend=false"
            ], cwd=terraform_dir)
            
            if exit_code != 0:
                self.validation_results["terraform_validation"]["errors"].append(
                    f"Terraform init failed: {stderr}"
                )
                return False
            
            # Validate terraform
            exit_code, stdout, stderr = self._run_command([
                "terraform", "validate", "-json"
            ], cwd=terraform_dir)
            
            if exit_code != 0:
                self.validation_results["terraform_validation"]["errors"].append(
                    f"Terraform validation failed: {stderr}"
                )
                return False
            
            # Check terraform formatting
            exit_code, stdout, stderr = self._run_command([
                "terraform", "fmt", "-check", "-recursive"
            ], cwd=terraform_dir)
            
            if exit_code != 0:
                self.validation_results["terraform_validation"]["errors"].append(
                    "Terraform files are not properly formatted"
                )
                return False
            
            # Validate environment-specific configuration
            env_dir = terraform_dir / "environments" / self.environment
            if env_dir.exists():
                exit_code, stdout, stderr = self._run_command([
                    "terraform", "init", "-backend=false"
                ], cwd=env_dir)
                
                if exit_code != 0:
                    self.validation_results["terraform_validation"]["errors"].append(
                        f"Environment-specific terraform init failed: {stderr}"
                    )
                    return False
                
                exit_code, stdout, stderr = self._run_command([
                    "terraform", "validate"
                ], cwd=env_dir)
                
                if exit_code != 0:
                    self.validation_results["terraform_validation"]["errors"].append(
                        f"Environment-specific terraform validation failed: {stderr}"
                    )
                    return False
            
            self.validation_results["terraform_validation"]["passed"] = True
            print("✅ Terraform validation passed")
            return True
            
        except Exception as e:
            self.validation_results["terraform_validation"]["errors"].append(str(e))
            print(f"❌ Terraform validation failed: {e}")
            return False
    
    def detect_infrastructure_drift(self) -> bool:
        """Detect infrastructure drift."""
        print("🔄 Detecting infrastructure drift...")
        
        session = self._get_aws_session()
        if not session:
            self.validation_results["drift_detection"]["errors"].append(
                "AWS credentials not available for drift detection"
            )
            print("⚠️  Skipping drift detection - AWS credentials not available")
            self.validation_results["drift_detection"]["passed"] = True
            return True
        
        try:
            terraform_dir = self.project_root / "terraform"
            
            # Initialize terraform with backend
            exit_code, stdout, stderr = self._run_command([
                "terraform", "init"
            ], cwd=terraform_dir)
            
            if exit_code != 0:
                self.validation_results["drift_detection"]["errors"].append(
                    f"Terraform init with backend failed: {stderr}"
                )
                return False
            
            # Select or create workspace
            exit_code, stdout, stderr = self._run_command([
                "terraform", "workspace", "select", self.environment
            ], cwd=terraform_dir)
            
            if exit_code != 0:
                # Try to create workspace if it doesn't exist
                exit_code, stdout, stderr = self._run_command([
                    "terraform", "workspace", "new", self.environment
                ], cwd=terraform_dir)
                
                if exit_code != 0:
                    self.validation_results["drift_detection"]["errors"].append(
                        f"Failed to create/select workspace: {stderr}"
                    )
                    return False
            
            # Create terraform plan to detect drift
            tfvars_file = f"{self.environment}.tfvars"
            exit_code, stdout, stderr = self._run_command([
                "terraform", "plan", 
                f"-var-file={tfvars_file}",
                "-detailed-exitcode",
                "-out=drift-check.tfplan"
            ], cwd=terraform_dir)
            
            if exit_code == 0:
                # No changes needed
                print("✅ No infrastructure drift detected")
                self.validation_results["drift_detection"]["passed"] = True
                self.validation_results["drift_detection"]["drift_detected"] = False
                return True
            elif exit_code == 2:
                # Changes detected
                print("⚠️  Infrastructure drift detected")
                self.validation_results["drift_detection"]["passed"] = True
                self.validation_results["drift_detection"]["drift_detected"] = True
                
                # Get plan details
                exit_code, plan_output, stderr = self._run_command([
                    "terraform", "show", "-json", "drift-check.tfplan"
                ], cwd=terraform_dir)
                
                if exit_code == 0:
                    try:
                        plan_data = json.loads(plan_output)
                        changes = plan_data.get("resource_changes", [])
                        
                        drift_summary = []
                        for change in changes:
                            action = change.get("change", {}).get("actions", [])
                            resource = change.get("address", "unknown")
                            drift_summary.append(f"{resource}: {', '.join(action)}")
                        
                        self.validation_results["drift_detection"]["errors"] = [
                            f"Drift detected in {len(changes)} resources:",
                            *drift_summary[:10]  # Limit to first 10 changes
                        ]
                        
                        if len(changes) > 10:
                            self.validation_results["drift_detection"]["errors"].append(
                                f"... and {len(changes) - 10} more changes"
                            )
                    except json.JSONDecodeError:
                        self.validation_results["drift_detection"]["errors"].append(
                            "Could not parse terraform plan output"
                        )
                
                return True
            else:
                # Plan failed
                self.validation_results["drift_detection"]["errors"].append(
                    f"Terraform plan failed: {stderr}"
                )
                return False
                
        except Exception as e:
            self.validation_results["drift_detection"]["errors"].append(str(e))
            print(f"❌ Drift detection failed: {e}")
            return False
    
    def validate_security_compliance(self) -> bool:
        """Validate security compliance."""
        print("🔒 Validating security compliance...")
        
        try:
            # Run terraform security scan
            exit_code, stdout, stderr = self._run_command([
                "tfsec", "terraform/", "--format", "json", "--soft-fail"
            ])
            
            security_issues = []
            if exit_code != 0 and stderr:
                security_issues.append(f"TFSec scan issues: {stderr}")
            
            # Parse tfsec output if available
            if stdout:
                try:
                    tfsec_data = json.loads(stdout)
                    results = tfsec_data.get("results", [])
                    
                    high_severity_issues = [
                        r for r in results 
                        if r.get("severity") in ["HIGH", "CRITICAL"]
                    ]
                    
                    if high_severity_issues:
                        security_issues.extend([
                            f"High/Critical security issue: {issue.get('description', 'Unknown')}"
                            for issue in high_severity_issues[:5]  # Limit to first 5
                        ])
                        
                        if len(high_severity_issues) > 5:
                            security_issues.append(
                                f"... and {len(high_severity_issues) - 5} more high/critical issues"
                            )
                except json.JSONDecodeError:
                    security_issues.append("Could not parse tfsec output")
            
            # Run Python security scan
            exit_code, stdout, stderr = self._run_command([
                "python", "-m", "bandit", "-r", 
                "shared/", "lambda/", "ecs/", "scripts/",
                "-f", "json", "-ll"
            ])
            
            if exit_code != 0 and stderr:
                security_issues.append(f"Python security issues: {stderr}")
            
            # Check for secrets
            exit_code, stdout, stderr = self._run_command([
                "detect-secrets", "scan", "--baseline", ".secrets.baseline", "."
            ])
            
            if exit_code != 0:
                security_issues.append("Potential secrets detected in code")
            
            if security_issues:
                self.validation_results["security_validation"]["errors"] = security_issues
                # For non-production environments, security issues are warnings
                if self.environment != "prod":
                    print("⚠️  Security issues found (warnings for non-prod)")
                    self.validation_results["security_validation"]["passed"] = True
                    return True
                else:
                    print("❌ Security issues found (blocking for production)")
                    return False
            else:
                self.validation_results["security_validation"]["passed"] = True
                print("✅ Security compliance validation passed")
                return True
                
        except Exception as e:
            self.validation_results["security_validation"]["errors"].append(str(e))
            print(f"❌ Security validation failed: {e}")
            return False
    
    def estimate_deployment_cost(self) -> bool:
        """Estimate deployment cost."""
        print("💰 Estimating deployment cost...")
        
        try:
            # Run cost estimation script
            exit_code, stdout, stderr = self._run_command([
                "python", "scripts/cost-monitor.py", 
                "--environment", self.environment,
                "--estimate", "--json"
            ])
            
            if exit_code == 0 and stdout:
                try:
                    cost_data = json.loads(stdout)
                    estimated_cost = cost_data.get("estimated_monthly_cost", 0)
                    self.validation_results["cost_estimation"]["estimated_cost"] = estimated_cost
                    
                    # Check cost thresholds
                    cost_thresholds = {
                        "dev": 100,      # $100/month for dev
                        "staging": 300,  # $300/month for staging
                        "prod": 1000     # $1000/month for prod
                    }
                    
                    threshold = cost_thresholds.get(self.environment, 500)
                    
                    if estimated_cost > threshold:
                        self.validation_results["cost_estimation"]["errors"].append(
                            f"Estimated cost ${estimated_cost:.2f}/month exceeds threshold ${threshold}/month"
                        )
                        
                        # For production, high costs are blocking
                        if self.environment == "prod" and estimated_cost > threshold * 2:
                            print(f"❌ Cost estimation failed - too expensive for {self.environment}")
                            return False
                        else:
                            print(f"⚠️  High cost warning: ${estimated_cost:.2f}/month")
                    else:
                        print(f"✅ Cost estimation passed: ${estimated_cost:.2f}/month")
                    
                    self.validation_results["cost_estimation"]["passed"] = True
                    return True
                    
                except json.JSONDecodeError:
                    self.validation_results["cost_estimation"]["errors"].append(
                        "Could not parse cost estimation output"
                    )
            else:
                self.validation_results["cost_estimation"]["errors"].append(
                    f"Cost estimation failed: {stderr}"
                )
            
            # If cost estimation fails, don't block deployment
            print("⚠️  Cost estimation unavailable")
            self.validation_results["cost_estimation"]["passed"] = True
            return True
            
        except Exception as e:
            self.validation_results["cost_estimation"]["errors"].append(str(e))
            print(f"⚠️  Cost estimation failed: {e}")
            # Don't block deployment on cost estimation failure
            self.validation_results["cost_estimation"]["passed"] = True
            return True
    
    def validate_resources(self) -> bool:
        """Validate resource configurations."""
        print("🔧 Validating resource configurations...")
        
        try:
            # Load configuration
            config_path = self.project_root / "config.yaml"
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            env_config = config.get("environments", {}).get(self.environment, {})
            resource_config = config.get("resources", {})
            
            validation_errors = []
            
            # Validate Lambda configuration
            lambda_config = resource_config.get("lambda", {})
            orchestrator_memory = lambda_config.get("orchestrator_memory", 512)
            sync_memory = lambda_config.get("sync_memory", 3008)
            timeout = lambda_config.get("timeout", 900)
            
            if orchestrator_memory < 128 or orchestrator_memory > 10240:
                validation_errors.append(
                    f"Orchestrator memory {orchestrator_memory}MB is outside valid range (128-10240)"
                )
            
            if sync_memory < 128 or sync_memory > 10240:
                validation_errors.append(
                    f"Sync memory {sync_memory}MB is outside valid range (128-10240)"
                )
            
            if timeout < 1 or timeout > 900:
                validation_errors.append(
                    f"Lambda timeout {timeout}s is outside valid range (1-900)"
                )
            
            # Validate ECS configuration
            ecs_config = resource_config.get("ecs", {})
            task_cpu = ecs_config.get("task_cpu", 2048)
            task_memory = ecs_config.get("task_memory", 8192)
            
            # Valid CPU/Memory combinations for Fargate
            valid_combinations = {
                256: [512, 1024, 2048],
                512: [1024, 2048, 3072, 4096],
                1024: [2048, 3072, 4096, 5120, 6144, 7168, 8192],
                2048: [4096, 5120, 6144, 7168, 8192, 9216, 10240, 11264, 12288, 13312, 14336, 15360, 16384],
                4096: list(range(8192, 30721, 1024)),
                8192: list(range(16384, 61441, 4096)),
                16384: list(range(32768, 122881, 8192))
            }
            
            if task_cpu not in valid_combinations:
                validation_errors.append(f"Invalid ECS task CPU: {task_cpu}")
            elif task_memory not in valid_combinations[task_cpu]:
                validation_errors.append(
                    f"Invalid ECS memory {task_memory}MB for CPU {task_cpu}. "
                    f"Valid options: {valid_combinations[task_cpu]}"
                )
            
            # Validate environment-specific settings
            size_threshold = env_config.get("size_threshold_gb", 20)
            if size_threshold < 1 or size_threshold > 100:
                validation_errors.append(
                    f"Size threshold {size_threshold}GB is outside reasonable range (1-100)"
                )
            
            # Validate schedule expression
            schedule = env_config.get("schedule_expression", "")
            if not schedule.startswith("cron(") and not schedule.startswith("rate("):
                validation_errors.append(
                    f"Invalid schedule expression: {schedule}"
                )
            
            if validation_errors:
                self.validation_results["resource_validation"]["errors"] = validation_errors
                print("❌ Resource validation failed")
                return False
            else:
                self.validation_results["resource_validation"]["passed"] = True
                print("✅ Resource validation passed")
                return True
                
        except Exception as e:
            self.validation_results["resource_validation"]["errors"].append(str(e))
            print(f"❌ Resource validation failed: {e}")
            return False
    
    def run_all_validations(self) -> bool:
        """Run all deployment validations."""
        print(f"🚀 Starting deployment validation for {self.environment} environment...\n")
        
        validations = [
            ("Configuration", self.validate_configuration),
            ("Terraform", self.validate_terraform),
            ("Infrastructure Drift", self.detect_infrastructure_drift),
            ("Security Compliance", self.validate_security_compliance),
            ("Cost Estimation", self.estimate_deployment_cost),
            ("Resource Configuration", self.validate_resources),
        ]
        
        all_passed = True
        for name, validation_func in validations:
            try:
                if not validation_func():
                    all_passed = False
            except Exception as e:
                print(f"❌ {name} validation failed with exception: {e}")
                all_passed = False
            print()
        
        return all_passed
    
    def generate_validation_report(self) -> Dict:
        """Generate a detailed validation report."""
        total_validations = len(self.validation_results)
        passed_validations = sum(
            1 for result in self.validation_results.values() 
            if result["passed"]
        )
        
        report = {
            "environment": self.environment,
            "summary": {
                "total_validations": total_validations,
                "passed_validations": passed_validations,
                "failed_validations": total_validations - passed_validations,
                "success_rate": f"{(passed_validations / total_validations) * 100:.1f}%",
                "deployment_ready": passed_validations == total_validations
            },
            "validations": self.validation_results,
            "recommendations": self._generate_recommendations()
        }
        
        return report
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on validation results."""
        recommendations = []
        
        # Configuration recommendations
        if not self.validation_results["config_validation"]["passed"]:
            recommendations.append(
                "Fix configuration errors before deployment"
            )
        
        # Drift recommendations
        if self.validation_results["drift_detection"].get("drift_detected"):
            recommendations.append(
                "Review infrastructure drift and consider applying changes"
            )
        
        # Security recommendations
        if not self.validation_results["security_validation"]["passed"]:
            recommendations.append(
                "Address security issues before production deployment"
            )
        
        # Cost recommendations
        estimated_cost = self.validation_results["cost_estimation"].get("estimated_cost", 0)
        if estimated_cost > 500:
            recommendations.append(
                f"Consider cost optimization - estimated ${estimated_cost:.2f}/month"
            )
        
        return recommendations
    
    def print_validation_summary(self):
        """Print a summary of all validations."""
        report = self.generate_validation_report()
        summary = report["summary"]
        
        print("=" * 70)
        print(f"📊 DEPLOYMENT VALIDATION SUMMARY - {self.environment.upper()}")
        print("=" * 70)
        print(f"Total Validations: {summary['total_validations']}")
        print(f"Passed: {summary['passed_validations']}")
        print(f"Failed: {summary['failed_validations']}")
        print(f"Success Rate: {summary['success_rate']}")
        print(f"Deployment Ready: {'✅ YES' if summary['deployment_ready'] else '❌ NO'}")
        print()
        
        if summary['failed_validations'] > 0:
            print("❌ FAILED VALIDATIONS:")
            for validation_name, result in self.validation_results.items():
                if not result["passed"]:
                    print(f"  • {validation_name.replace('_', ' ').title()}")
                    for error in result["errors"]:
                        print(f"    - {error}")
            print()
        
        # Show drift information
        if self.validation_results["drift_detection"].get("drift_detected"):
            print("⚠️  INFRASTRUCTURE DRIFT DETECTED:")
            for error in self.validation_results["drift_detection"]["errors"]:
                print(f"  - {error}")
            print()
        
        # Show cost information
        estimated_cost = self.validation_results["cost_estimation"].get("estimated_cost", 0)
        if estimated_cost > 0:
            print(f"💰 ESTIMATED MONTHLY COST: ${estimated_cost:.2f}")
            print()
        
        # Show recommendations
        recommendations = report["recommendations"]
        if recommendations:
            print("💡 RECOMMENDATIONS:")
            for rec in recommendations:
                print(f"  • {rec}")
            print()
        
        print("=" * 70)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate deployment readiness"
    )
    parser.add_argument(
        "environment",
        choices=["dev", "staging", "prod"],
        help="Target environment for deployment"
    )
    parser.add_argument(
        "--report",
        type=str,
        help="Generate JSON report to file"
    )
    parser.add_argument(
        "--fail-on-drift",
        action="store_true",
        help="Fail validation if infrastructure drift is detected"
    )
    parser.add_argument(
        "--skip-aws",
        action="store_true",
        help="Skip AWS-dependent validations (drift detection, cost estimation)"
    )
    
    args = parser.parse_args()
    
    project_root = Path(__file__).parent.parent
    validator = DeploymentValidator(project_root, args.environment)
    
    # Skip AWS validations if requested
    if args.skip_aws:
        validator.validation_results["drift_detection"]["passed"] = True
        validator.validation_results["cost_estimation"]["passed"] = True
    
    success = validator.run_all_validations()
    
    # Check drift failure condition
    if args.fail_on_drift and validator.validation_results["drift_detection"].get("drift_detected"):
        success = False
        print("❌ Validation failed due to infrastructure drift (--fail-on-drift)")
    
    validator.print_validation_summary()
    
    if args.report:
        report = validator.generate_validation_report()
        with open(args.report, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"📄 Validation report saved to {args.report}")
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()