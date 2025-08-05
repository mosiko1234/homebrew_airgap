"""
Homebrew API client for fetching and processing formula data.

This module provides functionality to interact with the Homebrew API,
fetch formula data, and process it for the sync system.
"""

import requests
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from models import Formula, BottleInfo, SyncConfig
from error_handling import (
    RetryHandler, RetryConfig, ErrorClassifier, CloudWatchMetrics,
    create_structured_logger
)


@dataclass
class DownloadEstimate:
    """Represents download size estimation results."""
    total_bottles: int
    total_size_bytes: int
    total_size_gb: float
    formulas_with_bottles: int
    
    @property
    def total_size_mb(self) -> float:
        """Get total size in MB."""
        return self.total_size_bytes / (1024 * 1024)


class HomebrewAPIClient:
    """Client for interacting with the Homebrew API."""
    
    DEFAULT_API_URL = "https://formulae.brew.sh/api/formula.json"
    DEFAULT_TIMEOUT = 30
    DEFAULT_RETRY_ATTEMPTS = 3
    
    def __init__(self, 
                 api_url: str = DEFAULT_API_URL,
                 timeout: int = DEFAULT_TIMEOUT,
                 retry_attempts: int = DEFAULT_RETRY_ATTEMPTS,
                 enable_metrics: bool = True):
        """
        Initialize the Homebrew API client.
        
        Args:
            api_url: URL to the Homebrew formula API
            timeout: Request timeout in seconds
            retry_attempts: Number of retry attempts for failed requests
            enable_metrics: Whether to enable CloudWatch metrics
        """
        self.api_url = api_url
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.logger = create_structured_logger(__name__)
        
        # Initialize error handling components
        self.metrics = CloudWatchMetrics() if enable_metrics else None
        self.retry_config = RetryConfig(
            max_attempts=retry_attempts,
            base_delay=2.0,
            max_delay=60.0,
            exponential_base=2.0
        )
        self.retry_handler = RetryHandler(self.retry_config, self.metrics)
        self.error_classifier = ErrorClassifier()
    
    def fetch_formulas(self) -> List[Dict]:
        """
        Fetch all formulas from the Homebrew API with retry logic.
        
        Returns:
            List of formula dictionaries from the API
            
        Raises:
            requests.RequestException: If API request fails after all retries
            ValueError: If API response is invalid
        """
        def _fetch():
            self.logger.info(f"Fetching formulas from {self.api_url}")
            
            response = requests.get(
                self.api_url,
                timeout=self.timeout,
                headers={
                    'User-Agent': 'homebrew-bottles-sync/1.0',
                    'Accept': 'application/json'
                }
            )
            response.raise_for_status()
            
            data = response.json()
            
            if not isinstance(data, list):
                raise ValueError("API response must be a list of formulas")
            
            return data
        
        try:
            data = self.retry_handler.retry_sync(_fetch)
            self.logger.info(f"Successfully fetched {len(data)} formulas")
            
            # Send success metric
            if self.metrics:
                self.metrics.put_metric('HomebrewAPIFetch', 1, 'Count', {'Operation': 'fetch_formulas'})
            
            return data
            
        except (ValueError, KeyError) as e:
            self.logger.error(f"Invalid API response: {e}")
            if self.metrics:
                self.metrics.put_error_metric(
                    self.error_classifier.classify_error(e, "fetch_formulas")
                )
            raise
        except Exception as e:
            self.logger.error(f"Failed to fetch formulas: {e}")
            if self.metrics:
                self.metrics.put_error_metric(
                    self.error_classifier.classify_error(e, "fetch_formulas")
                )
            raise
    
    def parse_formula(self, formula_data: Dict) -> Optional[Formula]:
        """
        Parse a single formula from API data.
        
        Args:
            formula_data: Raw formula data from API
            
        Returns:
            Formula object or None if parsing fails
        """
        try:
            name = formula_data.get('name')
            if not name:
                self.logger.warning("Formula missing name, skipping")
                return None
            
            # Get version from versions.stable or fallback to version_scheme
            versions = formula_data.get('versions', {})
            version = versions.get('stable')
            if not version:
                self.logger.warning(f"Formula {name} missing stable version, skipping")
                return None
            
            # Parse bottles
            bottles_data = formula_data.get('bottle', {}).get('stable', {}).get('files', {})
            bottles = {}
            
            for platform, bottle_data in bottles_data.items():
                try:
                    bottle_info = BottleInfo(
                        url=bottle_data.get('url', ''),
                        sha256=bottle_data.get('sha256', ''),
                        size=bottle_data.get('size', 0)
                    )
                    bottle_info.validate()
                    bottles[platform] = bottle_info
                except (ValueError, KeyError) as e:
                    self.logger.warning(f"Invalid bottle data for {name}:{platform}: {e}")
                    continue
            
            formula = Formula(name=name, version=version, bottles=bottles)
            formula.validate()
            return formula
            
        except (ValueError, KeyError) as e:
            self.logger.warning(f"Failed to parse formula: {e}")
            return None
    
    def parse_formulas(self, formulas_data: List[Dict]) -> List[Formula]:
        """
        Parse multiple formulas from API data.
        
        Args:
            formulas_data: List of raw formula data from API
            
        Returns:
            List of successfully parsed Formula objects
        """
        formulas = []
        failed_count = 0
        
        for formula_data in formulas_data:
            formula = self.parse_formula(formula_data)
            if formula:
                formulas.append(formula)
            else:
                failed_count += 1
        
        self.logger.info(f"Parsed {len(formulas)} formulas successfully, {failed_count} failed")
        return formulas
    
    def filter_formulas_by_platforms(self, 
                                   formulas: List[Formula], 
                                   target_platforms: List[str]) -> List[Formula]:
        """
        Filter formulas to only include those with bottles for target platforms.
        
        Args:
            formulas: List of Formula objects
            target_platforms: List of target platform names
            
        Returns:
            List of formulas that have bottles for at least one target platform
        """
        filtered_formulas = []
        
        for formula in formulas:
            target_bottles = formula.get_target_bottles(target_platforms)
            if target_bottles:
                # Create a new formula with only target bottles
                filtered_formula = Formula(
                    name=formula.name,
                    version=formula.version,
                    bottles=target_bottles
                )
                filtered_formulas.append(filtered_formula)
        
        self.logger.info(f"Filtered to {len(filtered_formulas)} formulas with target platform bottles")
        return filtered_formulas
    
    def estimate_download_size(self, 
                             formulas: List[Formula], 
                             target_platforms: Optional[List[str]] = None) -> DownloadEstimate:
        """
        Estimate total download size for formulas.
        
        Args:
            formulas: List of Formula objects
            target_platforms: Optional list of target platforms to filter by
            
        Returns:
            DownloadEstimate with size calculations
        """
        total_bottles = 0
        total_size_bytes = 0
        formulas_with_bottles = 0
        
        for formula in formulas:
            bottles_to_count = formula.bottles
            
            # Filter by target platforms if specified
            if target_platforms:
                bottles_to_count = formula.get_target_bottles(target_platforms)
            
            if bottles_to_count:
                formulas_with_bottles += 1
                for bottle in bottles_to_count.values():
                    total_bottles += 1
                    total_size_bytes += bottle.size
        
        total_size_gb = total_size_bytes / (1024 ** 3)
        
        estimate = DownloadEstimate(
            total_bottles=total_bottles,
            total_size_bytes=total_size_bytes,
            total_size_gb=total_size_gb,
            formulas_with_bottles=formulas_with_bottles
        )
        
        self.logger.info(f"Download estimate: {total_bottles} bottles, "
                        f"{estimate.total_size_mb:.1f} MB ({total_size_gb:.2f} GB) "
                        f"from {formulas_with_bottles} formulas")
        
        return estimate
    
    def fetch_and_process_formulas(self, config: SyncConfig) -> Tuple[List[Formula], DownloadEstimate]:
        """
        Fetch formulas from API and process them according to configuration.
        
        Args:
            config: SyncConfig with target platforms and other settings
            
        Returns:
            Tuple of (filtered_formulas, download_estimate)
            
        Raises:
            requests.RequestException: If API request fails
            ValueError: If configuration or API response is invalid
        """
        # Validate config
        config.validate()
        
        # Fetch raw formula data
        raw_formulas = self.fetch_formulas()
        
        # Parse formulas
        parsed_formulas = self.parse_formulas(raw_formulas)
        
        # Filter by target platforms
        filtered_formulas = self.filter_formulas_by_platforms(
            parsed_formulas, 
            config.target_platforms
        )
        
        # Estimate download size
        download_estimate = self.estimate_download_size(
            filtered_formulas, 
            config.target_platforms
        )
        
        return filtered_formulas, download_estimate
    
    def should_use_ecs(self, download_estimate: DownloadEstimate, size_threshold_gb: int) -> bool:
        """
        Determine if ECS should be used based on download size.
        
        Args:
            download_estimate: DownloadEstimate object
            size_threshold_gb: Size threshold in GB for ECS routing
            
        Returns:
            True if ECS should be used, False for Lambda
        """
        use_ecs = download_estimate.total_size_gb >= size_threshold_gb
        
        self.logger.info(f"Download size: {download_estimate.total_size_gb:.2f} GB, "
                        f"threshold: {size_threshold_gb} GB, "
                        f"routing to: {'ECS' if use_ecs else 'Lambda'}")
        
        return use_ecs
    
    def get_formulas_summary(self, formulas: List[Formula]) -> Dict[str, int]:
        """
        Get a summary of formulas by platform.
        
        Args:
            formulas: List of Formula objects
            
        Returns:
            Dictionary with platform counts
        """
        platform_counts = {}
        
        for formula in formulas:
            for platform in formula.bottles.keys():
                platform_counts[platform] = platform_counts.get(platform, 0) + 1
        
        return platform_counts