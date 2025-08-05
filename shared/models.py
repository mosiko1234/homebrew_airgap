"""
Core data models for the Homebrew Bottles Sync System.

This module defines the data classes used throughout the system for
representing formulas, bottles, hash entries, and configuration.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime, timezone
import json
import re


@dataclass
class BottleInfo:
    """Information about a specific bottle for a formula."""
    url: str
    sha256: str
    size: int
    
    def validate(self) -> None:
        """Validate bottle information."""
        if not self.url:
            raise ValueError("Bottle URL cannot be empty")
        
        if not self.url.startswith(('http://', 'https://')):
            raise ValueError("Bottle URL must be a valid HTTP/HTTPS URL")
        
        if not self.sha256:
            raise ValueError("SHA256 hash cannot be empty")
        
        if not re.match(r'^[a-fA-F0-9]{64}$', self.sha256):
            raise ValueError("SHA256 hash must be 64 hexadecimal characters")
        
        if self.size <= 0:
            raise ValueError("Bottle size must be positive")


@dataclass
class Formula:
    """Represents a Homebrew formula with its bottles."""
    name: str
    version: str
    bottles: Dict[str, BottleInfo] = field(default_factory=dict)
    
    def validate(self) -> None:
        """Validate formula data."""
        if not self.name:
            raise ValueError("Formula name cannot be empty")
        
        if not re.match(r'^[a-zA-Z0-9_-]+$', self.name):
            raise ValueError("Formula name must contain only alphanumeric characters, hyphens, and underscores")
        
        if not self.version:
            raise ValueError("Formula version cannot be empty")
        
        # Validate all bottles
        for platform, bottle in self.bottles.items():
            if not platform:
                raise ValueError("Platform name cannot be empty")
            bottle.validate()
    
    def get_target_bottles(self, target_platforms: List[str]) -> Dict[str, BottleInfo]:
        """Get bottles for specified target platforms."""
        return {
            platform: bottle 
            for platform, bottle in self.bottles.items() 
            if platform in target_platforms
        }


@dataclass
class HashEntry:
    """Represents an entry in the bottles hash file."""
    formula_name: str
    version: str
    platform: str
    sha256: str
    download_date: str
    file_size: int
    
    def validate(self) -> None:
        """Validate hash entry data."""
        if not self.formula_name:
            raise ValueError("Formula name cannot be empty")
        
        if not self.version:
            raise ValueError("Version cannot be empty")
        
        if not self.platform:
            raise ValueError("Platform cannot be empty")
        
        if not self.sha256:
            raise ValueError("SHA256 hash cannot be empty")
        
        if not re.match(r'^[a-fA-F0-9]{64}$', self.sha256):
            raise ValueError("SHA256 hash must be 64 hexadecimal characters")
        
        if not self.download_date:
            raise ValueError("Download date cannot be empty")
        
        # Validate date format (YYYY-MM-DD)
        try:
            datetime.strptime(self.download_date, '%Y-%m-%d')
        except ValueError:
            raise ValueError("Download date must be in YYYY-MM-DD format")
        
        if self.file_size <= 0:
            raise ValueError("File size must be positive")
    
    def to_dict(self) -> Dict:
        """Convert hash entry to dictionary for JSON serialization."""
        return {
            "sha256": self.sha256,
            "download_date": self.download_date,
            "file_size": self.file_size
        }
    
    @classmethod
    def from_dict(cls, formula_name: str, version: str, platform: str, data: Dict) -> 'HashEntry':
        """Create HashEntry from dictionary data."""
        return cls(
            formula_name=formula_name,
            version=version,
            platform=platform,
            sha256=data["sha256"],
            download_date=data["download_date"],
            file_size=data["file_size"]
        )


@dataclass
class SyncConfig:
    """Configuration for the sync process."""
    target_platforms: List[str] = field(default_factory=lambda: ["arm64_sonoma", "arm64_ventura", "monterey"])
    size_threshold_gb: int = 20
    max_concurrent_downloads: int = 10
    retry_attempts: int = 3
    slack_webhook_url: Optional[str] = None
    s3_bucket_name: Optional[str] = None
    external_hash_file_s3_key: Optional[str] = None
    external_hash_file_s3_bucket: Optional[str] = None
    external_hash_file_url: Optional[str] = None
    
    def validate(self) -> None:
        """Validate sync configuration."""
        if not self.target_platforms:
            raise ValueError("Target platforms list cannot be empty")
        
        for platform in self.target_platforms:
            if not platform:
                raise ValueError("Platform name cannot be empty")
        
        if self.size_threshold_gb <= 0:
            raise ValueError("Size threshold must be positive")
        
        if self.max_concurrent_downloads <= 0:
            raise ValueError("Max concurrent downloads must be positive")
        
        if self.retry_attempts < 0:
            raise ValueError("Retry attempts cannot be negative")
        
        if self.slack_webhook_url and not self.slack_webhook_url.startswith('https://'):
            raise ValueError("Slack webhook URL must be HTTPS")
        
        # Validate external hash file configuration
        external_sources = [
            self.external_hash_file_s3_key,
            self.external_hash_file_url
        ]
        if sum(1 for source in external_sources if source) > 1:
            raise ValueError("Only one external hash file source can be specified")
        
        if self.external_hash_file_s3_key and not self.external_hash_file_s3_key.endswith('.json'):
            raise ValueError("External hash file S3 key must end with .json")
        
        if self.external_hash_file_url and not self.external_hash_file_url.startswith('https://'):
            raise ValueError("External hash file URL must be HTTPS")
    
    def to_dict(self) -> Dict:
        """Convert config to dictionary for JSON serialization."""
        return {
            "target_platforms": self.target_platforms,
            "size_threshold_gb": self.size_threshold_gb,
            "max_concurrent_downloads": self.max_concurrent_downloads,
            "retry_attempts": self.retry_attempts,
            "slack_webhook_url": self.slack_webhook_url,
            "s3_bucket_name": self.s3_bucket_name,
            "external_hash_file_s3_key": self.external_hash_file_s3_key,
            "external_hash_file_s3_bucket": self.external_hash_file_s3_bucket,
            "external_hash_file_url": self.external_hash_file_url
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'SyncConfig':
        """Create SyncConfig from dictionary data."""
        return cls(
            target_platforms=data.get("target_platforms", ["arm64_sonoma", "arm64_ventura", "monterey"]),
            size_threshold_gb=data.get("size_threshold_gb", 20),
            max_concurrent_downloads=data.get("max_concurrent_downloads", 10),
            retry_attempts=data.get("retry_attempts", 3),
            slack_webhook_url=data.get("slack_webhook_url"),
            s3_bucket_name=data.get("s3_bucket_name"),
            external_hash_file_s3_key=data.get("external_hash_file_s3_key"),
            external_hash_file_s3_bucket=data.get("external_hash_file_s3_bucket"),
            external_hash_file_url=data.get("external_hash_file_url")
        )


class HashFileManager:
    """Manages the bottles hash file operations with atomic updates."""
    
    HASH_FILE_KEY = "bottles_hash.json"
    TEMP_HASH_FILE_KEY = "bottles_hash.json.tmp"
    
    def __init__(self, s3_service=None):
        """
        Initialize HashFileManager.
        
        Args:
            s3_service: Optional S3Service instance for remote operations
        """
        self.bottles: Dict[str, HashEntry] = {}
        self.last_updated: Optional[str] = None
        self.s3_service = s3_service
    
    def load_from_dict(self, data: Dict) -> None:
        """Load hash data from dictionary."""
        self.last_updated = data.get("last_updated")
        self.bottles = {}
        
        bottles_data = data.get("bottles", {})
        for bottle_key, bottle_data in bottles_data.items():
            # Parse bottle key format: "formula-version-platform"
            parts = bottle_key.rsplit('-', 1)
            if len(parts) != 2:
                continue
            
            formula_version, platform = parts
            # Split formula and version (version is after the last hyphen in formula_version)
            formula_parts = formula_version.rsplit('-', 1)
            if len(formula_parts) != 2:
                continue
            
            formula_name, version = formula_parts
            
            hash_entry = HashEntry.from_dict(formula_name, version, platform, bottle_data)
            hash_entry.validate()
            self.bottles[bottle_key] = hash_entry
    
    def to_dict(self) -> Dict:
        """Convert hash file to dictionary for JSON serialization."""
        return {
            "last_updated": self.last_updated or datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            "bottles": {
                key: entry.to_dict() 
                for key, entry in self.bottles.items()
            }
        }
    
    def add_bottle(self, formula: Formula, platform: str, bottle: BottleInfo, download_date: str) -> None:
        """Add a bottle to the hash file."""
        bottle_key = f"{formula.name}-{formula.version}-{platform}"
        hash_entry = HashEntry(
            formula_name=formula.name,
            version=formula.version,
            platform=platform,
            sha256=bottle.sha256,
            download_date=download_date,
            file_size=bottle.size
        )
        hash_entry.validate()
        self.bottles[bottle_key] = hash_entry
    
    def has_bottle(self, formula: Formula, platform: str, bottle: BottleInfo) -> bool:
        """Check if a bottle already exists in the hash file."""
        bottle_key = f"{formula.name}-{formula.version}-{platform}"
        if bottle_key not in self.bottles:
            return False
        
        existing_entry = self.bottles[bottle_key]
        return existing_entry.sha256 == bottle.sha256
    
    def validate(self) -> None:
        """Validate the entire hash file."""
        for entry in self.bottles.values():
            entry.validate()
    
    def load_from_url(self, url: str) -> bool:
        """
        Load hash file from external URL.
        
        Args:
            url: HTTPS URL to download hash file from
            
        Returns:
            True if loaded successfully, False otherwise
        """
        try:
            import requests
            
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            self.load_from_dict(data)
            
            import logging
            logging.info(f"Successfully loaded external hash file from URL: {url}")
            return True
            
        except requests.exceptions.RequestException as e:
            import logging
            logging.warning(f"Failed to download hash file from URL {url}: {e}")
            return False
        except (ValueError, KeyError) as e:
            import logging
            logging.warning(f"Failed to parse hash file from URL {url}: {e}")
            return False
    
    def load_external_hash_file(self, sync_config: 'SyncConfig') -> bool:
        """
        Load external hash file based on sync configuration.
        
        Args:
            sync_config: SyncConfig with external hash file settings
            
        Returns:
            True if external hash file loaded successfully, False otherwise
        """
        if sync_config.external_hash_file_url:
            return self.load_from_url(sync_config.external_hash_file_url)
        elif sync_config.external_hash_file_s3_key:
            return self.load_from_s3(
                external_key=sync_config.external_hash_file_s3_key,
                external_bucket=sync_config.external_hash_file_s3_bucket
            )
        return False
    
    def load_from_s3(self, external_key: Optional[str] = None, external_bucket: Optional[str] = None) -> bool:
        """
        Load hash file from S3.
        
        Args:
            external_key: Optional external hash file key to load from
            external_bucket: Optional external bucket name (if different from default)
            
        Returns:
            True if loaded successfully, False if file doesn't exist or failed to load
        """
        if not self.s3_service:
            raise ValueError("S3 service not configured")
        
        # Try external source first if specified
        if external_key:
            if external_bucket and external_bucket != self.s3_service.bucket_name:
                # Load from external bucket
                from shared.s3_service import S3Service
                external_s3_service = S3Service(external_bucket, self.s3_service.region_name)
                data = external_s3_service.download_json(external_key)
            else:
                # Load from same bucket with external key
                data = self.s3_service.download_json(external_key)
            
            if data is not None:
                try:
                    self.load_from_dict(data)
                    import logging
                    logging.info(f"Successfully loaded external hash file from {external_bucket or self.s3_service.bucket_name}/{external_key}")
                    return True
                except (ValueError, KeyError) as e:
                    import logging
                    logging.warning(f"Failed to parse external hash file from {external_bucket or self.s3_service.bucket_name}/{external_key}: {e}")
        
        # Fall back to default hash file
        data = self.s3_service.download_json(self.HASH_FILE_KEY)
        if data is not None:
            try:
                self.load_from_dict(data)
                return True
            except (ValueError, KeyError) as e:
                import logging
                logging.warning(f"Failed to parse default hash file: {e}")
        
        return False    
   
 def validate_external_hash_file(self, data: Dict) -> tuple[bool, List[str]]:
        """
        Validate external hash file format and content.
        
        Args:
            data: Dictionary containing hash file data
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        try:
            # Check required top-level fields
            if "bottles" not in data:
                errors.append("Missing 'bottles' field")
            
            if "last_updated" not in data:
                errors.append("Missing 'last_updated' field")
            elif data["last_updated"]:
                # Validate timestamp format
                try:
                    datetime.fromisoformat(data["last_updated"].replace('Z', '+00:00'))
                except ValueError:
                    errors.append(f"Invalid timestamp format: {data['last_updated']}")
            
            # Validate bottles structure
            bottles_data = data.get("bottles", {})
            if not isinstance(bottles_data, dict):
                errors.append("'bottles' field must be a dictionary")
            else:
                for bottle_key, bottle_data in bottles_data.items():
                    if not isinstance(bottle_data, dict):
                        errors.append(f"Bottle data for '{bottle_key}' must be a dictionary")
                        continue
                    
                    # Check required bottle fields
                    required_fields = ["sha256", "download_date", "file_size"]
                    for field in required_fields:
                        if field not in bottle_data:
                            errors.append(f"Missing '{field}' in bottle '{bottle_key}'")
                    
                    # Validate SHA256 format
                    sha256 = bottle_data.get("sha256", "")
                    if sha256 and not re.match(r'^[a-fA-F0-9]{64}$', sha256):
                        errors.append(f"Invalid SHA256 format in bottle '{bottle_key}': {sha256}")
                    
                    # Validate date format
                    download_date = bottle_data.get("download_date", "")
                    if download_date:
                        try:
                            datetime.strptime(download_date, '%Y-%m-%d')
                        except ValueError:
                            errors.append(f"Invalid date format in bottle '{bottle_key}': {download_date}")
                    
                    # Validate file size
                    file_size = bottle_data.get("file_size")
                    if file_size is not None and (not isinstance(file_size, int) or file_size <= 0):
                        errors.append(f"Invalid file size in bottle '{bottle_key}': {file_size}")
                    
                    # Validate bottle key format
                    if not re.match(r'^[a-zA-Z0-9_-]+-[a-zA-Z0-9._-]+-[a-zA-Z0-9_]+$', bottle_key):
                        errors.append(f"Invalid bottle key format: {bottle_key}")
        
        except Exception as e:
            errors.append(f"Unexpected error during validation: {str(e)}")
        
        return len(errors) == 0, errors
    
    def migrate_external_hash_file(self, external_data: Dict) -> Dict:
        """
        Migrate external hash file to current format if needed.
        
        Args:
            external_data: External hash file data
            
        Returns:
            Migrated hash file data
        """
        migrated_data = external_data.copy()
        
        # Ensure last_updated field exists
        if "last_updated" not in migrated_data or not migrated_data["last_updated"]:
            migrated_data["last_updated"] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        
        # Ensure bottles field exists
        if "bottles" not in migrated_data:
            migrated_data["bottles"] = {}
        
        # Migrate bottle entries if needed
        bottles = migrated_data["bottles"]
        migrated_bottles = {}
        
        for bottle_key, bottle_data in bottles.items():
            if isinstance(bottle_data, dict):
                migrated_bottle = bottle_data.copy()
                
                # Ensure all required fields exist with defaults
                if "sha256" not in migrated_bottle:
                    migrated_bottle["sha256"] = "unknown"
                
                if "download_date" not in migrated_bottle:
                    # Use current date as fallback
                    migrated_bottle["download_date"] = datetime.now(timezone.utc).strftime('%Y-%m-%d')
                
                if "file_size" not in migrated_bottle:
                    migrated_bottle["file_size"] = 0
                
                # Normalize bottle key format if needed
                normalized_key = self._normalize_bottle_key(bottle_key)
                migrated_bottles[normalized_key] = migrated_bottle
            else:
                # Skip invalid bottle entries
                import logging
                logging.warning(f"Skipping invalid bottle entry: {bottle_key}")
        
        migrated_data["bottles"] = migrated_bottles
        return migrated_data
    
    def _normalize_bottle_key(self, bottle_key: str) -> str:
        """
        Normalize bottle key to standard format: formula-version-platform
        
        Args:
            bottle_key: Original bottle key
            
        Returns:
            Normalized bottle key
        """
        # Handle various possible formats
        # Standard format: formula-version-platform
        if re.match(r'^[a-zA-Z0-9_-]+-[a-zA-Z0-9._-]+-[a-zA-Z0-9_]+$', bottle_key):
            return bottle_key
        
        # Try to parse and reconstruct
        parts = bottle_key.split('-')
        if len(parts) >= 3:
            # Assume last part is platform, second-to-last is version, rest is formula
            platform = parts[-1]
            version = parts[-2]
            formula = '-'.join(parts[:-2])
            return f"{formula}-{version}-{platform}"
        
        # Return as-is if can't normalize
        return bottle_key
    
    def merge_with_external_hash_file(self, external_data: Dict) -> int:
        """
        Merge external hash file data with current hash file.
        External entries take precedence over existing ones.
        
        Args:
            external_data: External hash file data to merge
            
        Returns:
            Number of bottles merged from external source
        """
        merged_count = 0
        
        # Validate and migrate external data
        is_valid, errors = self.validate_external_hash_file(external_data)
        if not is_valid:
            import logging
            logging.warning(f"External hash file validation failed: {errors}")
            # Try to migrate anyway
            external_data = self.migrate_external_hash_file(external_data)
        
        # Merge bottles
        external_bottles = external_data.get("bottles", {})
        for bottle_key, bottle_data in external_bottles.items():
            try:
                # Parse bottle key
                parts = bottle_key.rsplit('-', 1)
                if len(parts) != 2:
                    continue
                
                formula_version, platform = parts
                formula_parts = formula_version.rsplit('-', 1)
                if len(formula_parts) != 2:
                    continue
                
                formula_name, version = formula_parts
                
                # Create hash entry
                hash_entry = HashEntry.from_dict(formula_name, version, platform, bottle_data)
                hash_entry.validate()
                
                # Add to current hash file (overwrites existing)
                self.bottles[bottle_key] = hash_entry
                merged_count += 1
                
            except (ValueError, KeyError) as e:
                import logging
                logging.warning(f"Failed to merge bottle {bottle_key}: {e}")
                continue
        
        # Update timestamp if we merged anything
        if merged_count > 0:
            self.last_updated = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        
        return merged_count
    
    def save_to_s3_atomic(self) -> bool:
        """
        Save hash file to S3 using atomic update (write to temp file, then rename).
        
        Returns:
            True if saved successfully, False otherwise
        """
        if not self.s3_service:
            raise ValueError("S3 service not configured")
        
        try:
            # Update timestamp
            self.last_updated = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            
            # First, upload to temporary key
            data = self.to_dict()
            if not self.s3_service.upload_json(data, self.TEMP_HASH_FILE_KEY):
                return False
            
            # Verify the temporary file was uploaded correctly
            temp_data = self.s3_service.download_json(self.TEMP_HASH_FILE_KEY)
            if temp_data is None:
                return False
            
            # Verify data integrity
            if temp_data.get("last_updated") != self.last_updated:
                return False
            
            # Copy temp file to final location (atomic operation in S3)
            if not self._copy_s3_object(self.TEMP_HASH_FILE_KEY, self.HASH_FILE_KEY):
                return False
            
            # Clean up temporary file
            self.s3_service.delete_object(self.TEMP_HASH_FILE_KEY)
            
            return True
            
        except Exception as e:
            import logging
            logging.error(f"Failed to save hash file atomically: {e}")
            # Clean up temporary file on error
            self.s3_service.delete_object(self.TEMP_HASH_FILE_KEY)
            return False
    
    def _copy_s3_object(self, source_key: str, dest_key: str) -> bool:
        """
        Copy an S3 object from source to destination key.
        
        Args:
            source_key: Source S3 key
            dest_key: Destination S3 key
            
        Returns:
            True if copy successful, False otherwise
        """
        try:
            copy_source = {
                'Bucket': self.s3_service.bucket_name,
                'Key': source_key
            }
            self.s3_service.s3_client.copy_object(
                CopySource=copy_source,
                Bucket=self.s3_service.bucket_name,
                Key=dest_key
            )
            return True
        except Exception as e:
            import logging
            logging.error(f"Failed to copy S3 object from {source_key} to {dest_key}: {e}")
            return False
    
    def backup_current_hash_file(self) -> bool:
        """
        Create a backup of the current hash file with timestamp.
        
        Returns:
            True if backup created successfully, False otherwise
        """
        if not self.s3_service:
            raise ValueError("S3 service not configured")
        
        if not self.s3_service.object_exists(self.HASH_FILE_KEY):
            return True  # No file to backup
        
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        backup_key = f"backups/bottles_hash_{timestamp}.json"
        
        return self._copy_s3_object(self.HASH_FILE_KEY, backup_key)
    
    def detect_corruption(self) -> bool:
        """
        Detect if the hash file is corrupted by validating its structure and data.
        
        Returns:
            True if corruption detected, False if file is valid
        """
        try:
            self.validate()
            
            # Additional corruption checks
            if not self.last_updated:
                import logging
                logging.warning("Hash file missing last_updated timestamp")
                return True
            
            # Check if last_updated is a valid ISO timestamp
            try:
                datetime.fromisoformat(self.last_updated.replace('Z', '+00:00'))
            except ValueError:
                import logging
                logging.warning(f"Hash file has invalid timestamp format: {self.last_updated}")
                return True
            
            # Check for duplicate bottle keys
            bottle_keys = list(self.bottles.keys())
            if len(bottle_keys) != len(set(bottle_keys)):
                import logging
                logging.warning("Hash file contains duplicate bottle keys")
                return True
            
            # Check for inconsistent data
            for key, entry in self.bottles.items():
                expected_key = f"{entry.formula_name}-{entry.version}-{entry.platform}"
                if key != expected_key:
                    import logging
                    logging.warning(f"Hash file key mismatch: {key} != {expected_key}")
                    return True
            
            # Check for reasonable file sizes (bottles should be > 0 and < 10GB)
            for entry in self.bottles.values():
                if entry.file_size <= 0 or entry.file_size > 10 * 1024 * 1024 * 1024:
                    import logging
                    logging.warning(f"Hash file contains unreasonable file size: {entry.file_size}")
                    return True
            
            # Check for reasonable dates (not in future, not too old)
            current_date = datetime.now(timezone.utc).date()
            for entry in self.bottles.values():
                try:
                    entry_date = datetime.strptime(entry.download_date, '%Y-%m-%d').date()
                    if entry_date > current_date:
                        import logging
                        logging.warning(f"Hash file contains future date: {entry.download_date}")
                        return True
                    
                    # Check if date is more than 2 years old (might indicate corruption)
                    days_old = (current_date - entry_date).days
                    if days_old > 730:  # 2 years
                        import logging
                        logging.warning(f"Hash file contains very old date: {entry.download_date} ({days_old} days old)")
                        # Don't return True here as old dates might be legitimate
                        
                except ValueError:
                    import logging
                    logging.warning(f"Hash file contains invalid date format: {entry.download_date}")
                    return True
            
            return False
            
        except (ValueError, KeyError) as e:
            import logging
            logging.warning(f"Hash file validation failed: {e}")
            return True
    
    def rebuild_from_s3_metadata(self) -> bool:
        """
        Rebuild hash file from S3 object metadata (emergency recovery).
        This is a fallback method when the hash file is corrupted.
        
        Returns:
            True if rebuild successful, False otherwise
        """
        if not self.s3_service:
            raise ValueError("S3 service not configured")
        
        try:
            # Clear current data
            self.bottles = {}
            self.last_updated = None
            
            # List all bottle files in S3
            objects = self.s3_service.list_objects(prefix="", max_keys=10000)
            
            for obj in objects:
                key = obj['key']
                
                # Skip non-bottle files
                if not key.endswith('.bottle.tar.gz'):
                    continue
                
                # Extract date from path (YYYY-MM-DD format)
                path_parts = key.split('/')
                if len(path_parts) < 2:
                    continue
                
                date_folder = path_parts[0]
                filename = path_parts[-1]
                
                # Validate date format
                try:
                    datetime.strptime(date_folder, '%Y-%m-%d')
                except ValueError:
                    continue
                
                # Parse filename to extract formula info
                # Expected format: formula-version.platform.bottle.tar.gz
                if not filename.endswith('.bottle.tar.gz'):
                    continue
                
                base_name = filename[:-len('.bottle.tar.gz')]
                parts = base_name.split('.')
                if len(parts) < 2:
                    continue
                
                platform = parts[-1]
                formula_version = '.'.join(parts[:-1])
                
                # Split formula and version
                formula_parts = formula_version.rsplit('-', 1)
                if len(formula_parts) != 2:
                    continue
                
                formula_name, version = formula_parts
                
                # Get object metadata for SHA and size
                metadata = self.s3_service.get_object_metadata(key)
                if not metadata:
                    continue
                
                # Create hash entry (without SHA validation since we don't have the original)
                bottle_key = f"{formula_name}-{version}-{platform}"
                hash_entry = HashEntry(
                    formula_name=formula_name,
                    version=version,
                    platform=platform,
                    sha256="unknown",  # Will need to be updated when bottles are re-validated
                    download_date=date_folder,
                    file_size=metadata['size']
                )
                
                self.bottles[bottle_key] = hash_entry
            
            # Set last updated timestamp
            self.last_updated = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            
            return True
            
        except Exception as e:
            import logging
            logging.error(f"Failed to rebuild hash file from S3 metadata: {e}")
            return False