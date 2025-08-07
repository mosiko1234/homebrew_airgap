#!/usr/bin/env python3
"""
Comprehensive deployment monitoring system that integrates health checks,
smoke tests, and deployment tracking for complete post-deployment verification.
"""

import argparse
import json
import os
import sys
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.deployment_tracker import DeploymentTracker
from scripts.notify_deployment import NotificationManager


class DeploymentMonitor:
    """Comprehensive deployment monitoring and verification system"""
    
    def __init__(self, environment: str, project_root: str = "."):
        self.environment = environment
        self.project_root = Path(project_root)
        self.scripts_dir = self.project_root / "scripts"
        
        # Initialize components
        self.deployment_tracker = DeploymentTracker(project_root)
        self.notification_manager = NotificationManager()
        
        # Configuration
        self.health_check_timeout = 300  # 5 minutes
        self.smoke_test_timeout = 600    # 10 minutes
        
    def run_post_deployment_monitoring(self, commit_sha: str = None, 
                                     skip_health_checks: bool = False,
                                     skip_smoke_tests: bool = False) -> Dict:
        """Run complete post-deployment monitoring workflow"""
        
        print(f"🔍 Starting post-deployment monitoring for {self.environment}")
        
        start_time = time.time()
        results = {
            "environment": self.environment,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "commit_sha": commit_sha,
            "overall_success": False,
            "duration_seconds": 0,
            "health_checks": {},
            "smoke_tests": {},
            "deployment_metrics": {},
            "notifications_sent": []
        }
        
        try:
            # Step 1: Run health checks
            if not skip_health_checks:
                print("📊 Running health checks...")
                health_results = self._run_health_checks()
                results["health_checks"] = health_results
                
                if not health_results.get("overall_healthy", False):
                    print("❌ Health checks failed - stopping monitoring")
                    self._send_failure_notification(
                        "Health checks failed", 
                        commit_sha, 
                        health_results.get("summary", {})
                    )
                    return results
                else:
                    print("✅ Health checks passed")
            
            # Step 2: Run smoke tests
            if not skip_smoke_tests:
                print("🧪 Running smoke tests...")
                smoke_results = self._run_smoke_tests()
                results["smoke_tests"] = smoke_results
                
                if not smoke_results.get("overall_success", False):
                    print("❌ Smoke tests failed - deployment may have issues")
                    self._send_failure_notification(
                        "Smoke tests failed", 
                        commit_sha, 
                        smoke_results.get("summary", {})
                    )
                    return results
                else:
                    print("✅ Smoke tests passed")
            
            # Step 3: Update deployment tracking
            print("📝 Updating deployment tracking...")
            duration_seconds = int(time.time() - start_time)
            
            self.deployment_tracker.create_record(
                environment=self.environment,
                action="deploy",
                status="success",
                commit_sha=commit_sha,
                duration_seconds=duration_seconds
            )
            
            # Step 4: Get deployment metrics
            metrics = self.deployment_tracker.get_deployment_metrics(self.environment)
            results["deployment_metrics"] = metrics
            
            # Step 5: Send success notification
            print("📢 Sending success notification...")
            self._send_success_notification(commit_sha, duration_seconds, results)
            
            results["overall_success"] = True
            results["duration_seconds"] = duration_seconds
            
            print(f"✅ Post-deployment monitoring completed successfully in {duration_seconds}s")
            
        except Exception as e:
            duration_seconds = int(time.time() - start_time)
            results["duration_seconds"] = duration_seconds
            results["error"] = str(e)
            
            print(f"❌ Post-deployment monitoring failed: {e}")
            
            # Record failed deployment
            self.deployment_tracker.create_record(
                environment=self.environment,
                action="deploy",
                status="failed",
                commit_sha=commit_sha,
                duration_seconds=duration_seconds,
                error_message=str(e)
            )
            
            # Send failure notification
            self._send_failure_notification("Monitoring failed", commit_sha, {"error": str(e)})
        
        return results
    
    def _run_health_checks(self) -> Dict:
        """Run deployment health checks"""
        
        health_check_script = self.scripts_dir / "deployment-health-check.py"
        
        if not health_check_script.exists():
            return {
                "error": "Health check script not found",
                "overall_healthy": False
            }
        
        try:
            # Run health check script
            cmd = [
                sys.executable, str(health_check_script),
                "--environment", self.environment,
                "--output-format", "json"
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.health_check_timeout,
                cwd=self.project_root
            )
            
            if result.returncode == 0:
                return json.loads(result.stdout)
            else:
                # Parse partial results if available
                try:
                    partial_results = json.loads(result.stdout)
                    partial_results["overall_healthy"] = False
                    return partial_results
                except json.JSONDecodeError:
                    return {
                        "error": f"Health checks failed: {result.stderr}",
                        "overall_healthy": False,
                        "exit_code": result.returncode
                    }
                    
        except subprocess.TimeoutExpired:
            return {
                "error": f"Health checks timed out after {self.health_check_timeout}s",
                "overall_healthy": False
            }
        except Exception as e:
            return {
                "error": f"Health check execution failed: {e}",
                "overall_healthy": False
            }
    
    def _run_smoke_tests(self) -> Dict:
        """Run deployment smoke tests"""
        
        smoke_test_script = self.project_root / "tests" / "smoke" / "test_deployment.py"
        
        if not smoke_test_script.exists():
            return {
                "error": "Smoke test script not found",
                "overall_success": False
            }
        
        try:
            # Run smoke test script
            cmd = [
                sys.executable, str(smoke_test_script),
                "--environment", self.environment,
                "--output-format", "json"
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.smoke_test_timeout,
                cwd=self.project_root
            )
            
            if result.returncode == 0:
                return json.loads(result.stdout)
            else:
                # Parse partial results if available
                try:
                    partial_results = json.loads(result.stdout)
                    partial_results["overall_success"] = False
                    return partial_results
                except json.JSONDecodeError:
                    return {
                        "error": f"Smoke tests failed: {result.stderr}",
                        "overall_success": False,
                        "exit_code": result.returncode
                    }
                    
        except subprocess.TimeoutExpired:
            return {
                "error": f"Smoke tests timed out after {self.smoke_test_timeout}s",
                "overall_success": False
            }
        except Exception as e:
            return {
                "error": f"Smoke test execution failed: {e}",
                "overall_success": False
            }
    
    def _send_success_notification(self, commit_sha: str, duration_seconds: int, results: Dict):
        """Send success notification with detailed results"""
        
        details = {
            "duration": duration_seconds,
            "health_checks_passed": results.get("health_checks", {}).get("summary", {}).get("passed", 0),
            "smoke_tests_passed": results.get("smoke_tests", {}).get("summary", {}).get("passed", 0),
            "deployment_metrics": results.get("deployment_metrics", {})
        }
        
        success = self.notification_manager.send_deployment_notification(
            self.environment,
            "success",
            commit_sha or "unknown",
            details
        )
        
        if success:
            results["notifications_sent"].append("success_notification")
    
    def _send_failure_notification(self, reason: str, commit_sha: str, details: Dict):
        """Send failure notification with error details"""
        
        failure_details = {
            "reason": reason,
            "details": details
        }
        
        success = self.notification_manager.send_deployment_notification(
            self.environment,
            "failure",
            commit_sha or "unknown",
            failure_details
        )
        
        return success
    
    def generate_monitoring_report(self, days: int = 7) -> Dict:
        """Generate comprehensive monitoring report"""
        
        print(f"📊 Generating monitoring report for {self.environment} ({days} days)")
        
        # Get deployment metrics
        metrics = self.deployment_tracker.get_deployment_metrics(self.environment, days)
        
        # Get recent deployment history
        history = self.deployment_tracker.get_deployment_history(self.environment, limit=20)
        
        # Calculate additional metrics
        recent_deployments = [
            record for record in history
            if datetime.fromisoformat(record.timestamp.replace('Z', '+00:00')) > 
               datetime.utcnow() - timedelta(days=days)
        ]
        
        # Deployment frequency
        deployment_frequency = len(recent_deployments) / days if days > 0 else 0
        
        # Mean time to recovery (MTTR) - time between failed and successful deployment
        mttr_hours = self._calculate_mttr(recent_deployments)
        
        # Change failure rate
        change_failure_rate = self._calculate_change_failure_rate(recent_deployments)
        
        report = {
            "environment": self.environment,
            "report_period_days": days,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "metrics": metrics,
            "dora_metrics": {
                "deployment_frequency_per_day": round(deployment_frequency, 2),
                "change_failure_rate_percent": round(change_failure_rate, 1),
                "mean_time_to_recovery_hours": round(mttr_hours, 1) if mttr_hours else None
            },
            "recent_deployments": [
                {
                    "timestamp": record.timestamp,
                    "status": record.status,
                    "action": record.action,
                    "commit_sha": record.commit_sha[:8],
                    "user": record.user,
                    "duration_seconds": record.duration_seconds
                }
                for record in recent_deployments[:10]  # Last 10 deployments
            ],
            "recommendations": self._generate_recommendations(metrics, recent_deployments)
        }
        
        return report
    
    def _calculate_mttr(self, deployments: List) -> Optional[float]:
        """Calculate Mean Time To Recovery in hours"""
        
        recovery_times = []
        
        for i, deployment in enumerate(deployments[:-1]):  # Skip last one
            if deployment.status == "failed":
                # Look for next successful deployment
                for next_deployment in deployments[i+1:]:
                    if next_deployment.status == "success":
                        failed_time = datetime.fromisoformat(deployment.timestamp.replace('Z', '+00:00'))
                        success_time = datetime.fromisoformat(next_deployment.timestamp.replace('Z', '+00:00'))
                        recovery_time = (success_time - failed_time).total_seconds() / 3600  # Convert to hours
                        recovery_times.append(recovery_time)
                        break
        
        return sum(recovery_times) / len(recovery_times) if recovery_times else None
    
    def _calculate_change_failure_rate(self, deployments: List) -> float:
        """Calculate change failure rate as percentage"""
        
        if not deployments:
            return 0.0
        
        deploy_actions = [d for d in deployments if d.action == "deploy"]
        if not deploy_actions:
            return 0.0
        
        failed_deploys = [d for d in deploy_actions if d.status == "failed"]
        
        return (len(failed_deploys) / len(deploy_actions)) * 100
    
    def _generate_recommendations(self, metrics: Dict, deployments: List) -> List[str]:
        """Generate recommendations based on metrics"""
        
        recommendations = []
        
        # Success rate recommendations
        success_rate = metrics.get("success_rate", 0)
        if success_rate < 90:
            recommendations.append(
                f"Success rate is {success_rate}% - consider improving testing and validation"
            )
        elif success_rate < 95:
            recommendations.append(
                f"Success rate is {success_rate}% - good but could be improved"
            )
        
        # Deployment frequency recommendations
        total_deployments = metrics.get("total_deployments", 0)
        period_days = metrics.get("period_days", 30)
        
        if total_deployments == 0:
            recommendations.append("No deployments in the reporting period")
        elif total_deployments / period_days < 0.1:  # Less than 1 deployment per 10 days
            recommendations.append("Low deployment frequency - consider more frequent releases")
        
        # Duration recommendations
        avg_duration = metrics.get("average_duration_seconds", 0)
        if avg_duration > 1800:  # 30 minutes
            recommendations.append(
                f"Average deployment time is {avg_duration/60:.1f} minutes - consider optimization"
            )
        
        # Recent failures
        recent_failures = [d for d in deployments[:5] if d.status == "failed"]
        if recent_failures:
            recommendations.append(
                f"{len(recent_failures)} recent failures detected - investigate root causes"
            )
        
        if not recommendations:
            recommendations.append("All metrics look healthy - keep up the good work!")
        
        return recommendations
    
    def run_continuous_monitoring(self, interval_minutes: int = 60, max_iterations: int = None):
        """Run continuous monitoring at specified intervals"""
        
        print(f"🔄 Starting continuous monitoring for {self.environment}")
        print(f"   Interval: {interval_minutes} minutes")
        if max_iterations:
            print(f"   Max iterations: {max_iterations}")
        
        iteration = 0
        
        try:
            while True:
                iteration += 1
                print(f"\n--- Monitoring iteration {iteration} ---")
                
                # Run health checks only (no smoke tests for continuous monitoring)
                health_results = self._run_health_checks()
                
                if not health_results.get("overall_healthy", False):
                    print("⚠️  Health check issues detected")
                    
                    # Send alert for continuous monitoring issues
                    self._send_failure_notification(
                        "Continuous monitoring detected issues",
                        "continuous-monitoring",
                        health_results.get("summary", {})
                    )
                else:
                    print("✅ System healthy")
                
                # Check if we should stop
                if max_iterations and iteration >= max_iterations:
                    print(f"Completed {max_iterations} iterations")
                    break
                
                # Wait for next iteration
                print(f"⏰ Waiting {interval_minutes} minutes until next check...")
                time.sleep(interval_minutes * 60)
                
        except KeyboardInterrupt:
            print(f"\n🛑 Continuous monitoring stopped after {iteration} iterations")
        except Exception as e:
            print(f"\n❌ Continuous monitoring failed: {e}")
            raise


def main():
    """Main CLI interface for deployment monitoring"""
    
    parser = argparse.ArgumentParser(description="Comprehensive deployment monitoring system")
    parser.add_argument("--environment", required=True,
                       choices=["dev", "staging", "prod"],
                       help="Environment to monitor")
    parser.add_argument("--commit", help="Git commit SHA for deployment tracking")
    parser.add_argument("--project-root", default=".", help="Project root directory")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Post-deployment monitoring command
    monitor_parser = subparsers.add_parser("post-deploy", help="Run post-deployment monitoring")
    monitor_parser.add_argument("--skip-health-checks", action="store_true",
                               help="Skip health checks")
    monitor_parser.add_argument("--skip-smoke-tests", action="store_true",
                               help="Skip smoke tests")
    monitor_parser.add_argument("--output-format", choices=["text", "json"], default="text",
                               help="Output format")
    
    # Continuous monitoring command
    continuous_parser = subparsers.add_parser("continuous", help="Run continuous monitoring")
    continuous_parser.add_argument("--interval", type=int, default=60,
                                  help="Monitoring interval in minutes (default: 60)")
    continuous_parser.add_argument("--max-iterations", type=int,
                                  help="Maximum iterations (default: unlimited)")
    
    # Report generation command
    report_parser = subparsers.add_parser("report", help="Generate monitoring report")
    report_parser.add_argument("--days", type=int, default=7,
                              help="Report period in days (default: 7)")
    report_parser.add_argument("--output-format", choices=["text", "json"], default="text",
                              help="Output format")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Initialize monitor
    monitor = DeploymentMonitor(args.environment, args.project_root)
    
    try:
        if args.command == "post-deploy":
            results = monitor.run_post_deployment_monitoring(
                commit_sha=args.commit,
                skip_health_checks=args.skip_health_checks,
                skip_smoke_tests=args.skip_smoke_tests
            )
            
            if args.output_format == "json":
                print(json.dumps(results, indent=2))
            else:
                print(f"\n📊 Post-deployment monitoring results:")
                print(f"Environment: {results['environment']}")
                print(f"Overall Success: {'✅' if results['overall_success'] else '❌'}")
                print(f"Duration: {results['duration_seconds']}s")
                
                if results.get('health_checks'):
                    hc = results['health_checks']
                    print(f"Health Checks: {hc.get('summary', {}).get('passed', 0)} passed, "
                          f"{hc.get('summary', {}).get('failed', 0)} failed")
                
                if results.get('smoke_tests'):
                    st = results['smoke_tests']
                    print(f"Smoke Tests: {st.get('summary', {}).get('passed', 0)} passed, "
                          f"{st.get('summary', {}).get('failed', 0)} failed")
            
            sys.exit(0 if results['overall_success'] else 1)
        
        elif args.command == "continuous":
            monitor.run_continuous_monitoring(
                interval_minutes=args.interval,
                max_iterations=args.max_iterations
            )
        
        elif args.command == "report":
            report = monitor.generate_monitoring_report(args.days)
            
            if args.output_format == "json":
                print(json.dumps(report, indent=2))
            else:
                print(f"\n📊 Monitoring Report - {report['environment'].upper()}")
                print(f"Period: {report['report_period_days']} days")
                print(f"Generated: {report['generated_at']}")
                
                metrics = report['metrics']
                print(f"\n📈 Deployment Metrics:")
                print(f"  Total Deployments: {metrics['total_deployments']}")
                print(f"  Success Rate: {metrics['success_rate']}%")
                print(f"  Average Duration: {metrics['average_duration_seconds']}s")
                
                dora = report['dora_metrics']
                print(f"\n🎯 DORA Metrics:")
                print(f"  Deployment Frequency: {dora['deployment_frequency_per_day']}/day")
                print(f"  Change Failure Rate: {dora['change_failure_rate_percent']}%")
                if dora['mean_time_to_recovery_hours']:
                    print(f"  Mean Time to Recovery: {dora['mean_time_to_recovery_hours']}h")
                
                print(f"\n💡 Recommendations:")
                for rec in report['recommendations']:
                    print(f"  • {rec}")
    
    except KeyboardInterrupt:
        print("\n🛑 Monitoring interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Monitoring failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()