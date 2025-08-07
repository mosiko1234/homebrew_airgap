#!/usr/bin/env python3
"""
Deployment Status Tracking System
Tracks deployment status, history, and provides rollback capabilities
"""

import json
import os
import sys
import argparse
import subprocess
import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import boto3
from botocore.exceptions import ClientError


@dataclass
class DeploymentRecord:
    """Represents a deployment record"""
    environment: str
    action: str
    status: str
    timestamp: str
    commit_sha: str
    user: str
    terraform_version: str
    rollback_version: Optional[str] = None
    duration_seconds: Optional[int] = None
    error_message: Optional[str] = None
    terraform_outputs: Optional[Dict] = None


class DeploymentTracker:
    """Manages deployment tracking and rollback functionality"""
    
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.records_dir = self.project_root / ".deployment-records"
        self.records_dir.mkdir(exist_ok=True)
        
        # Initialize AWS clients if available
        try:
            self.s3_client = boto3.client('s3')
            self.ssm_client = boto3.client('ssm')
        except Exception:
            self.s3_client = None
            self.ssm_client = None
    
    def create_record(self, environment: str, action: str, status: str, 
                     commit_sha: str = None, rollback_version: str = None,
                     error_message: str = None, terraform_outputs: Dict = None) -> str:
        """Create a new deployment record"""
        
        if not commit_sha:
            try:
                commit_sha = subprocess.check_output(
                    ['git', 'rev-parse', 'HEAD'], 
                    cwd=self.project_root,
                    text=True
                ).strip()
            except subprocess.CalledProcessError:
                commit_sha = "unknown"
        
        # Get Terraform version
        try:
            tf_version_output = subprocess.check_output(
                ['terraform', 'version', '-json'],
                text=True
            )
            tf_version = json.loads(tf_version_output)['terraform_version']
        except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError):
            tf_version = "unknown"
        
        record = DeploymentRecord(
            environment=environment,
            action=action,
            status=status,
            timestamp=datetime.datetime.utcnow().isoformat() + "Z",
            commit_sha=commit_sha,
            user=os.getenv('USER', 'unknown'),
            terraform_version=tf_version,
            rollback_version=rollback_version,
            error_message=error_message,
            terraform_outputs=terraform_outputs
        )
        
        # Save record to file
        record_filename = f"{environment}-{datetime.datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.json"
        record_path = self.records_dir / record_filename
        
        with open(record_path, 'w') as f:
            json.dump(asdict(record), f, indent=2)
        
        print(f"Deployment record created: {record_path}")
        
        # Store in SSM Parameter Store if available
        self._store_in_ssm(record)
        
        return str(record_path)
    
    def _store_in_ssm(self, record: DeploymentRecord):
        """Store deployment record in AWS SSM Parameter Store"""
        if not self.ssm_client:
            return
        
        try:
            parameter_name = f"/homebrew-bottles-sync/deployments/{record.environment}/latest"
            
            self.ssm_client.put_parameter(
                Name=parameter_name,
                Value=json.dumps(asdict(record)),
                Type='String',
                Overwrite=True,
                Description=f"Latest deployment record for {record.environment}"
            )
            
            print(f"Deployment record stored in SSM: {parameter_name}")
            
        except ClientError as e:
            print(f"Warning: Failed to store record in SSM: {e}")
    
    def get_latest_record(self, environment: str) -> Optional[DeploymentRecord]:
        """Get the latest deployment record for an environment"""
        
        # Try to get from SSM first
        if self.ssm_client:
            try:
                parameter_name = f"/homebrew-bottles-sync/deployments/{environment}/latest"
                response = self.ssm_client.get_parameter(Name=parameter_name)
                record_data = json.loads(response['Parameter']['Value'])
                return DeploymentRecord(**record_data)
            except ClientError:
                pass  # Fall back to local files
        
        # Get from local files
        env_records = []
        for record_file in self.records_dir.glob(f"{environment}-*.json"):
            try:
                with open(record_file, 'r') as f:
                    record_data = json.load(f)
                    env_records.append((record_file.stat().st_mtime, DeploymentRecord(**record_data)))
            except (json.JSONDecodeError, TypeError):
                continue
        
        if not env_records:
            return None
        
        # Return the most recent record
        env_records.sort(key=lambda x: x[0], reverse=True)
        return env_records[0][1]
    
    def get_deployment_history(self, environment: str, limit: int = 10) -> List[DeploymentRecord]:
        """Get deployment history for an environment"""
        
        env_records = []
        for record_file in self.records_dir.glob(f"{environment}-*.json"):
            try:
                with open(record_file, 'r') as f:
                    record_data = json.load(f)
                    env_records.append((record_file.stat().st_mtime, DeploymentRecord(**record_data)))
            except (json.JSONDecodeError, TypeError):
                continue
        
        # Sort by timestamp (most recent first) and limit results
        env_records.sort(key=lambda x: x[0], reverse=True)
        return [record[1] for record in env_records[:limit]]
    
    def get_rollback_candidates(self, environment: str) -> List[DeploymentRecord]:
        """Get successful deployments that can be used for rollback"""
        
        history = self.get_deployment_history(environment, limit=20)
        return [record for record in history if record.status == "success" and record.action == "deploy"]
    
    def can_rollback(self, environment: str, target_commit: str) -> bool:
        """Check if rollback to a specific commit is possible"""
        
        candidates = self.get_rollback_candidates(environment)
        return any(record.commit_sha == target_commit for record in candidates)
    
    def get_environment_status(self, environment: str) -> Dict[str, Any]:
        """Get current status of an environment"""
        
        latest_record = self.get_latest_record(environment)
        if not latest_record:
            return {
                "environment": environment,
                "status": "unknown",
                "message": "No deployment records found"
            }
        
        return {
            "environment": environment,
            "status": latest_record.status,
            "last_deployment": latest_record.timestamp,
            "commit_sha": latest_record.commit_sha,
            "user": latest_record.user,
            "action": latest_record.action,
            "terraform_version": latest_record.terraform_version
        }
    
    def generate_status_report(self) -> Dict[str, Any]:
        """Generate a comprehensive status report for all environments"""
        
        environments = ["dev", "staging", "prod"]
        report = {
            "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
            "environments": {}
        }
        
        for env in environments:
            report["environments"][env] = self.get_environment_status(env)
        
        return report
    
    def get_deployment_metrics(self, environment: str, days: int = 30) -> Dict[str, Any]:
        """Get deployment metrics for an environment over specified days"""
        
        cutoff_date = datetime.datetime.utcnow() - datetime.timedelta(days=days)
        history = self.get_deployment_history(environment, limit=100)
        
        # Filter by date
        recent_deployments = [
            record for record in history
            if datetime.datetime.fromisoformat(record.timestamp.replace('Z', '+00:00')) > cutoff_date
        ]
        
        if not recent_deployments:
            return {
                "environment": environment,
                "period_days": days,
                "total_deployments": 0,
                "success_rate": 0.0,
                "average_duration": 0,
                "metrics": {}
            }
        
        # Calculate metrics
        total_deployments = len(recent_deployments)
        successful_deployments = len([r for r in recent_deployments if r.status == "success"])
        failed_deployments = len([r for r in recent_deployments if r.status == "failed"])
        
        success_rate = (successful_deployments / total_deployments) * 100 if total_deployments > 0 else 0
        
        # Calculate average duration for deployments that have duration
        durations = [r.duration_seconds for r in recent_deployments if r.duration_seconds]
        average_duration = sum(durations) / len(durations) if durations else 0
        
        # Group by action type
        actions = {}
        for record in recent_deployments:
            if record.action not in actions:
                actions[record.action] = {"count": 0, "success": 0, "failed": 0}
            actions[record.action]["count"] += 1
            if record.status == "success":
                actions[record.action]["success"] += 1
            elif record.status == "failed":
                actions[record.action]["failed"] += 1
        
        return {
            "environment": environment,
            "period_days": days,
            "total_deployments": total_deployments,
            "successful_deployments": successful_deployments,
            "failed_deployments": failed_deployments,
            "success_rate": round(success_rate, 1),
            "average_duration_seconds": round(average_duration, 1),
            "actions": actions,
            "most_recent": recent_deployments[0].timestamp if recent_deployments else None
        }
    
    def update_deployment_duration(self, environment: str, duration_seconds: int):
        """Update the duration of the most recent deployment"""
        
        latest_record = self.get_latest_record(environment)
        if latest_record and latest_record.duration_seconds is None:
            # Update the record file
            for record_file in self.records_dir.glob(f"{environment}-*.json"):
                try:
                    with open(record_file, 'r') as f:
                        record_data = json.load(f)
                    
                    if (record_data.get('timestamp') == latest_record.timestamp and
                        record_data.get('commit_sha') == latest_record.commit_sha):
                        
                        record_data['duration_seconds'] = duration_seconds
                        
                        with open(record_file, 'w') as f:
                            json.dump(record_data, f, indent=2)
                        
                        print(f"Updated deployment duration: {duration_seconds}s")
                        break
                        
                except (json.JSONDecodeError, IOError):
                    continue

def m
ain():
    """Main CLI interface for deployment tracking"""
    
    parser = argparse.ArgumentParser(description="Deployment Status Tracking System")
    parser.add_argument("--project-root", default=".", help="Project root directory")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Create record command
    create_parser = subparsers.add_parser("create", help="Create deployment record")
    create_parser.add_argument("--environment", required=True, choices=["dev", "staging", "prod"])
    create_parser.add_argument("--action", required=True, choices=["deploy", "destroy", "rollback"])
    create_parser.add_argument("--status", required=True, 
                              choices=["started", "success", "failed", "destroyed", "rolled_back"])
    create_parser.add_argument("--commit", help="Git commit SHA")
    create_parser.add_argument("--rollback-version", help="Version being rolled back to")
    create_parser.add_argument("--error", help="Error message for failed deployments")
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Get deployment status")
    status_parser.add_argument("--environment", choices=["dev", "staging", "prod"], 
                              help="Specific environment (default: all)")
    
    # History command
    history_parser = subparsers.add_parser("history", help="Get deployment history")
    history_parser.add_argument("--environment", required=True, choices=["dev", "staging", "prod"])
    history_parser.add_argument("--limit", type=int, default=10, help="Number of records to show")
    
    # Rollback candidates command
    rollback_parser = subparsers.add_parser("rollback-candidates", help="Get rollback candidates")
    rollback_parser.add_argument("--environment", required=True, choices=["dev", "staging", "prod"])
    
    # Report command
    subparsers.add_parser("report", help="Generate comprehensive status report")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    tracker = DeploymentTracker(args.project_root)
    
    if args.command == "create":
        tracker.create_record(
            environment=args.environment,
            action=args.action,
            status=args.status,
            commit_sha=args.commit,
            rollback_version=args.rollback_version,
            error_message=args.error
        )
    
    elif args.command == "status":
        if args.environment:
            status = tracker.get_environment_status(args.environment)
            print(json.dumps(status, indent=2))
        else:
            report = tracker.generate_status_report()
            print(json.dumps(report, indent=2))
    
    elif args.command == "history":
        history = tracker.get_deployment_history(args.environment, args.limit)
        history_data = [asdict(record) for record in history]
        print(json.dumps(history_data, indent=2))
    
    elif args.command == "rollback-candidates":
        candidates = tracker.get_rollback_candidates(args.environment)
        candidates_data = [asdict(record) for record in candidates]
        print(json.dumps(candidates_data, indent=2))
    
    elif args.command == "report":
        report = tracker.generate_status_report()
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()