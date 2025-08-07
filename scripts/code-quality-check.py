#!/usr/bin/env python3
"""
Code Quality Check Script

This script runs comprehensive code quality checks including:
- Python linting with flake8
- Python formatting with black
- Import sorting with isort
- Terraform formatting and validation
- Security scanning
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple


class CodeQualityChecker:
    """Handles code quality checks for the project."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.results = {
            "python_lint": {"passed": False, "errors": []},
            "python_format": {"passed": False, "errors": []},
            "python_imports": {"passed": False, "errors": []},
            "terraform_format": {"passed": False, "errors": []},
            "terraform_validate": {"passed": False, "errors": []},
            "security_scan": {"passed": False, "errors": []},
        }
    
    def run_command(self, command: List[str], cwd: Path = None) -> Tuple[int, str, str]:
        """Run a command and return exit code, stdout, stderr."""
        try:
            result = subprocess.run(
                command,
                cwd=cwd or self.project_root,
                capture_output=True,
                text=True,
                timeout=300
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return 1, "", "Command timed out after 300 seconds"
        except Exception as e:
            return 1, "", str(e)
    
    def check_python_lint(self) -> bool:
        """Run flake8 linting on Python files."""
        print("🔍 Running Python linting (flake8)...")
        
        exit_code, stdout, stderr = self.run_command([
            "python", "-m", "flake8", 
            "shared/", "lambda/", "ecs/", "scripts/", "tests/",
            "--format=json"
        ])
        
        if exit_code == 0:
            self.results["python_lint"]["passed"] = True
            print("✅ Python linting passed")
            return True
        else:
            self.results["python_lint"]["errors"] = [
                f"Flake8 errors: {stderr}" if stderr else stdout
            ]
            print(f"❌ Python linting failed: {stderr}")
            return False
    
    def check_python_format(self) -> bool:
        """Check Python code formatting with black."""
        print("🎨 Checking Python formatting (black)...")
        
        exit_code, stdout, stderr = self.run_command([
            "python", "-m", "black", 
            "--check", "--diff",
            "shared/", "lambda/", "ecs/", "scripts/", "tests/"
        ])
        
        if exit_code == 0:
            self.results["python_format"]["passed"] = True
            print("✅ Python formatting is correct")
            return True
        else:
            self.results["python_format"]["errors"] = [
                f"Black formatting issues: {stdout}"
            ]
            print(f"❌ Python formatting issues found: {stdout}")
            return False
    
    def check_python_imports(self) -> bool:
        """Check Python import sorting with isort."""
        print("📦 Checking Python import sorting (isort)...")
        
        exit_code, stdout, stderr = self.run_command([
            "python", "-m", "isort", 
            "--check-only", "--diff",
            "shared/", "lambda/", "ecs/", "scripts/", "tests/"
        ])
        
        if exit_code == 0:
            self.results["python_imports"]["passed"] = True
            print("✅ Python import sorting is correct")
            return True
        else:
            self.results["python_imports"]["errors"] = [
                f"Import sorting issues: {stdout}"
            ]
            print(f"❌ Python import sorting issues found: {stdout}")
            return False
    
    def check_terraform_format(self) -> bool:
        """Check Terraform formatting."""
        print("🏗️  Checking Terraform formatting...")
        
        terraform_dirs = [
            "terraform/",
            "terraform/modules/",
            "terraform/environments/"
        ]
        
        all_passed = True
        for tf_dir in terraform_dirs:
            tf_path = self.project_root / tf_dir
            if not tf_path.exists():
                continue
                
            exit_code, stdout, stderr = self.run_command([
                "terraform", "fmt", "-check", "-recursive"
            ], cwd=tf_path)
            
            if exit_code != 0:
                all_passed = False
                self.results["terraform_format"]["errors"].append(
                    f"Terraform formatting issues in {tf_dir}: {stdout}"
                )
        
        if all_passed:
            self.results["terraform_format"]["passed"] = True
            print("✅ Terraform formatting is correct")
            return True
        else:
            print("❌ Terraform formatting issues found")
            return False
    
    def check_terraform_validate(self) -> bool:
        """Validate Terraform configurations."""
        print("🔧 Validating Terraform configurations...")
        
        terraform_dirs = [
            "terraform/",
            "terraform/environments/dev/",
            "terraform/environments/staging/",
            "terraform/environments/prod/"
        ]
        
        all_passed = True
        for tf_dir in terraform_dirs:
            tf_path = self.project_root / tf_dir
            if not tf_path.exists():
                continue
            
            # Initialize terraform
            init_code, _, init_stderr = self.run_command([
                "terraform", "init", "-backend=false"
            ], cwd=tf_path)
            
            if init_code != 0:
                all_passed = False
                self.results["terraform_validate"]["errors"].append(
                    f"Terraform init failed in {tf_dir}: {init_stderr}"
                )
                continue
            
            # Validate terraform
            validate_code, validate_stdout, validate_stderr = self.run_command([
                "terraform", "validate", "-json"
            ], cwd=tf_path)
            
            if validate_code != 0:
                all_passed = False
                self.results["terraform_validate"]["errors"].append(
                    f"Terraform validation failed in {tf_dir}: {validate_stderr}"
                )
        
        if all_passed:
            self.results["terraform_validate"]["passed"] = True
            print("✅ Terraform validation passed")
            return True
        else:
            print("❌ Terraform validation failed")
            return False
    
    def check_security(self) -> bool:
        """Run security scans."""
        print("🔒 Running security scans...")
        
        # Run bandit for Python security
        bandit_code, bandit_stdout, bandit_stderr = self.run_command([
            "python", "-m", "bandit", "-r", 
            "shared/", "lambda/", "ecs/", "scripts/",
            "-f", "json", "-ll"
        ])
        
        # Run tfsec for Terraform security
        tfsec_code, tfsec_stdout, tfsec_stderr = self.run_command([
            "tfsec", "terraform/", "--format", "json", "--soft-fail"
        ])
        
        security_issues = []
        
        if bandit_code != 0 and bandit_stderr:
            security_issues.append(f"Bandit security issues: {bandit_stderr}")
        
        if tfsec_code != 0 and tfsec_stderr:
            security_issues.append(f"TFSec security issues: {tfsec_stderr}")
        
        if not security_issues:
            self.results["security_scan"]["passed"] = True
            print("✅ Security scans passed")
            return True
        else:
            self.results["security_scan"]["errors"] = security_issues
            print("❌ Security issues found")
            return False
    
    def fix_python_formatting(self) -> bool:
        """Auto-fix Python formatting issues."""
        print("🔧 Auto-fixing Python formatting...")
        
        # Run black to fix formatting
        black_code, _, black_stderr = self.run_command([
            "python", "-m", "black",
            "shared/", "lambda/", "ecs/", "scripts/", "tests/"
        ])
        
        # Run isort to fix imports
        isort_code, _, isort_stderr = self.run_command([
            "python", "-m", "isort",
            "shared/", "lambda/", "ecs/", "scripts/", "tests/"
        ])
        
        if black_code == 0 and isort_code == 0:
            print("✅ Python formatting fixed")
            return True
        else:
            print(f"❌ Failed to fix Python formatting: {black_stderr} {isort_stderr}")
            return False
    
    def fix_terraform_formatting(self) -> bool:
        """Auto-fix Terraform formatting."""
        print("🔧 Auto-fixing Terraform formatting...")
        
        terraform_dirs = [
            "terraform/",
            "terraform/modules/",
            "terraform/environments/"
        ]
        
        all_fixed = True
        for tf_dir in terraform_dirs:
            tf_path = self.project_root / tf_dir
            if not tf_path.exists():
                continue
                
            exit_code, _, stderr = self.run_command([
                "terraform", "fmt", "-recursive"
            ], cwd=tf_path)
            
            if exit_code != 0:
                all_fixed = False
                print(f"❌ Failed to fix Terraform formatting in {tf_dir}: {stderr}")
        
        if all_fixed:
            print("✅ Terraform formatting fixed")
            return True
        else:
            return False
    
    def run_all_checks(self, fix: bool = False) -> bool:
        """Run all code quality checks."""
        print("🚀 Starting comprehensive code quality checks...\n")
        
        if fix:
            print("🔧 Auto-fix mode enabled\n")
            self.fix_python_formatting()
            self.fix_terraform_formatting()
            print()
        
        checks = [
            self.check_python_lint,
            self.check_python_format,
            self.check_python_imports,
            self.check_terraform_format,
            self.check_terraform_validate,
            self.check_security,
        ]
        
        all_passed = True
        for check in checks:
            try:
                if not check():
                    all_passed = False
            except Exception as e:
                print(f"❌ Check failed with exception: {e}")
                all_passed = False
            print()
        
        return all_passed
    
    def generate_report(self) -> Dict:
        """Generate a detailed report of all checks."""
        total_checks = len(self.results)
        passed_checks = sum(1 for result in self.results.values() if result["passed"])
        
        report = {
            "summary": {
                "total_checks": total_checks,
                "passed_checks": passed_checks,
                "failed_checks": total_checks - passed_checks,
                "success_rate": f"{(passed_checks / total_checks) * 100:.1f}%"
            },
            "details": self.results
        }
        
        return report
    
    def print_summary(self):
        """Print a summary of all checks."""
        report = self.generate_report()
        summary = report["summary"]
        
        print("=" * 60)
        print("📊 CODE QUALITY SUMMARY")
        print("=" * 60)
        print(f"Total Checks: {summary['total_checks']}")
        print(f"Passed: {summary['passed_checks']}")
        print(f"Failed: {summary['failed_checks']}")
        print(f"Success Rate: {summary['success_rate']}")
        print()
        
        if summary['failed_checks'] > 0:
            print("❌ FAILED CHECKS:")
            for check_name, result in self.results.items():
                if not result["passed"]:
                    print(f"  • {check_name.replace('_', ' ').title()}")
                    for error in result["errors"]:
                        print(f"    - {error}")
            print()
        
        print("=" * 60)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run comprehensive code quality checks"
    )
    parser.add_argument(
        "--fix", 
        action="store_true", 
        help="Auto-fix formatting issues"
    )
    parser.add_argument(
        "--report", 
        type=str, 
        help="Generate JSON report to file"
    )
    
    args = parser.parse_args()
    
    project_root = Path(__file__).parent.parent
    checker = CodeQualityChecker(project_root)
    
    success = checker.run_all_checks(fix=args.fix)
    checker.print_summary()
    
    if args.report:
        report = checker.generate_report()
        with open(args.report, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"📄 Report saved to {args.report}")
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()