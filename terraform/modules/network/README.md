# Network Module

This Terraform module creates a secure VPC infrastructure for the Homebrew Bottles Sync System, designed to support ECS tasks that need outbound internet access while maintaining security best practices.

## Architecture

The module creates a multi-AZ VPC with both public and private subnets:

- **Public Subnets**: Host NAT Gateways for outbound internet access
- **Private Subnets**: Host ECS tasks with no direct internet access
- **NAT Gateways**: Provide secure outbound internet access for private resources
- **Security Groups**: Implement least-privilege access controls
- **Network ACLs**: Additional security layer for subnet-level filtering

## Resources Created

### Core Networking
- VPC with DNS support enabled
- Internet Gateway for public subnet access
- Public subnets (configurable count across AZs)
- Private subnets (configurable count across AZs)
- NAT Gateways with Elastic IPs (optional)

### Security
- Security Group for ECS tasks (minimal outbound access)
- Security Group for Lambda functions (if VPC access needed)
- Network ACLs for public and private subnets
- Route tables with appropriate routing rules

## Usage

```hcl
module "network" {
  source = "./modules/network"
  
  project_name     = "homebrew-bottles-sync"
  environment      = "prod"
  vpc_cidr         = "10.0.0.0/16"
  availability_zones = ["us-east-1a", "us-east-1b"]
  
  public_subnet_cidrs  = ["10.0.1.0/24", "10.0.2.0/24"]
  private_subnet_cidrs = ["10.0.10.0/24", "10.0.20.0/24"]
  
  enable_nat_gateway = true
}
```

## Variables

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| project_name | Name of the project, used for resource naming | `string` | `"homebrew-bottles-sync"` | no |
| environment | Environment name (e.g., dev, staging, prod) | `string` | `"prod"` | no |
| vpc_cidr | CIDR block for the VPC | `string` | `"10.0.0.0/16"` | no |
| availability_zones | List of availability zones to use | `list(string)` | `["us-east-1a", "us-east-1b"]` | no |
| public_subnet_cidrs | CIDR blocks for public subnets | `list(string)` | `["10.0.1.0/24", "10.0.2.0/24"]` | no |
| private_subnet_cidrs | CIDR blocks for private subnets | `list(string)` | `["10.0.10.0/24", "10.0.20.0/24"]` | no |
| enable_nat_gateway | Whether to create NAT Gateways for private subnet internet access | `bool` | `true` | no |

## Outputs

| Name | Description |
|------|-------------|
| vpc_id | ID of the VPC |
| vpc_cidr_block | CIDR block of the VPC |
| public_subnet_ids | IDs of the public subnets |
| private_subnet_ids | IDs of the private subnets |
| internet_gateway_id | ID of the Internet Gateway |
| nat_gateway_ids | IDs of the NAT Gateways |
| ecs_security_group_id | ID of the security group for ECS tasks |
| lambda_security_group_id | ID of the security group for Lambda functions |
| public_route_table_id | ID of the public route table |
| private_route_table_ids | IDs of the private route tables |

## Security Features

### ECS Security Group
- **Outbound HTTPS (443)**: For downloading bottles and API calls
- **Outbound HTTP (80)**: For handling redirects
- **Outbound DNS (53/UDP)**: For domain name resolution
- **No inbound rules**: Following least privilege principle

### Network ACLs
- **Private Subnets**: Restrictive rules allowing only necessary outbound traffic
- **Public Subnets**: Permissive rules to support NAT Gateway functionality

### Best Practices Implemented
- DNS resolution enabled in VPC
- Multi-AZ deployment for high availability
- Separate route tables per private subnet
- Least privilege security group rules
- Network ACLs as additional security layer

## Cost Considerations

- NAT Gateways incur hourly charges and data processing fees
- Consider setting `enable_nat_gateway = false` for development environments
- Elastic IPs are free when attached to running NAT Gateways

## Requirements Satisfied

This module satisfies the following requirements from the Homebrew Bottles Sync System:

- **Requirement 5.1**: Modular Terraform infrastructure deployment
- **Requirement 6.1**: AWS security best practices with minimal required permissions