#!/usr/bin/env python3
"""
Notification configuration management system.
Loads and manages notification settings from YAML configuration files.
"""

import os
import yaml
from datetime import datetime, time
from pathlib import Path
from typing import Dict, List, Optional, Any
import re


class NotificationConfig:
    """Manages notification configuration from YAML files"""
    
    def __init__(self, config_path: str = None):
        if config_path is None:
            # Default to config/notification-config.yaml
            project_root = Path(__file__).parent.parent
            config_path = project_root / "config" / "notification-config.yaml"
        
        self.config_path = Path(config_path)
        self.config = self._load_config()
    
    def _load_config(self) -> Dict:
        """Load configuration from YAML file with environment variable substitution"""
        
        if not self.config_path.exists():
            print(f"⚠️ Notification config file not found: {self.config_path}")
            return self._get_default_config()
        
        try:
            with open(self.config_path, 'r') as f:
                content = f.read()
            
            # Substitute environment variables
            content = self._substitute_env_vars(content)
            
            config = yaml.safe_load(content)
            return config or {}
            
        except Exception as e:
            print(f"⚠️ Error loading notification config: {e}")
            return self._get_default_config()
    
    def _substitute_env_vars(self, content: str) -> str:
        """Substitute environment variables in configuration content"""
        
        # Pattern to match ${VAR_NAME} or ${VAR_NAME:default_value}
        pattern = r'\$\{([^}:]+)(?::([^}]*))?\}'
        
        def replace_var(match):
            var_name = match.group(1)
            default_value = match.group(2) or ""
            return os.getenv(var_name, default_value)
        
        return re.sub(pattern, replace_var, content)
    
    def _get_default_config(self) -> Dict:
        """Get default configuration when config file is not available"""
        
        return {
            "global": {
                "severity_routing": {
                    "critical": ["slack", "email"],
                    "high": ["slack", "email"],
                    "medium": ["slack"],
                    "low": ["slack"],
                    "info": ["slack"]
                }
            },
            "slack": {
                "default_webhook": os.getenv('SLACK_WEBHOOK_URL', ''),
                "channels": {}
            },
            "email": {
                "recipients": {
                    "dev": [],
                    "staging": [],
                    "prod": []
                }
            },
            "environments": {},
            "notification_types": {}
        }
    
    def get_severity_routing(self, severity: str) -> List[str]:
        """Get notification channels for a given severity level"""
        
        routing = self.config.get("global", {}).get("severity_routing", {})
        return routing.get(severity, ["slack"])
    
    def get_environment_config(self, environment: str) -> Dict:
        """Get configuration for a specific environment"""
        
        return self.config.get("environments", {}).get(environment, {})
    
    def get_notification_channels(self, notification_type: str, environment: str, severity: str) -> List[str]:
        """Get notification channels for a specific notification type, environment, and severity"""
        
        # Start with severity-based routing
        channels = self.get_severity_routing(severity)
        
        # Check for environment-specific overrides
        env_config = self.get_environment_config(environment)
        env_channels = env_config.get("channels", {}).get(notification_type)
        
        if env_channels:
            channels = env_channels
        
        return channels
    
    def get_slack_config(self) -> Dict:
        """Get Slack configuration"""
        
        return self.config.get("slack", {})
    
    def get_email_config(self) -> Dict:
        """Get email configuration"""
        
        return self.config.get("email", {})
    
    def get_email_recipients(self, environment: str, notification_type: str = None) -> List[str]:
        """Get email recipients for an environment and notification type"""
        
        email_config = self.get_email_config()
        recipients = []
        
        # Get environment-specific recipients
        env_recipients = email_config.get("recipients", {}).get(environment, [])
        recipients.extend(env_recipients)
        
        # Get special recipient lists based on notification type
        if notification_type:
            if "cost" in notification_type:
                cost_recipients = email_config.get("recipients", {}).get("cost_alerts", [])
                recipients.extend(cost_recipients)
            elif "security" in notification_type:
                security_recipients = email_config.get("recipients", {}).get("security", [])
                recipients.extend(security_recipients)
        
        # Remove duplicates and empty strings
        recipients = [r.strip() for r in recipients if r and r.strip()]
        return list(set(recipients))
    
    def get_critical_recipients(self) -> List[str]:
        """Get critical alert recipients"""
        
        email_config = self.get_email_config()
        return email_config.get("recipients", {}).get("critical", [])
    
    def should_send_notification(self, environment: str, severity: str, notification_type: str) -> bool:
        """Check if notification should be sent based on time restrictions and rules"""
        
        env_config = self.get_environment_config(environment)
        
        # Check quiet hours
        if self._is_quiet_hours(env_config, severity):
            return False
        
        # Check business hours restrictions
        if self._is_outside_business_hours(env_config, severity):
            return False
        
        return True
    
    def _is_quiet_hours(self, env_config: Dict, severity: str) -> bool:
        """Check if current time is within quiet hours"""
        
        quiet_hours = env_config.get("quiet_hours", {})
        if not quiet_hours.get("enabled", False):
            return False
        
        # Check if severity is exempt from quiet hours
        exceptions = quiet_hours.get("exceptions", [])
        if severity in exceptions:
            return False
        
        # Parse time range
        try:
            start_time = datetime.strptime(quiet_hours.get("start", "22:00"), "%H:%M").time()
            end_time = datetime.strptime(quiet_hours.get("end", "08:00"), "%H:%M").time()
            current_time = datetime.utcnow().time()
            
            # Handle overnight quiet hours (e.g., 22:00 to 08:00)
            if start_time > end_time:
                return current_time >= start_time or current_time <= end_time
            else:
                return start_time <= current_time <= end_time
                
        except ValueError:
            return False
    
    def _is_outside_business_hours(self, env_config: Dict, severity: str) -> bool:
        """Check if current time is outside business hours"""
        
        business_hours = env_config.get("business_hours_only", {})
        if not business_hours.get("enabled", False):
            return False
        
        # Check if severity is exempt from business hours restriction
        exceptions = business_hours.get("exceptions", [])
        if severity in exceptions:
            return False
        
        now = datetime.utcnow()
        
        # Check weekdays only restriction
        if business_hours.get("weekdays_only", False):
            if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
                return True
        
        # Parse business hours
        try:
            start_time = datetime.strptime(business_hours.get("start", "09:00"), "%H:%M").time()
            end_time = datetime.strptime(business_hours.get("end", "18:00"), "%H:%M").time()
            current_time = now.time()
            
            return not (start_time <= current_time <= end_time)
            
        except ValueError:
            return False
    
    def get_severity_override(self, environment: str, notification_type: str) -> Optional[str]:
        """Get severity override for a specific environment and notification type"""
        
        env_config = self.get_environment_config(environment)
        overrides = env_config.get("severity_override", {})
        return overrides.get(notification_type)
    
    def get_notification_type_config(self, notification_type: str) -> Dict:
        """Get configuration for a specific notification type"""
        
        return self.config.get("notification_types", {}).get(notification_type, {})
    
    def get_dashboard_urls(self, environment: str) -> Dict[str, str]:
        """Get dashboard URLs for an environment"""
        
        dashboard_config = self.config.get("dashboard", {})
        base_url = dashboard_config.get("base_url", "")
        paths = dashboard_config.get("paths", {})
        
        urls = {}
        for key, path_template in paths.items():
            urls[key] = base_url + path_template.format(environment=environment)
        
        return urls
    
    def get_thresholds(self) -> Dict:
        """Get monitoring and alerting thresholds"""
        
        return self.config.get("thresholds", {})
    
    def get_cost_threshold(self, environment: str) -> float:
        """Get cost threshold for an environment"""
        
        thresholds = self.get_thresholds()
        cost_thresholds = thresholds.get("costs", {})
        return cost_thresholds.get(environment, 1000.0)  # Default $1000
    
    def get_custom_fields(self) -> List[Dict]:
        """Get custom fields to include in notifications"""
        
        content_config = self.config.get("content", {})
        return content_config.get("custom_fields", [])
    
    def get_links(self) -> Dict[str, str]:
        """Get additional links to include in notifications"""
        
        content_config = self.config.get("content", {})
        return content_config.get("links", {})
    
    def is_rate_limited(self, notification_type: str, environment: str) -> bool:
        """Check if notifications are rate limited (placeholder for future implementation)"""
        
        # This would integrate with a rate limiting system
        # For now, always return False
        return False
    
    def get_retry_config(self) -> Dict:
        """Get retry configuration for failed notifications"""
        
        return self.config.get("global", {}).get("retry", {
            "max_attempts": 3,
            "backoff_seconds": [5, 15, 30]
        })
    
    def validate_config(self) -> List[str]:
        """Validate configuration and return list of issues"""
        
        issues = []
        
        # Check required sections
        required_sections = ["global", "slack", "email"]
        for section in required_sections:
            if section not in self.config:
                issues.append(f"Missing required section: {section}")
        
        # Check Slack configuration
        slack_config = self.get_slack_config()
        if not slack_config.get("default_webhook"):
            issues.append("Slack webhook URL not configured")
        
        # Check email configuration
        email_config = self.get_email_config()
        smtp_config = email_config.get("smtp", {})
        if not smtp_config.get("server"):
            issues.append("SMTP server not configured")
        
        # Check environment configurations
        environments = ["dev", "staging", "prod"]
        for env in environments:
            recipients = self.get_email_recipients(env)
            if not recipients:
                issues.append(f"No email recipients configured for {env} environment")
        
        return issues
    
    def reload_config(self):
        """Reload configuration from file"""
        
        self.config = self._load_config()
        print("📝 Notification configuration reloaded")


def main():
    """CLI interface for notification configuration management"""
    
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description="Notification configuration management")
    parser.add_argument("--config-file", help="Path to notification config file")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Validate command
    subparsers.add_parser("validate", help="Validate configuration")
    
    # Show command
    show_parser = subparsers.add_parser("show", help="Show configuration")
    show_parser.add_argument("--section", help="Show specific section")
    show_parser.add_argument("--environment", help="Show environment-specific config")
    
    # Test command
    test_parser = subparsers.add_parser("test", help="Test notification routing")
    test_parser.add_argument("--notification-type", required=True)
    test_parser.add_argument("--environment", required=True)
    test_parser.add_argument("--severity", default="medium")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Initialize config
    config = NotificationConfig(args.config_file)
    
    if args.command == "validate":
        issues = config.validate_config()
        if issues:
            print("❌ Configuration validation failed:")
            for issue in issues:
                print(f"  • {issue}")
        else:
            print("✅ Configuration is valid")
    
    elif args.command == "show":
        if args.section:
            section_config = config.config.get(args.section, {})
            print(json.dumps(section_config, indent=2))
        elif args.environment:
            env_config = config.get_environment_config(args.environment)
            print(json.dumps(env_config, indent=2))
        else:
            print(json.dumps(config.config, indent=2))
    
    elif args.command == "test":
        channels = config.get_notification_channels(
            args.notification_type,
            args.environment,
            args.severity
        )
        
        should_send = config.should_send_notification(
            args.environment,
            args.severity,
            args.notification_type
        )
        
        print(f"Notification Type: {args.notification_type}")
        print(f"Environment: {args.environment}")
        print(f"Severity: {args.severity}")
        print(f"Channels: {channels}")
        print(f"Should Send: {should_send}")
        
        if not should_send:
            print("⚠️ Notification would be suppressed due to time restrictions")


if __name__ == "__main__":
    main()