terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.60, < 7.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project   = "cloud-native-devops-platform"
      ManagedBy = "terraform"
    }
  }
}

variable "aws_region" {
  description = "AWS region."
  type        = string
  default     = "ap-south-1"
}

variable "cluster_name" {
  type    = string
  default = "taskapi-eks"
}

variable "kubernetes_version" {
  description = "No default on purpose. Look up a version in EKS standard support today; older versions move to paid extended support."
  type        = string
}

variable "admin_cidr" {
  description = "Your public IP in CIDR form (for example 203.0.113.10/32). Only this range may reach the cluster API."
  type        = string
}

variable "node_instance_type" {
  type    = string
  default = "t3.small"
}

data "aws_availability_zones" "available" {
  state = "available"
}

# COST NOTE: nodes sit in public subnets so no NAT gateway (an hourly charge plus data
# fees) is needed. Security groups still block inbound traffic. See docs/cost-and-cleanup.md.
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "${var.cluster_name}-vpc"
  cidr = "10.0.0.0/16"
  azs  = slice(data.aws_availability_zones.available.names, 0, 2)

  public_subnets          = ["10.0.1.0/24", "10.0.2.0/24"]
  map_public_ip_on_launch = true
  enable_nat_gateway      = false
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = var.cluster_name
  cluster_version = var.kubernetes_version

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.public_subnets

  cluster_endpoint_public_access           = true
  cluster_endpoint_public_access_cidrs     = [var.admin_cidr]
  enable_cluster_creator_admin_permissions = true

  # The module enables control-plane logging to CloudWatch by default, which adds cost.
  # Turned off for a short learning session; enable audit logs for anything real.
  cluster_enabled_log_types = []

  eks_managed_node_groups = {
    default = {
      instance_types = [var.node_instance_type]
      min_size       = 1
      max_size       = 2
      desired_size   = 1
    }
  }
}

output "configure_kubectl" {
  value = "aws eks update-kubeconfig --region ${var.aws_region} --name ${var.cluster_name}"
}
