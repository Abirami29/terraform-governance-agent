# NEGATIVE CASE (golden-set): this module is clean.
# Used to confirm security_check does NOT over-flag well-configured resources.
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

resource "aws_vpc" "this" {
  cidr_block           = var.cidr_block
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = var.name
  }
}

variable "cidr_block" {
  type = string
}

variable "name" {
  type = string
}