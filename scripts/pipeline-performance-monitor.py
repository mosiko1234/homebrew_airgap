#!/usr/bin/env python3
"""
Pipeline Performance Monitor

Tracks and reports CI/CD pipeline performance metrics including:
- Build times
- Cache hit rates
- Resource usage
- Deployment efficiency
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import argparse
import requests
from dataclasses import dataclass, asdict


@dataclass
class PipelineMetrics:
    """Pipeline performance metrics"""
    pipeline_id: str
    commit_sha: str
    branch: str
    trigger_event: str
    start_time: datetime
    end_time: Optional[datetime] = None
    total_duration: Optional[int] = None
    
    # Stage durations (in seconds)
    validation_duration: Optional[int] = None
    test_duration: Optional[int] = None
    build_duration: Optional[int] = None
    deploy_duration: Optional[int] = None
    
    # Cache metrics
    cache_hits: int = 0
    cache_misses: int = 0
    cache_hit_rate: float = 0.0
    
    # Resource metrics
    parallel_jobs: int = 1
    skipped_stages: List[str] = None
    
    # Deployment metrics
    environments_deployed: List[str] = None
    changes_detected: Dict[str, bool] = None
    
    def __post_init__(self):
        if self.skipped_stages is None:
            self.skipped_stages = []
        if self.environments_deployed is None:
            self.environments_deployed = []
        if self.changes_detected is None:
            self.changes_detected = {}


class PipelinePerformanceMonitor:
    """Monitor and track pipeline performance"""
    
    def __init__(self, github_token: Optional[str] = None):
        self.github_token = github_token or os.getenv('GITHUB_TOKEN')
        self.repo = os.getenv('GITHUB_REPOSITORY', 'unknown/unknown')
        self.metrics_file = 'pipeline-metrics.json'
        
    def start_tracking(self, pipeline_id: str, commit_sha: str, branch: str, trigger_event: str) -> PipelineMetrics:
        """Start tracking a new pipeline run"""
        metrics = PipelineMetrics(
            pipeline_id=pipeline_id,
            commit_sha=commit_sha,
            branch=branch,
            trigger_event=trigger_event,
            start_time=datetime.utcnow()
        )
        
        print(f"🚀 Started tracking pipeline {pipeline_id}")
        print(f"   Commit: {commit_sha}")
        print(f"   Branch: {branch}")
        print(f"   Trigger: {trigger_event}")
        
        return metrics
    
    def record_stage_duration(self, metrics: PipelineMetrics, stage: str, duration: int):
        """Record duration for a specific stage"""
        if stage == 'validation':
            metrics.validation_duration = duration
        elif stage == 'test':
            metrics.test_duration = duration
        elif stage == 'build':
            metrics.build_duration = duration
        elif stage == 'deploy':
            metrics.deploy_duration = duration
        
        print(f"📊 {stage.title()} stage completed in {duration}s")
    
    def record_cache_metrics(self, metrics: PipelineMetrics, hits: int, misses: int):
        """Record cache hit/miss metrics"""
        metrics.cache_hits = hits
        metrics.cache_misses = misses
        total = hits + misses
        metrics.cache_hit_rate = (hits / total * 100) if total > 0 else 0
        
        print(f"💾 Cache metrics: {hits} hits, {misses} misses ({metrics.cache_hit_rate:.1f}% hit rate)")
    
    def record_skipped_stage(self, metrics: PipelineMetrics, stage: str, reason: str):
        """Record a skipped stage"""
        metrics.skipped_stages.append(f"{stage}: {reason}")
        print(f"⏭️ Skipped {stage}: {reason}")
    
    def record_deployment(self, metrics: PipelineMetrics, environment: str, changes_applied: bool):
        """Record deployment information"""
        metrics.environments_deployed.append(environment)
        metrics.changes_detected[environment] = changes_applied
        
        status = "with changes" if changes_applied else "no changes"
        print(f"🌍 Deployed to {environment} ({status})")
    
    def finish_tracking(self, metrics: PipelineMetrics, success: bool = True):
        """Finish tracking and calculate final metrics"""
        metrics.end_time = datetime.utcnow()
        metrics.total_duration = int((metrics.end_time - metrics.start_time).total_seconds())
        
        # Save metrics
        self._save_metrics(metrics)
        
        # Generate report
        self._generate_report(metrics, success)
        
        return metrics
    
    def _save_metrics(self, metrics: PipelineMetrics):
        """Save metrics to file"""
        try:
            # Load existing metrics
            existing_metrics = []
            if os.path.exists(self.metrics_file):
                with open(self.metrics_file, 'r') as f:
                    existing_metrics = json.load(f)
            
            # Add new metrics
            metrics_dict = asdict(metrics)
            # Convert datetime objects to strings
            metrics_dict['start_time'] = metrics.start_time.isoformat()
            if metrics.end_time:
                metrics_dict['end_time'] = metrics.end_time.isoformat()
            
            existing_metrics.append(metrics_dict)
            
            # Keep only last 100 runs
            existing_metrics = existing_metrics[-100:]
            
            # Save updated metrics
            with open(self.metrics_file, 'w') as f:
                json.dump(existing_metrics, f, indent=2)
                
        except Exception as e:
            print(f"⚠️ Failed to save metrics: {e}")
    
    def _generate_report(self, metrics: PipelineMetrics, success: bool):
        """Generate performance report"""
        print("\n" + "="*60)
        print("📈 PIPELINE PERFORMANCE REPORT")
        print("="*60)
        
        # Basic info
        print(f"Pipeline ID: {metrics.pipeline_id}")
        print(f"Commit: {metrics.commit_sha}")
        print(f"Branch: {metrics.branch}")
        print(f"Trigger: {metrics.trigger_event}")
        print(f"Status: {'✅ SUCCESS' if success else '❌ FAILED'}")
        print(f"Total Duration: {metrics.total_duration}s ({metrics.total_duration/60:.1f}m)")
        
        # Stage breakdown
        print("\n🔍 Stage Breakdown:")
        stages = [
            ('Validation', metrics.validation_duration),
            ('Testing', metrics.test_duration),
            ('Build', metrics.build_duration),
            ('Deployment', metrics.deploy_duration)
        ]
        
        for stage_name, duration in stages:
            if duration:
                percentage = (duration / metrics.total_duration * 100) if metrics.total_duration > 0 else 0
                print(f"  {stage_name}: {duration}s ({percentage:.1f}%)")
            else:
                print(f"  {stage_name}: Not executed")
        
        # Optimization metrics
        print(f"\n⚡ Optimizations:")
        print(f"  Cache Hit Rate: {metrics.cache_hit_rate:.1f}%")
        print(f"  Parallel Jobs: {metrics.parallel_jobs}")
        print(f"  Skipped Stages: {len(metrics.skipped_stages)}")
        
        if metrics.skipped_stages:
            for skipped in metrics.skipped_stages:
                print(f"    - {skipped}")
        
        # Deployment info
        if metrics.environments_deployed:
            print(f"\n🌍 Deployments:")
            for env in metrics.environments_deployed:
                changes = metrics.changes_detected.get(env, False)
                status = "changes applied" if changes else "no changes"
                print(f"  {env}: {status}")
        
        # Performance insights
        self._generate_insights(metrics)
    
    def _generate_insights(self, metrics: PipelineMetrics):
        """Generate performance insights and recommendations"""
        print(f"\n💡 Performance Insights:")
        
        insights = []
        
        # Cache performance
        if metrics.cache_hit_rate < 50:
            insights.append("🔄 Low cache hit rate - consider optimizing cache keys")
        elif metrics.cache_hit_rate > 90:
            insights.append("✅ Excellent cache performance")
        
        # Stage duration analysis
        if metrics.test_duration and metrics.test_duration > 300:  # 5 minutes
            insights.append("🧪 Test stage is slow - consider parallel execution")
        
        if metrics.build_duration and metrics.build_duration > 600:  # 10 minutes
            insights.append("🔨 Build stage is slow - check Docker layer caching")
        
        # Skipped stages efficiency
        if len(metrics.skipped_stages) > 0:
            insights.append(f"⚡ Efficiently skipped {len(metrics.skipped_stages)} unnecessary stages")
        
        # Total duration assessment
        if metrics.total_duration and metrics.total_duration < 300:  # 5 minutes
            insights.append("🚀 Excellent pipeline performance!")
        elif metrics.total_duration and metrics.total_duration > 1800:  # 30 minutes
            insights.append("🐌 Pipeline is slow - review optimization opportunities")
        
        if not insights:
            insights.append("📊 Pipeline performance is within normal ranges")
        
        for insight in insights:
            print(f"  {insight}")
    
    def get_historical_metrics(self, days: int = 30) -> List[Dict]:
        """Get historical metrics for analysis"""
        if not os.path.exists(self.metrics_file):
            return []
        
        try:
            with open(self.metrics_file, 'r') as f:
                all_metrics = json.load(f)
            
            # Filter by date
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            recent_metrics = []
            
            for metric in all_metrics:
                start_time = datetime.fromisoformat(metric['start_time'])
                if start_time >= cutoff_date:
                    recent_metrics.append(metric)
            
            return recent_metrics
            
        except Exception as e:
            print(f"⚠️ Failed to load historical metrics: {e}")
            return []
    
    def generate_trend_report(self, days: int = 30):
        """Generate trend analysis report"""
        metrics = self.get_historical_metrics(days)
        
        if not metrics:
            print("📊 No historical data available for trend analysis")
            return
        
        print(f"\n📈 PIPELINE TRENDS ({days} days)")
        print("="*50)
        
        # Calculate averages
        total_runs = len(metrics)
        avg_duration = sum(m.get('total_duration', 0) for m in metrics) / total_runs
        avg_cache_hit_rate = sum(m.get('cache_hit_rate', 0) for m in metrics) / total_runs
        
        # Count successes (assuming success if end_time exists)
        successful_runs = sum(1 for m in metrics if m.get('end_time'))
        success_rate = (successful_runs / total_runs * 100) if total_runs > 0 else 0
        
        print(f"Total Runs: {total_runs}")
        print(f"Success Rate: {success_rate:.1f}%")
        print(f"Average Duration: {avg_duration:.0f}s ({avg_duration/60:.1f}m)")
        print(f"Average Cache Hit Rate: {avg_cache_hit_rate:.1f}%")
        
        # Identify trends
        if total_runs >= 5:
            recent_5 = metrics[-5:]
            older_5 = metrics[-10:-5] if len(metrics) >= 10 else metrics[:-5]
            
            if older_5:
                recent_avg = sum(m.get('total_duration', 0) for m in recent_5) / len(recent_5)
                older_avg = sum(m.get('total_duration', 0) for m in older_5) / len(older_5)
                
                if recent_avg < older_avg * 0.9:
                    print("📈 Trend: Pipeline performance is improving!")
                elif recent_avg > older_avg * 1.1:
                    print("📉 Trend: Pipeline performance is degrading")
                else:
                    print("📊 Trend: Pipeline performance is stable")


def main():
    parser = argparse.ArgumentParser(description='Pipeline Performance Monitor')
    parser.add_argument('--action', choices=['start', 'stage', 'cache', 'skip', 'deploy', 'finish', 'report'], 
                       required=True, help='Action to perform')
    parser.add_argument('--pipeline-id', help='Pipeline run ID')
    parser.add_argument('--commit-sha', help='Commit SHA')
    parser.add_argument('--branch', help='Branch name')
    parser.add_argument('--trigger', help='Trigger event')
    parser.add_argument('--stage', help='Stage name')
    parser.add_argument('--duration', type=int, help='Duration in seconds')
    parser.add_argument('--cache-hits', type=int, help='Cache hits')
    parser.add_argument('--cache-misses', type=int, help='Cache misses')
    parser.add_argument('--reason', help='Reason for skipping')
    parser.add_argument('--environment', help='Deployment environment')
    parser.add_argument('--changes-applied', action='store_true', help='Whether changes were applied')
    parser.add_argument('--success', action='store_true', help='Whether pipeline succeeded')
    parser.add_argument('--days', type=int, default=30, help='Days for trend analysis')
    
    args = parser.parse_args()
    
    monitor = PipelinePerformanceMonitor()
    
    if args.action == 'start':
        if not all([args.pipeline_id, args.commit_sha, args.branch, args.trigger]):
            print("❌ Missing required arguments for start action")
            sys.exit(1)
        
        metrics = monitor.start_tracking(args.pipeline_id, args.commit_sha, args.branch, args.trigger)
        
        # Save initial metrics
        with open('current-pipeline-metrics.json', 'w') as f:
            metrics_dict = asdict(metrics)
            metrics_dict['start_time'] = metrics.start_time.isoformat()
            json.dump(metrics_dict, f, indent=2)
    
    elif args.action == 'stage':
        if not all([args.stage, args.duration]):
            print("❌ Missing required arguments for stage action")
            sys.exit(1)
        
        # Load current metrics
        try:
            with open('current-pipeline-metrics.json', 'r') as f:
                metrics_dict = json.load(f)
            
            metrics = PipelineMetrics(**{k: v for k, v in metrics_dict.items() if k != 'start_time'})
            metrics.start_time = datetime.fromisoformat(metrics_dict['start_time'])
            
            monitor.record_stage_duration(metrics, args.stage, args.duration)
            
            # Save updated metrics
            with open('current-pipeline-metrics.json', 'w') as f:
                metrics_dict = asdict(metrics)
                metrics_dict['start_time'] = metrics.start_time.isoformat()
                json.dump(metrics_dict, f, indent=2)
                
        except Exception as e:
            print(f"❌ Failed to load current metrics: {e}")
            sys.exit(1)
    
    elif args.action == 'report':
        monitor.generate_trend_report(args.days)
    
    else:
        print(f"❌ Action '{args.action}' not fully implemented yet")
        sys.exit(1)


if __name__ == '__main__':
    main()