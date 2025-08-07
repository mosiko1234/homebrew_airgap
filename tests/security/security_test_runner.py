#!/usr/bin/env python3
"""
Comprehensive security test runner.

This module provides a unified interface to run all security tests
including Terraform security scanning, dependency vulnerability scanning,
and secrets detection.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List

# Import security test modules
try:
    # Try relative imports first (when run as module)
    from .test_terraform_security import TerraformSecurityScanner
    from .test_dependency_security import DependencySecurityScanner
    from .test_secrets_detection import SecretsDetector
except ImportError:
    # Fall back to direct imports (when run as script)
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent))
    from test_terraform_security import TerraformSecurityScanner
    from test_dependency_security import DependencySecurityScanner
    from test_secrets_detection import SecretsDetector


class SecurityTestRunner:
    """Unified security test runner."""
    
    def __init__(self):
        self.terraform_scanner = TerraformSecurityScanner()
        self.dependency_scanner = DependencySecurityScanner()
        self.secrets_detector = SecretsDetector()
        self.results = {}
    
    def run_all_security_tests(self) -> Dict:
        """
        Run all security tests and return comprehensive results.
        
        Returns:
            Dict containing all security test results
        """
        print("🔒 Running comprehensive security test suite...")
        
        # 1. Terraform Security Tests
        print("\n📋 Running Terraform security tests...")
        terraform_results = self._run_terraform_tests()
        
        # 2. Dependency Security Tests
        print("\n📦 Running dependency security tests...")
        dependency_results = self._run_dependency_tests()
        
        # 3. Secrets Detection Tests
        print("\n🔍 Running secrets detection tests...")
        secrets_results = self._run_secrets_tests()
        
        # Compile comprehensive results
        self.results = {
            "terraform_security": terraform_results,
            "dependency_security": dependency_results,
            "secrets_detection": secrets_results,
            "summary": self._generate_summary()
        }
        
        return self.results
    
    def _run_terraform_tests(self) -> Dict:
        """Run all Terraform security tests."""
        results = {}
        
        try:
            # Run tfsec scan
            print("  • Running tfsec scan...")
            results["tfsec"] = self.terraform_scanner.run_tfsec_scan()
            
            # Run checkov scan
            print("  • Running checkov scan...")
            results["checkov"] = self.terraform_scanner.run_checkov_scan()
            
            # Validate IAM policies
            print("  • Validating IAM policies...")
            results["iam_validation"] = self.terraform_scanner.validate_iam_policies()
            
            # Calculate overall status
            statuses = [r["status"] for r in results.values()]
            if "error" in statuses:
                overall_status = "error"
            elif "failed" in statuses:
                overall_status = "failed"
            else:
                overall_status = "passed"
            
            results["overall_status"] = overall_status
            
        except Exception as e:
            results = {
                "overall_status": "error",
                "error": f"Failed to run Terraform security tests: {str(e)}"
            }
        
        return results
    
    def _run_dependency_tests(self) -> Dict:
        """Run all dependency security tests."""
        results = {}
        
        try:
            # Run safety scan
            print("  • Running safety vulnerability scan...")
            results["safety"] = self.dependency_scanner.run_safety_scan()
            
            # Run pip-audit scan
            print("  • Running pip-audit scan...")
            results["pip_audit"] = self.dependency_scanner.run_pip_audit_scan()
            
            # Scan requirements files
            print("  • Scanning requirements files...")
            results["requirements"] = self.dependency_scanner.scan_requirements_files()
            
            # Check for insecure packages
            print("  • Checking for insecure packages...")
            results["insecure_packages"] = self.dependency_scanner.check_insecure_packages()
            
            # Calculate overall status
            statuses = [r["status"] for r in results.values()]
            if "error" in statuses:
                overall_status = "error"
            elif "failed" in statuses:
                overall_status = "failed"
            elif "warning" in statuses:
                overall_status = "warning"
            else:
                overall_status = "passed"
            
            results["overall_status"] = overall_status
            
        except Exception as e:
            results = {
                "overall_status": "error",
                "error": f"Failed to run dependency security tests: {str(e)}"
            }
        
        return results
    
    def _run_secrets_tests(self) -> Dict:
        """Run all secrets detection tests."""
        results = {}
        
        try:
            # Run truffleHog scan
            print("  • Running truffleHog secrets scan...")
            results["trufflehog"] = self.secrets_detector.run_truffleHog_scan()
            
            # Run regex-based scan
            print("  • Running regex-based secrets scan...")
            results["regex"] = self.secrets_detector.run_regex_scan()
            
            # Scan environment variables
            print("  • Scanning environment variables...")
            results["environment_vars"] = self.secrets_detector.scan_environment_variables()
            
            # Validate git history
            print("  • Validating git history...")
            results["git_history"] = self.secrets_detector.validate_git_history()
            
            # Calculate overall status
            statuses = [r["status"] for r in results.values()]
            if "error" in statuses:
                overall_status = "error"
            elif "failed" in statuses:
                overall_status = "failed"
            elif "warning" in statuses:
                overall_status = "warning"
            else:
                overall_status = "passed"
            
            results["overall_status"] = overall_status
            
        except Exception as e:
            results = {
                "overall_status": "error",
                "error": f"Failed to run secrets detection tests: {str(e)}"
            }
        
        return results
    
    def _generate_summary(self) -> Dict:
        """Generate comprehensive security test summary."""
        summary = {
            "total_tests_run": 0,
            "tests_passed": 0,
            "tests_failed": 0,
            "tests_with_warnings": 0,
            "tests_with_errors": 0,
            "critical_issues": [],
            "high_issues": [],
            "medium_issues": [],
            "low_issues": []
        }
        
        # Count test results
        for category, category_results in self.results.items():
            if category == "summary":
                continue
                
            if isinstance(category_results, dict):
                for test_name, test_result in category_results.items():
                    if test_name == "overall_status":
                        continue
                        
                    if isinstance(test_result, dict) and "status" in test_result:
                        summary["total_tests_run"] += 1
                        
                        status = test_result["status"]
                        if status == "passed":
                            summary["tests_passed"] += 1
                        elif status == "failed":
                            summary["tests_failed"] += 1
                        elif status == "warning":
                            summary["tests_with_warnings"] += 1
                        elif status == "error":
                            summary["tests_with_errors"] += 1
                        
                        # Collect issues by severity
                        issues = test_result.get("issues", []) or test_result.get("vulnerabilities", []) or test_result.get("secrets", [])
                        for issue in issues:
                            severity = issue.get("severity", "LOW").upper()
                            if severity == "CRITICAL":
                                summary["critical_issues"].append(issue)
                            elif severity == "HIGH":
                                summary["high_issues"].append(issue)
                            elif severity == "MEDIUM":
                                summary["medium_issues"].append(issue)
                            else:
                                summary["low_issues"].append(issue)
        
        # Calculate overall security score
        total_issues = len(summary["critical_issues"]) + len(summary["high_issues"]) + len(summary["medium_issues"]) + len(summary["low_issues"])
        
        if len(summary["critical_issues"]) > 0:
            summary["security_score"] = "CRITICAL"
        elif len(summary["high_issues"]) > 5:
            summary["security_score"] = "HIGH_RISK"
        elif len(summary["high_issues"]) > 0 or len(summary["medium_issues"]) > 10:
            summary["security_score"] = "MEDIUM_RISK"
        elif total_issues > 0:
            summary["security_score"] = "LOW_RISK"
        else:
            summary["security_score"] = "SECURE"
        
        return summary
    
    def print_summary_report(self):
        """Print a formatted summary report."""
        if not self.results:
            print("❌ No security test results available")
            return
        
        summary = self.results.get("summary", {})
        
        print("\n" + "="*60)
        print("🔒 SECURITY TEST SUMMARY REPORT")
        print("="*60)
        
        # Overall security score
        score = summary.get("security_score", "UNKNOWN")
        score_emoji = {
            "SECURE": "✅",
            "LOW_RISK": "🟡",
            "MEDIUM_RISK": "🟠",
            "HIGH_RISK": "🔴",
            "CRITICAL": "💀"
        }.get(score, "❓")
        
        print(f"\n{score_emoji} Overall Security Score: {score}")
        
        # Test statistics
        print(f"\n📊 Test Statistics:")
        print(f"   Total tests run: {summary.get('total_tests_run', 0)}")
        print(f"   Tests passed: {summary.get('tests_passed', 0)}")
        print(f"   Tests failed: {summary.get('tests_failed', 0)}")
        print(f"   Tests with warnings: {summary.get('tests_with_warnings', 0)}")
        print(f"   Tests with errors: {summary.get('tests_with_errors', 0)}")
        
        # Issue breakdown
        print(f"\n🚨 Issues Found:")
        print(f"   Critical: {len(summary.get('critical_issues', []))}")
        print(f"   High: {len(summary.get('high_issues', []))}")
        print(f"   Medium: {len(summary.get('medium_issues', []))}")
        print(f"   Low: {len(summary.get('low_issues', []))}")
        
        # Category results
        print(f"\n📋 Category Results:")
        
        # Terraform Security
        tf_status = self.results.get("terraform_security", {}).get("overall_status", "unknown")
        tf_emoji = "✅" if tf_status == "passed" else "❌" if tf_status == "failed" else "⚠️"
        print(f"   {tf_emoji} Terraform Security: {tf_status.upper()}")
        
        # Dependency Security
        dep_status = self.results.get("dependency_security", {}).get("overall_status", "unknown")
        dep_emoji = "✅" if dep_status == "passed" else "❌" if dep_status == "failed" else "⚠️"
        print(f"   {dep_emoji} Dependency Security: {dep_status.upper()}")
        
        # Secrets Detection
        sec_status = self.results.get("secrets_detection", {}).get("overall_status", "unknown")
        sec_emoji = "✅" if sec_status == "passed" else "❌" if sec_status == "failed" else "⚠️"
        print(f"   {sec_emoji} Secrets Detection: {sec_status.upper()}")
        
        # Critical issues details
        if summary.get("critical_issues"):
            print(f"\n💀 CRITICAL ISSUES (MUST FIX):")
            for issue in summary["critical_issues"][:5]:  # Show first 5
                print(f"   - {issue.get('file', 'Unknown')}: {issue.get('issue', issue.get('description', 'Unknown issue'))}")
        
        # High issues details
        if summary.get("high_issues"):
            print(f"\n🔴 HIGH PRIORITY ISSUES:")
            for issue in summary["high_issues"][:5]:  # Show first 5
                print(f"   - {issue.get('file', 'Unknown')}: {issue.get('issue', issue.get('description', 'Unknown issue'))}")
        
        print("\n" + "="*60)
    
    def save_results_to_file(self, output_file: str = "security_test_results.json"):
        """Save results to JSON file."""
        try:
            with open(output_file, 'w') as f:
                json.dump(self.results, f, indent=2, default=str)
            print(f"📄 Results saved to {output_file}")
        except Exception as e:
            print(f"❌ Failed to save results: {str(e)}")
    
    def get_exit_code(self) -> int:
        """Get appropriate exit code based on results."""
        if not self.results:
            return 1
        
        summary = self.results.get("summary", {})
        
        # Exit with error if critical issues found
        if len(summary.get("critical_issues", [])) > 0:
            return 1
        
        # Exit with error if too many high-severity issues
        if len(summary.get("high_issues", [])) > 10:
            return 1
        
        # Exit with error if any tests failed
        if summary.get("tests_failed", 0) > 0:
            return 1
        
        return 0


def main():
    """Main entry point for security test runner."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run comprehensive security tests")
    parser.add_argument("--output", "-o", help="Output file for results (JSON)", default="security_test_results.json")
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress detailed output")
    parser.add_argument("--fail-on-high", action="store_true", help="Fail if high-severity issues found")
    
    args = parser.parse_args()
    
    # Create and run security test runner
    runner = SecurityTestRunner()
    
    try:
        # Run all security tests
        results = runner.run_all_security_tests()
        
        # Print summary unless quiet mode
        if not args.quiet:
            runner.print_summary_report()
        
        # Save results to file
        runner.save_results_to_file(args.output)
        
        # Exit with appropriate code
        exit_code = runner.get_exit_code()
        
        # Override exit code if fail-on-high is set
        if args.fail_on_high and len(results.get("summary", {}).get("high_issues", [])) > 0:
            exit_code = 1
        
        sys.exit(exit_code)
        
    except KeyboardInterrupt:
        print("\n❌ Security tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Security tests failed with error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()