terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  backend "s3" {
    bucket       = "football-data-pipeline-terraform-state"
    key          = "global/s3/terraform.tfstate"
    region       = "eu-central-1"
    use_lockfile = true
    encrypt      = true
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = local.common_tags
  }
}

resource "aws_s3_bucket" "data_landing_zone" {
  bucket        = local.s3_landing_bucket_name
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "data_landing_zone_access_block" {
  bucket = aws_s3_bucket.data_landing_zone.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_iam_user" "data_loader" {
  name          = local.iam_data_loader_name
  force_destroy = true
}

resource "aws_iam_access_key" "data_loader_keys" {
  user = aws_iam_user.data_loader.name
}

data "aws_iam_policy_document" "data_loader_policy" {
  statement {
    effect = "Allow"
    actions = [
      "s3:PutObject",
      "s3:AbortMultipartUpload"
    ]
    resources = ["${aws_s3_bucket.data_landing_zone.arn}/*"]
  }
}

resource "aws_iam_user_policy" "data_loader_policy" {
  name   = local.iam_data_loader_policy
  user   = aws_iam_user.data_loader.name
  policy = data.aws_iam_policy_document.data_loader_policy.json
}

output "loader_access_key_id" {
  description = "AWS Access Key ID for data ingestion"
  value       = aws_iam_access_key.data_loader_keys.id
}

output "loader_secret_access_key" {
  description = "AWS Secret Access Key for data ingestion"
  value       = aws_iam_access_key.data_loader_keys.secret
  sensitive   = true
}

output "s3_bucket_name" {
  description = "S3 bucket name for data landing zone"
  value       = aws_s3_bucket.data_landing_zone.bucket
}
