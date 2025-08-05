"""
S3 storage service for the Homebrew Bottles Sync System.

This module provides S3 operations for uploading, downloading, and managing
bottles and hash files with atomic update functionality.
"""

import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from shared.models import HashFileManager
from shared.error_handling import (
    RetryHandler, RetryConfig, ErrorClassifier, CloudWatchMetrics,
    ErrorContext, ErrorType, create_structured_logger
)


logger = create_structured_logger(__name__)


class S3Service:
    """Service for S3 operations including upload, download, and bucket management."""
    
    def __init__(self, bucket_name: str, region_name: str = 'us-east-1', 
                 enable_metrics: bool = True, retry_config: Optional[RetryConfig] = None):
        """
        Initialize S3 service.
        
        Args:
            bucket_name: Name of the S3 bucket
            region_name: AWS region name
            enable_metrics: Whether to enable CloudWatch metrics
            retry_config: Optional retry configuration
        """
        self.bucket_name = bucket_name
        self.region_name = region_name
        self._s3_client = None
        
        # Initialize error handling components
        self.metrics = CloudWatchMetrics(region=region_name) if enable_metrics else None
        self.retry_config = retry_config or RetryConfig(max_attempts=3, base_delay=1.0, max_delay=30.0)
        self.retry_handler = RetryHandler(self.retry_config, self.metrics)
        self.error_classifier = ErrorClassifier()
    
    @property
    def s3_client(self):
        """Lazy initialization of S3 client."""
        if self._s3_client is None:
            try:
                self._s3_client = boto3.client('s3', region_name=self.region_name)
            except NoCredentialsError:
                logger.error("AWS credentials not found")
                raise
        return self._s3_client
    
    def bucket_exists(self) -> bool:
        """
        Check if the S3 bucket exists and is accessible.
        
        Returns:
            True if bucket exists and is accessible, False otherwise
        """
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            return True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                logger.warning(f"Bucket {self.bucket_name} does not exist")
            elif error_code == '403':
                logger.warning(f"Access denied to bucket {self.bucket_name}")
            else:
                logger.error(f"Error checking bucket {self.bucket_name}: {e}")
            return False
    
    def upload_file(self, file_path: str, s3_key: str, metadata: Optional[Dict[str, str]] = None) -> bool:
        """
        Upload a file to S3 with retry logic.
        
        Args:
            file_path: Local path to the file to upload
            s3_key: S3 key (path) for the uploaded file
            metadata: Optional metadata to attach to the object
            
        Returns:
            True if upload successful, False otherwise
        """
        def _upload():
            extra_args = {}
            if metadata:
                extra_args['Metadata'] = metadata
            
            self.s3_client.upload_file(
                file_path, 
                self.bucket_name, 
                s3_key,
                ExtraArgs=extra_args
            )
            return True
        
        try:
            result = self.retry_handler.retry_sync(_upload)
            logger.info(f"Successfully uploaded {file_path} to s3://{self.bucket_name}/{s3_key}")
            
            # Send success metric
            if self.metrics:
                self.metrics.put_metric('S3Upload', 1, 'Count', {'Operation': 'upload_file'})
            
            return result
            
        except FileNotFoundError:
            logger.error(f"File not found: {file_path}")
            if self.metrics:
                self.metrics.put_error_metric(
                    self.error_classifier.classify_error(FileNotFoundError(f"File not found: {file_path}"), "upload_file")
                )
            return False
        except Exception as e:
            logger.error(f"Failed to upload {file_path} to S3: {e}")
            if self.metrics:
                self.metrics.put_error_metric(
                    self.error_classifier.classify_error(e, "upload_file")
                )
            return False
    
    def download_file(self, s3_key: str, file_path: str) -> bool:
        """
        Download a file from S3 with retry logic.
        
        Args:
            s3_key: S3 key (path) of the file to download
            file_path: Local path where the file will be saved
            
        Returns:
            True if download successful, False otherwise
        """
        def _download():
            self.s3_client.download_file(self.bucket_name, s3_key, file_path)
            return True
        
        try:
            result = self.retry_handler.retry_sync(_download)
            logger.info(f"Successfully downloaded s3://{self.bucket_name}/{s3_key} to {file_path}")
            
            # Send success metric
            if self.metrics:
                self.metrics.put_metric('S3Download', 1, 'Count', {'Operation': 'download_file'})
            
            return result
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                logger.warning(f"File not found in S3: s3://{self.bucket_name}/{s3_key}")
            else:
                logger.error(f"Failed to download from S3: {e}")
                if self.metrics:
                    self.metrics.put_error_metric(
                        self.error_classifier.classify_error(e, "download_file")
                    )
            return False
        except Exception as e:
            logger.error(f"Failed to download {s3_key} from S3: {e}")
            if self.metrics:
                self.metrics.put_error_metric(
                    self.error_classifier.classify_error(e, "download_file")
                )
            return False
    
    def object_exists(self, s3_key: str) -> bool:
        """
        Check if an object exists in S3.
        
        Args:
            s3_key: S3 key (path) to check
            
        Returns:
            True if object exists, False otherwise
        """
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
            return True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                return False
            else:
                logger.error(f"Error checking object existence: {e}")
                return False
    
    def get_object_metadata(self, s3_key: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for an S3 object.
        
        Args:
            s3_key: S3 key (path) of the object
            
        Returns:
            Dictionary containing object metadata, or None if object doesn't exist
        """
        try:
            response = self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
            return {
                'size': response.get('ContentLength'),
                'last_modified': response.get('LastModified'),
                'etag': response.get('ETag', '').strip('"'),
                'metadata': response.get('Metadata', {})
            }
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                logger.debug(f"Object not found: s3://{self.bucket_name}/{s3_key}")
            else:
                logger.error(f"Error getting object metadata: {e}")
            return None
    
    def upload_json(self, data: Dict[str, Any], s3_key: str, metadata: Optional[Dict[str, str]] = None) -> bool:
        """
        Upload JSON data directly to S3 with retry logic.
        
        Args:
            data: Dictionary to upload as JSON
            s3_key: S3 key (path) for the uploaded file
            metadata: Optional metadata to attach to the object
            
        Returns:
            True if upload successful, False otherwise
        """
        def _upload_json():
            json_data = json.dumps(data, indent=2, ensure_ascii=False)
            
            extra_args = {
                'ContentType': 'application/json'
            }
            if metadata:
                extra_args['Metadata'] = metadata
            
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=json_data.encode('utf-8'),
                **extra_args
            )
            return True
        
        try:
            result = self.retry_handler.retry_sync(_upload_json)
            logger.info(f"Successfully uploaded JSON to s3://{self.bucket_name}/{s3_key}")
            
            # Send success metric
            if self.metrics:
                self.metrics.put_metric('S3Upload', 1, 'Count', {'Operation': 'upload_json'})
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to upload JSON to S3: {e}")
            if self.metrics:
                self.metrics.put_error_metric(
                    self.error_classifier.classify_error(e, "upload_json")
                )
            return False
    
    def download_json(self, s3_key: str) -> Optional[Dict[str, Any]]:
        """
        Download and parse JSON data from S3 with retry logic.
        
        Args:
            s3_key: S3 key (path) of the JSON file to download
            
        Returns:
            Parsed JSON data as dictionary, or None if download/parse failed
        """
        def _download_json():
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
            json_data = response['Body'].read().decode('utf-8')
            return json.loads(json_data)
        
        try:
            result = self.retry_handler.retry_sync(_download_json)
            
            # Send success metric
            if self.metrics:
                self.metrics.put_metric('S3Download', 1, 'Count', {'Operation': 'download_json'})
            
            return result
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                logger.debug(f"JSON file not found in S3: s3://{self.bucket_name}/{s3_key}")
            else:
                logger.error(f"Failed to download JSON from S3: {e}")
                if self.metrics:
                    self.metrics.put_error_metric(
                        self.error_classifier.classify_error(e, "download_json")
                    )
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from S3: {e}")
            if self.metrics:
                self.metrics.put_error_metric(
                    self.error_classifier.classify_error(e, "download_json")
                )
            return None
        except Exception as e:
            logger.error(f"Failed to download/parse JSON from S3: {e}")
            if self.metrics:
                self.metrics.put_error_metric(
                    self.error_classifier.classify_error(e, "download_json")
                )
            return None
    
    def delete_object(self, s3_key: str) -> bool:
        """
        Delete an object from S3.
        
        Args:
            s3_key: S3 key (path) of the object to delete
            
        Returns:
            True if deletion successful, False otherwise
        """
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            logger.info(f"Successfully deleted s3://{self.bucket_name}/{s3_key}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to delete object from S3: {e}")
            return False
    
    def list_objects(self, prefix: str = "", max_keys: int = 1000) -> list:
        """
        List objects in S3 bucket with optional prefix filter.
        
        Args:
            prefix: Prefix to filter objects
            max_keys: Maximum number of objects to return
            
        Returns:
            List of object information dictionaries
        """
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
                MaxKeys=max_keys
            )
            
            objects = []
            for obj in response.get('Contents', []):
                objects.append({
                    'key': obj['Key'],
                    'size': obj['Size'],
                    'last_modified': obj['LastModified'],
                    'etag': obj['ETag'].strip('"')
                })
            
            return objects
            
        except ClientError as e:
            logger.error(f"Failed to list objects in S3: {e}")
            return []