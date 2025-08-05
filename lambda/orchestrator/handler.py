"""
Lambda orchestrator function for Homebrew Bottles Sync System.

This function handles EventBridge scheduled events, fetches formulas,
estimates download size, and routes to appropriate sync mechanism
(Lambda or ECS) based on size threshold.
"""

import json
import logging
import os
import traceback
from datetime import datetime, timezone
from typing import Dict, Any, Optional

import boto3
from botocore.exceptions import ClientError

# Import shared modules
import sys
sys.path.append('/opt/python')  # Lambda layer path
sys.path.append('.')  # Local development path

from shared.models import SyncConfig, HashFileManager
from shared.homebrew_api import HomebrewAPIClient
from shared.notification_service import NotificationService
from shared.s3_service import S3Service
from shared.monitoring import create_monitoring_manager, SyncPhase


# Initialize monitoring and logging
monitoring = create_monitoring_manager("orchestrator")
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class OrchestrationService:
    """Service for orchestrating the Homebrew bottles sync process."""
    
    def __init__(self):
        """Initialize the orchestration service with AWS clients and configuration."""
        # Get configuration from environment variables
        self.s3_bucket_name = os.environ.get('S3_BUCKET_NAME')
        self.slack_webhook_secret = os.environ.get('SLACK_WEBHOOK_SECRET')
        self.size_threshold_gb = int(os.environ.get('SIZE_THRESHOLD_GB', '20'))
        self.aws_region = os.environ.get('AWS_REGION', 'us-east-1')
        self.ecs_cluster_name = os.environ.get('ECS_CLUSTER_NAME')
        self.ecs_task_definition = os.environ.get('ECS_TASK_DEFINITION')
        self.lambda_sync_function = os.environ.get('LAMBDA_SYNC_FUNCTION')
        
        # Initialize services
        self.s3_service = S3Service(self.s3_bucket_name, self.aws_region) if self.s3_bucket_name else None
        self.notification_service = NotificationService(
            webhook_secret_name=self.slack_webhook_secret,
            aws_region=self.aws_region
        )
        self.homebrew_client = HomebrewAPIClient()
        
        # AWS clients for ECS and Lambda invocation
        self.ecs_client = boto3.client('ecs', region_name=self.aws_region)
        self.lambda_client = boto3.client('lambda', region_name=self.aws_region)
        
        logger.info("OrchestrationService initialized")
    
    def validate_configuration(self) -> None:
        """Validate required configuration parameters."""
        required_vars = [
            ('S3_BUCKET_NAME', self.s3_bucket_name),
            ('ECS_CLUSTER_NAME', self.ecs_cluster_name),
            ('ECS_TASK_DEFINITION', self.ecs_task_definition),
            ('LAMBDA_SYNC_FUNCTION', self.lambda_sync_function)
        ]
        
        missing_vars = [name for name, value in required_vars if not value]
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        # Validate S3 bucket access
        if not self.s3_service.bucket_exists():
            raise ValueError(f"S3 bucket {self.s3_bucket_name} does not exist or is not accessible")
        
        logger.info("Configuration validation passed")
    
    def get_sync_date(self) -> str:
        """Get the current date in YYYY-MM-DD format for sync organization."""
        return datetime.now(timezone.utc).strftime('%Y-%m-%d')
    
    def load_existing_hash_file(self, sync_config: SyncConfig) -> HashFileManager:
        """
        Load existing hash file from S3, external source, or create a new one.
        
        Args:
            sync_config: Sync configuration with external hash file settings
        
        Returns:
            HashFileManager instance with loaded or empty hash data
        """
        hash_manager = HashFileManager(self.s3_service)
        
        try:
            # First, try to load external hash file if configured
            external_loaded = False
            if sync_config.external_hash_file_url or sync_config.external_hash_file_s3_key:
                logger.info("Attempting to load external hash file")
                if hash_manager.load_external_hash_file(sync_config):
                    external_loaded = True
                    logger.info(f"Loaded external hash file with {len(hash_manager.bottles)} bottles")
                    
                    # Validate external hash file
                    if hash_manager.detect_corruption():
                        logger.warning("External hash file corruption detected, will try default hash file")
                        external_loaded = False
                        hash_manager = HashFileManager(self.s3_service)
                else:
                    logger.warning("Failed to load external hash file, will try default hash file")
            
            # If no external file loaded, try default hash file
            if not external_loaded:
                if hash_manager.load_from_s3():
                    logger.info(f"Loaded existing hash file with {len(hash_manager.bottles)} bottles")
                    
                    # Check for corruption
                    if hash_manager.detect_corruption():
                        logger.warning("Hash file corruption detected, creating backup and rebuilding")
                        hash_manager.backup_current_hash_file()
                        
                        # Try to rebuild from S3 metadata
                        if hash_manager.rebuild_from_s3_metadata():
                            logger.info("Successfully rebuilt hash file from S3 metadata")
                        else:
                            logger.warning("Failed to rebuild hash file, starting with empty hash file")
                            hash_manager = HashFileManager(self.s3_service)
                else:
                    logger.info("No existing hash file found, starting with empty hash file")
        
        except Exception as e:
            logger.error(f"Error loading hash file: {e}")
            logger.info("Starting with empty hash file")
            hash_manager = HashFileManager(self.s3_service)
        
        return hash_manager
    
    def fetch_formulas_and_estimate(self) -> tuple:
        """
        Fetch formulas from Homebrew API and estimate download size.
        
        Returns:
            Tuple of (formulas_list, download_estimate, sync_config)
        """
        # Create sync configuration with external hash file support
        sync_config = SyncConfig(
            size_threshold_gb=self.size_threshold_gb,
            s3_bucket_name=self.s3_bucket_name,
            slack_webhook_url=None,  # Will be retrieved from Secrets Manager
            external_hash_file_s3_key=os.environ.get('EXTERNAL_HASH_FILE_S3_KEY'),
            external_hash_file_s3_bucket=os.environ.get('EXTERNAL_HASH_FILE_S3_BUCKET'),
            external_hash_file_url=os.environ.get('EXTERNAL_HASH_FILE_URL')
        )
        sync_config.validate()
        
        logger.info(f"Fetching formulas for platforms: {sync_config.target_platforms}")
        
        # Fetch and process formulas
        formulas, download_estimate = self.homebrew_client.fetch_and_process_formulas(sync_config)
        
        logger.info(f"Found {len(formulas)} formulas with target platform bottles")
        logger.info(f"Estimated download: {download_estimate.total_bottles} bottles, "
                   f"{download_estimate.total_size_gb:.2f} GB")
        
        return formulas, download_estimate, sync_config
    
    def filter_new_bottles(self, formulas, hash_manager: HashFileManager):
        """
        Filter formulas to only include bottles that need to be downloaded.
        
        Args:
            formulas: List of Formula objects
            hash_manager: HashFileManager with existing bottle hashes
            
        Returns:
            Tuple of (filtered_formulas, new_bottles_count, skipped_bottles_count)
        """
        filtered_formulas = []
        new_bottles_count = 0
        skipped_bottles_count = 0
        
        for formula in formulas:
            new_bottles = {}
            
            for platform, bottle in formula.bottles.items():
                if hash_manager.has_bottle(formula, platform, bottle):
                    skipped_bottles_count += 1
                    logger.debug(f"Skipping {formula.name}-{formula.version}-{platform} (already downloaded)")
                else:
                    new_bottles[platform] = bottle
                    new_bottles_count += 1
            
            if new_bottles:
                # Create new formula with only new bottles
                from shared.models import Formula
                filtered_formula = Formula(
                    name=formula.name,
                    version=formula.version,
                    bottles=new_bottles
                )
                filtered_formulas.append(filtered_formula)
        
        logger.info(f"After filtering: {new_bottles_count} new bottles to download, "
                   f"{skipped_bottles_count} bottles skipped")
        
        return filtered_formulas, new_bottles_count, skipped_bottles_count
    
    def trigger_lambda_sync(self, formulas, sync_config: SyncConfig, sync_date: str) -> bool:
        """
        Trigger Lambda sync function for small downloads.
        
        Args:
            formulas: List of Formula objects to sync
            sync_config: Sync configuration
            sync_date: Date string for sync organization
            
        Returns:
            True if Lambda invocation successful, False otherwise
        """
        try:
            payload = {
                'sync_date': sync_date,
                'formulas': [
                    {
                        'name': f.name,
                        'version': f.version,
                        'bottles': {
                            platform: {
                                'url': bottle.url,
                                'sha256': bottle.sha256,
                                'size': bottle.size
                            }
                            for platform, bottle in f.bottles.items()
                        }
                    }
                    for f in formulas
                ],
                'config': sync_config.to_dict()
            }
            
            response = self.lambda_client.invoke(
                FunctionName=self.lambda_sync_function,
                InvocationType='Event',  # Asynchronous invocation
                Payload=json.dumps(payload)
            )
            
            if response['StatusCode'] == 202:
                logger.info(f"Successfully triggered Lambda sync for {len(formulas)} formulas")
                return True
            else:
                logger.error(f"Lambda invocation failed with status code: {response['StatusCode']}")
                return False
                
        except ClientError as e:
            logger.error(f"Failed to invoke Lambda sync function: {e}")
            return False
    
    def trigger_ecs_sync(self, formulas, sync_config: SyncConfig, sync_date: str) -> bool:
        """
        Trigger ECS task for large downloads.
        
        Args:
            formulas: List of Formula objects to sync
            sync_config: Sync configuration
            sync_date: Date string for sync organization
            
        Returns:
            True if ECS task started successfully, False otherwise
        """
        try:
            # Prepare environment variables for ECS task
            environment = [
                {'name': 'SYNC_DATE', 'value': sync_date},
                {'name': 'S3_BUCKET_NAME', 'value': self.s3_bucket_name},
                {'name': 'SLACK_WEBHOOK_SECRET', 'value': self.slack_webhook_secret or ''},
                {'name': 'AWS_REGION', 'value': self.aws_region},
                {'name': 'FORMULAS_JSON', 'value': json.dumps([
                    {
                        'name': f.name,
                        'version': f.version,
                        'bottles': {
                            platform: {
                                'url': bottle.url,
                                'sha256': bottle.sha256,
                                'size': bottle.size
                            }
                            for platform, bottle in f.bottles.items()
                        }
                    }
                    for f in formulas
                ])},
                {'name': 'CONFIG_JSON', 'value': json.dumps(sync_config.to_dict())}
            ]
            
            # Run ECS task
            response = self.ecs_client.run_task(
                cluster=self.ecs_cluster_name,
                taskDefinition=self.ecs_task_definition,
                launchType='FARGATE',
                networkConfiguration={
                    'awsvpcConfiguration': {
                        'subnets': os.environ.get('ECS_SUBNETS', '').split(','),
                        'securityGroups': os.environ.get('ECS_SECURITY_GROUPS', '').split(','),
                        'assignPublicIp': 'ENABLED'
                    }
                },
                overrides={
                    'containerOverrides': [
                        {
                            'name': 'homebrew-sync',
                            'environment': environment
                        }
                    ]
                }
            )
            
            if response['tasks']:
                task_arn = response['tasks'][0]['taskArn']
                logger.info(f"Successfully started ECS task: {task_arn}")
                return True
            else:
                logger.error("ECS task creation failed - no tasks returned")
                return False
                
        except ClientError as e:
            logger.error(f"Failed to start ECS task: {e}")
            return False
    
    def handle_scheduled_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle EventBridge scheduled event to orchestrate the sync process.
        
        Args:
            event: EventBridge event data
            
        Returns:
            Response dictionary with status and details
        """
        sync_date = self.get_sync_date()
        
        with monitoring.track_operation("orchestration", {"sync_date": sync_date}):
            try:
                monitoring.logger.info(f"Starting Homebrew bottles sync orchestration for {sync_date}",
                                     sync_date=sync_date, operation="orchestration_start")
                
                # Add X-Ray annotations
                monitoring.tracer.add_annotation("sync_date", sync_date)
                monitoring.tracer.add_annotation("component", "orchestrator")
                
                # Validate configuration
                with monitoring.track_operation("configuration_validation"):
                    self.validate_configuration()
                
                # Fetch formulas and estimate download size
                with monitoring.track_operation("formula_fetch"):
                    formulas, download_estimate, sync_config = self.fetch_formulas_and_estimate()
                    monitoring.record_sync_progress(0, download_estimate.total_bottles, 0, SyncPhase.FORMULA_FETCH)
                
                # Load existing hash file (now that we have sync_config)
                with monitoring.track_operation("hash_file_loading"):
                    hash_manager = self.load_existing_hash_file(sync_config)
                    monitoring.record_sync_progress(0, 0, 0, SyncPhase.HASH_LOADING)
                
                # Filter out bottles that are already downloaded
                with monitoring.track_operation("download_planning"):
                    filtered_formulas, new_bottles_count, skipped_bottles_count = self.filter_new_bottles(
                        formulas, hash_manager
                    )
                    monitoring.record_sync_progress(0, new_bottles_count, 0, SyncPhase.DOWNLOAD_PLANNING)
                
                # If no new bottles to download, send notification and exit
                if not filtered_formulas:
                    monitoring.logger.info("No new bottles to download", 
                                         skipped_bottles=skipped_bottles_count,
                                         operation="no_new_bottles")
                    
                    self.notification_service.send_sync_success(
                        new_bottles=0,
                        total_size="0 MB",
                        duration="< 1 minute",
                        skipped_bottles=skipped_bottles_count
                    )
                    
                    # Record completion metrics
                    monitoring.record_sync_progress(0, 0, 0, SyncPhase.CLEANUP)
                    
                    return {
                        'statusCode': 200,
                        'body': json.dumps({
                            'message': 'No new bottles to download',
                            'skipped_bottles': skipped_bottles_count
                        })
                    }
                
                # Re-estimate download size for filtered formulas
                filtered_estimate = self.homebrew_client.estimate_download_size(
                    filtered_formulas, sync_config.target_platforms
                )
                
                # Add metadata to trace
                monitoring.tracer.add_metadata("sync_stats", {
                    "new_bottles": new_bottles_count,
                    "skipped_bottles": skipped_bottles_count,
                    "estimated_size_gb": filtered_estimate.total_size_gb,
                    "total_formulas": len(filtered_formulas)
                })
                
                # Send initial notification
                size_str = f"{filtered_estimate.total_size_gb:.2f} GB"
                if filtered_estimate.total_size_gb < 1:
                    size_str = f"{filtered_estimate.total_size_mb:.1f} MB"
                
                self.notification_service.send_sync_start(
                    date=sync_date,
                    estimated_bottles=new_bottles_count,
                    estimated_size=size_str
                )
                
                # Decide routing based on size threshold
                use_ecs = self.homebrew_client.should_use_ecs(filtered_estimate, sync_config.size_threshold_gb)
                sync_method = "ECS" if use_ecs else "Lambda"
                
                monitoring.tracer.add_annotation("sync_method", sync_method)
                monitoring.tracer.add_annotation("estimated_size_gb", filtered_estimate.total_size_gb)
                
                # Route to appropriate sync mechanism
                with monitoring.track_operation(f"trigger_{sync_method.lower()}_sync"):
                    if use_ecs:
                        monitoring.logger.info(f"Routing to ECS for large download ({filtered_estimate.total_size_gb:.2f} GB)",
                                             sync_method="ECS", estimated_size_gb=filtered_estimate.total_size_gb)
                        success = self.trigger_ecs_sync(filtered_formulas, sync_config, sync_date)
                    else:
                        monitoring.logger.info(f"Routing to Lambda for small download ({filtered_estimate.total_size_gb:.2f} GB)",
                                             sync_method="Lambda", estimated_size_gb=filtered_estimate.total_size_gb)
                        success = self.trigger_lambda_sync(filtered_formulas, sync_config, sync_date)
                
                if success:
                    monitoring.logger.info(f"Successfully triggered {sync_method} sync",
                                         sync_method=sync_method, success=True)
                    
                    # Record successful orchestration metrics
                    if monitoring.metrics:
                        monitoring.metrics.put_metric("OrchestrationSuccess", 1, "Count", {
                            "SyncMethod": sync_method,
                            "EstimatedSizeGB": str(int(filtered_estimate.total_size_gb))
                        })
                    
                    return {
                        'statusCode': 200,
                        'body': json.dumps({
                            'message': f'Sync orchestration successful - routed to {sync_method}',
                            'sync_date': sync_date,
                            'new_bottles': new_bottles_count,
                            'skipped_bottles': skipped_bottles_count,
                            'estimated_size_gb': filtered_estimate.total_size_gb,
                            'sync_method': sync_method
                        })
                    }
                else:
                    error_msg = f"Failed to trigger {sync_method} sync"
                    monitoring.logger.error(error_msg, sync_method=sync_method, success=False)
                    
                    self.notification_service.send_sync_failure(
                        error_message=error_msg,
                        error_details=f"Orchestrator failed to start {sync_method} sync process"
                    )
                    
                    return {
                        'statusCode': 500,
                        'body': json.dumps({
                            'error': error_msg,
                            'sync_date': sync_date
                        })
                    }
                    
            except Exception as e:
                error_msg = f"Orchestration failed: {str(e)}"
                error_details = traceback.format_exc()
                
                monitoring.logger.error(error_msg, 
                                      error_details=error_details,
                                      exception_type=type(e).__name__)
                
                # Send failure notification
                self.notification_service.send_sync_failure(
                    error_message=error_msg,
                    error_details=error_details
                )
                
                return {
                    'statusCode': 500,
                    'body': json.dumps({
                        'error': error_msg,
                        'sync_date': sync_date
                    })
                }


def lambda_handler(event, context):
    """
    AWS Lambda handler function for EventBridge scheduled events.
    
    Args:
        event: EventBridge event data
        context: Lambda context object
        
    Returns:
        Response dictionary with status and details
    """
    logger.info(f"Received event: {json.dumps(event, default=str)}")
    
    # Initialize orchestration service
    orchestrator = OrchestrationService()
    
    # Handle the scheduled event
    return orchestrator.handle_scheduled_event(event)