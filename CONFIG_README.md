# Configuration System

This document describes the centralized configuration system for the Homebrew Bottles Sync System.

## Overview

The configuration system uses a single `config.yaml` file to manage all environment settings and automatically generates environment-specific `terraform.tfvars` files.

## Quick Start

1. **Edit the configuration**: Modify `config.yaml` with your settings
2. **Run setup script**: Execute `./scripts/setup-config.sh`
3. **Review generated files**: Check the generated `terraform/*.tfvars` files

## Configuration File Structure

### Project Settings
```yaml
project:
  name: "homebrew-bottles-sync"
  description: "Automated Homebrew bottles sync system"
  version: "1.0.0"
```

### Environment Settings
```yaml
environments:
  dev:
    aws_region: "us-west-2"
    size_threshold_gb: 5
    schedule_expression: "cron(0 */6 * * ? *)"
    enable_fargate_spot: true
    auto_shutdown: true
```

### Resource Configuration
```yaml
resources:
  lambda:
    orchestrator_memory: 512
    sync_memory: 3008
    timeout: 900
  ecs:
    task_cpu: 2048
    task_memory: 8192
    ephemeral_storage: 100
```

### Notifications
```yaml
notifications:
  slack:
    enabled: true
    channel: "#platform-updates"
  email:
    enabled: true
    addresses: ["devops@company.com"]
```

## Configuration Processor

The `scripts/config_processor.py` script provides several functions:

### Validate Configuration
```bash
python3 scripts/config_processor.py --validate
```

### Generate All terraform.tfvars Files
```bash
python3 scripts/config_processor.py --generate
```

### Generate Specific Environment
```bash
python3 scripts/config_processor.py --generate --environment dev
```

## Environment-Specific Optimizations

### Development Environment
- **Cost Optimized**: Uses smaller resources and Fargate Spot instances
- **Auto Shutdown**: Automatically shuts down expensive resources after hours
- **Frequent Sync**: Runs every 6 hours for testing

### Staging Environment
- **Production-like**: Similar to production but with some cost optimizations
- **Weekly Sync**: Runs weekly on Saturdays
- **Spot Instances**: Uses Fargate Spot for cost savings

### Production Environment
- **Full Resources**: Uses full production-grade resources
- **Reliability**: Uses on-demand instances for maximum reliability
- **Weekly Sync**: Runs weekly on Sundays

## Validation Rules

The configuration processor validates:

- **Required Sections**: All mandatory sections are present
- **AWS Regions**: Valid AWS region format (e.g., us-east-1)
- **Resource Limits**: Memory, CPU, and storage within AWS limits
- **Cron Expressions**: Valid AWS cron format
- **Email Addresses**: Valid email format when notifications enabled

## Error Handling

When validation fails, the processor provides:
- **Clear Error Messages**: Describes what's wrong
- **Fix Suggestions**: Tells you how to fix the issue
- **Field Location**: Shows exactly which field has the problem

Example error output:
```
Configuration validation failed:
  - environments.dev.aws_region: Invalid AWS region format: invalid-region
    Fix: Use format like 'us-east-1' or 'us-west-2'
```

## Generated Files

The processor generates these files:
- `terraform/dev.tfvars` - Development environment variables
- `terraform/staging.tfvars` - Staging environment variables  
- `terraform/prod.tfvars` - Production environment variables

**Important**: These files are auto-generated and should not be edited manually.

## Integration with CI/CD

The configuration system integrates with the CI/CD pipeline:

1. **Validation**: Pipeline validates config.yaml on every commit
2. **Generation**: Automatically generates tfvars before deployment
3. **Environment Selection**: Uses appropriate tfvars for each environment

## Troubleshooting

### Common Issues

**Config file not found**
```bash
Error: Configuration file not found: config.yaml
```
Solution: Ensure config.yaml exists in the project root

**Invalid YAML syntax**
```bash
Error: Invalid YAML syntax in config.yaml
```
Solution: Check YAML formatting, indentation, and syntax

**Missing required sections**
```bash
- resources: Missing required section: resources
```
Solution: Add the missing section to config.yaml

**Invalid AWS region**
```bash
- environments.dev.aws_region: Invalid AWS region format
```
Solution: Use valid AWS region format like 'us-east-1'

### Getting Help

1. Run validation to see specific errors:
   ```bash
   python3 scripts/config_processor.py --validate
   ```

2. Check the generated tfvars files:
   ```bash
   cat terraform/dev.tfvars
   ```

3. Review this documentation for configuration options

## Best Practices

1. **Always validate** before committing changes
2. **Use the setup script** for initial configuration
3. **Don't edit generated files** manually
4. **Keep sensitive data** in GitHub Secrets, not in config.yaml
5. **Test changes** in development environment first