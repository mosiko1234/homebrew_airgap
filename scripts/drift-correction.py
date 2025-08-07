#!/usr/bin/env python3
"""
Infrastructure Drift Correction Script

This script detects and optionally corrects infrastructure drift by:
- Comparing current infrastructure state with desired state
- Generating correction plans
- Applying corrections with approval
- Reporting drift status
"""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import boto3
from botocore.exceptions import ClientError, NoCredentialsError


class DriftCorrector:
    """Handles infrastructure drift detection and correction."""
    
    def __init__(self, project_root: Path, environment: str):
        self.project_root = project_root
        self.environment = environment
        self.terraform_dir = project_root / "terraform"
        self.drift_results = {
            "drift_detected": False,
            "resources_changed": 0,
            "changes": [],
            "correction_applied": False,
            "errors": []
        }
    
    def _run_command(self, command: List[str], cwd: Path = None) -> Tuple[int, str, str]:
        """Run a command and return exit code, stdout, stderr."""
        try:
            result = subprocess.run(
                command,
                cwd=cwd or self.terraform_dir,
                capture_output=True,
                text=True,
                timeout=600  # 10 minutes timeout
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return 1, "", "Command timed out after 10 minutes"
        except Exception as e:
            return 1, "", str(e)
    
    def initialize_terraform(self) -> bool:
        """Initialize Terraform with backend."""
        print("🔧 Initializing Terraform...")
        
        exit_code, stdout, stderr = self._run_command([
            "terraform", "init"
        ])
        
        if exit_code != 0:
            self.drift_results["errors"].append(f"Terraform init failed: {stderr}")
            return False
        
        # Select or create workspace
        exit_code, stdout, stderr = self._run_command([
            "terraform", "workspace", "select", self.environment
        ])
        
        if exit_code != 0:
            # Try to create workspace if it doesn't exist
            exit_code, stdout, stderr = self._run_command([
                "terraform", "workspace", "new", self.environment
            ])
            
            if exit_code != 0:
                self.drift_results["errors"].append(
                    f"Failed to create/select workspace: {stderr}"
                )
                return False
        
        print(f"✅ Terraform initialized for {self.environment} workspace")
        return True
    
    def detect_drift(self) -> bool:
        """Detect infrastructure drift."""
        print("🔍 Detecting infrastructure drift...")
        
        # Generate terraform vars
        exit_code, stdout, stderr = self._run_command([
            "python", "../scripts/config_processor.py",
            "--environment", self.environment,
            "--output", f"{self.environment}.tfvars"
        ])
        
        if exit_code != 0:
            self.drift_results["errors"].append(
                f"Failed to generate terraform vars: {stderr}"
            )
            return False
        
        # Create terraform plan to detect drift
        exit_code, stdout, stderr = self._run_command([
            "terraform", "plan",
            f"-var-file={self.environment}.tfvars",
            "-detailed-exitcode",
            "-out=drift-detection.tfplan"
        ])
        
        if exit_code == 0:
            # No changes needed
            print("✅ No infrastructure drift detected")
            self.drift_results["drift_detected"] = False
            return True
        elif exit_code == 2:
            # Changes detected
            print("⚠️  Infrastructure drift detected")
            self.drift_results["drift_detected"] = True
            
            # Get detailed plan information
            return self._analyze_drift_plan()
        else:
            # Plan failed
            self.drift_results["errors"].append(f"Terraform plan failed: {stderr}")
            return False
    
    def _analyze_drift_plan(self) -> bool:
        """Analyze the drift detection plan."""
        print("📊 Analyzing drift details...")
        
        # Get plan in JSON format
        exit_code, stdout, stderr = self._run_command([
            "terraform", "show", "-json", "drift-detection.tfplan"
        ])
        
        if exit_code != 0:
            self.drift_results["errors"].append(
                f"Failed to analyze plan: {stderr}"
            )
            return False
        
        try:
            plan_data = json.loads(stdout)
            resource_changes = plan_data.get("resource_changes", [])
            
            self.drift_results["resources_changed"] = len(resource_changes)
            
            # Categorize changes
            changes_by_action = {
                "create": [],
                "update": [],
                "delete": [],
                "replace": []
            }
            
            for change in resource_changes:
                address = change.get("address", "unknown")
                actions = change.get("change", {}).get("actions", [])
                
                change_info = {
                    "resource": address,
                    "actions": actions,
                    "reason": self._determine_change_reason(change)
                }
                
                if "create" in actions:
                    changes_by_action["create"].append(change_info)
                elif "delete" in actions and "create" in actions:
                    changes_by_action["replace"].append(change_info)
                elif "delete" in actions:
                    changes_by_action["delete"].append(change_info)
                else:
                    changes_by_action["update"].append(change_info)
            
            self.drift_results["changes"] = changes_by_action
            
            # Print summary
            print(f"📈 Drift Summary:")
            print(f"  • Resources to create: {len(changes_by_action['create'])}")
            print(f"  • Resources to update: {len(changes_by_action['update'])}")
            print(f"  • Resources to delete: {len(changes_by_action['delete'])}")
            print(f"  • Resources to replace: {len(changes_by_action['replace'])}")
            
            return True
            
        except json.JSONDecodeError as e:
            self.drift_results["errors"].append(f"Failed to parse plan JSON: {e}")
            return False
    
    def _determine_change_reason(self, change: Dict) -> str:
        """Determine the reason for a resource change."""
        change_detail = change.get("change", {})
        
        # Check if it's a configuration change
        if change_detail.get("before") and change_detail.get("after"):
            return "Configuration drift"
        elif not change_detail.get("before"):
            return "New resource"
        elif not change_detail.get("after"):
            return "Resource removal"
        else:
            return "Unknown change"
    
    def generate_correction_plan(self) -> bool:
        """Generate a detailed correction plan."""
        if not self.drift_results["drift_detected"]:
            print("ℹ️  No drift detected, no correction plan needed")
            return True
        
        print("📋 Generating correction plan...")
        
        # Get human-readable plan
        exit_code, stdout, stderr = self._run_command([
            "terraform", "show", "drift-detection.tfplan"
        ])
        
        if exit_code != 0:
            self.drift_results["errors"].append(
                f"Failed to generate correction plan: {stderr}"
            )
            return False
        
        # Save plan to file
        plan_file = self.terraform_dir / f"correction-plan-{self.environment}.txt"
        with open(plan_file, 'w') as f:
            f.write(stdout)
        
        print(f"📄 Correction plan saved to {plan_file}")
        
        # Display summary
        changes = self.drift_results["changes"]
        print("\n🔧 Correction Plan Summary:")
        
        for action, resources in changes.items():
            if resources:
                print(f"\n{action.upper()} ({len(resources)} resources):")
                for resource in resources[:5]:  # Show first 5
                    print(f"  • {resource['resource']}: {resource['reason']}")
                if len(resources) > 5:
                    print(f"  ... and {len(resources) - 5} more")
        
        return True
    
    def apply_correction(self, auto_approve: bool = False) -> bool:
        """Apply drift correction."""
        if not self.drift_results["drift_detected"]:
            print("ℹ️  No drift detected, no correction needed")
            return True
        
        print("🔧 Applying drift correction...")
        
        # Check for dangerous changes
        dangerous_changes = self._check_dangerous_changes()
        if dangerous_changes and not auto_approve:
            print("⚠️  Dangerous changes detected:")
            for change in dangerous_changes:
                print(f"  • {change}")
            
            if not self._confirm_dangerous_changes():
                print("❌ Drift correction cancelled by user")
                return False
        
        # Apply the plan
        exit_code, stdout, stderr = self._run_command([
            "terraform", "apply", "drift-detection.tfplan"
        ])
        
        if exit_code == 0:
            print("✅ Drift correction applied successfully")
            self.drift_results["correction_applied"] = True
            return True
        else:
            self.drift_results["errors"].append(f"Failed to apply correction: {stderr}")
            print(f"❌ Drift correction failed: {stderr}")
            return False
    
    def _check_dangerous_changes(self) -> List[str]:
        """Check for potentially dangerous changes."""
        dangerous_changes = []
        changes = self.drift_results["changes"]
        
        # Check for deletions
        if changes["delete"]:
            dangerous_changes.extend([
                f"DELETE: {change['resource']}" 
                for change in changes["delete"]
            ])
        
        # Check for replacements
        if changes["replace"]:
            dangerous_changes.extend([
                f"REPLACE: {change['resource']}" 
                for change in changes["replace"]
            ])
        
        # Check for database-related changes
        for change_list in changes.values():
            for change in change_list:
                resource = change["resource"].lower()
                if any(db_type in resource for db_type in ["rds", "dynamodb", "database"]):
                    dangerous_changes.append(f"DATABASE CHANGE: {change['resource']}")
        
        return dangerous_changes
    
    def _confirm_dangerous_changes(self) -> bool:
        """Ask user to confirm dangerous changes."""
        print("\n⚠️  WARNING: This correction includes potentially dangerous changes!")
        print("These changes could result in data loss or service disruption.")
        print("\nDo you want to proceed? (yes/no): ", end="")
        
        try:
            response = input().strip().lower()
            return response in ["yes", "y"]
        except (EOFError, KeyboardInterrupt):
            return False
    
    def create_drift_report(self) -> Dict:
        """Create a comprehensive drift report."""
        report = {
            "environment": self.environment,
            "timestamp": subprocess.run(
                ["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"],
                capture_output=True,
                text=True
            ).stdout.strip(),
            "drift_detected": self.drift_results["drift_detected"],
            "resources_changed": self.drift_results["resources_changed"],
            "correction_applied": self.drift_results["correction_applied"],
            "changes_summary": {},
            "errors": self.drift_results["errors"]
        }
        
        if self.drift_results["drift_detected"]:
            changes = self.drift_results["changes"]
            report["changes_summary"] = {
                action: len(resources) 
                for action, resources in changes.items()
            }
            report["detailed_changes"] = changes
        
        return report
    
    def print_drift_summary(self):
        """Print a summary of drift detection and correction."""
        print("\n" + "=" * 60)
        print(f"🔄 DRIFT CORRECTION SUMMARY - {self.environment.upper()}")
        print("=" * 60)
        
        if not self.drift_results["drift_detected"]:
            print("✅ No infrastructure drift detected")
            print("🎯 Infrastructure is in sync with configuration")
        else:
            print(f"⚠️  Infrastructure drift detected")
            print(f"📊 Resources affected: {self.drift_results['resources_changed']}")
            
            changes = self.drift_results["changes"]
            for action, resources in changes.items():
                if resources:
                    print(f"  • {action.capitalize()}: {len(resources)} resources")
            
            if self.drift_results["correction_applied"]:
                print("✅ Drift correction applied successfully")
            else:
                print("⏸️  Drift correction not applied")
        
        if self.drift_results["errors"]:
            print("\n❌ Errors encountered:")
            for error in self.drift_results["errors"]:
                print(f"  • {error}")
        
        print("=" * 60)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Detect and correct infrastructure drift"
    )
    parser.add_argument(
        "environment",
        choices=["dev", "staging", "prod"],
        help="Target environment"
    )
    parser.add_argument(
        "--detect-only",
        action="store_true",
        help="Only detect drift, don't apply corrections"
    )
    parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="Automatically approve corrections (dangerous)"
    )
    parser.add_argument(
        "--report",
        type=str,
        help="Generate JSON report to file"
    )
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="Generate correction plan but don't apply"
    )
    
    args = parser.parse_args()
    
    project_root = Path(__file__).parent.parent
    corrector = DriftCorrector(project_root, args.environment)
    
    success = True
    
    # Initialize Terraform
    if not corrector.initialize_terraform():
        success = False
    
    # Detect drift
    if success and not corrector.detect_drift():
        success = False
    
    # Generate correction plan if drift detected
    if success and corrector.drift_results["drift_detected"]:
        if not corrector.generate_correction_plan():
            success = False
    
    # Apply correction if requested and not detect-only
    if (success and 
        corrector.drift_results["drift_detected"] and 
        not args.detect_only and 
        not args.plan_only):
        
        if not corrector.apply_correction(args.auto_approve):
            success = False
    
    # Print summary
    corrector.print_drift_summary()
    
    # Generate report if requested
    if args.report:
        report = corrector.create_drift_report()
        with open(args.report, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"\n📄 Drift report saved to {args.report}")
    
    # Exit with appropriate code
    if not success:
        sys.exit(1)
    elif corrector.drift_results["drift_detected"] and args.detect_only:
        # Exit with code 2 to indicate drift detected but not corrected
        sys.exit(2)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()