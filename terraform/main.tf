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
  bucket = local.s3_landing_bucket_name
  # A bucket that still holds objects cannot be destroyed.
  force_destroy = false
}

# Keeps the previous version of an overwritten or deleted object, so it can be restored.
resource "aws_s3_bucket_versioning" "data_landing_zone_versioning" {
  bucket = aws_s3_bucket.data_landing_zone.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "data_landing_zone_lifecycle" {
  bucket = aws_s3_bucket.data_landing_zone.id

  rule {
    id     = "expire-old-versions"
    status = "Enabled"

    filter {}

    # Applies only to replaced versions; current objects never expire.
    noncurrent_version_expiration {
      noncurrent_days = var.noncurrent_version_retention_days
    }

    expiration {
      expired_object_delete_marker = true
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }

  depends_on = [aws_s3_bucket_versioning.data_landing_zone_versioning]
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
      "s3:GetObject",
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

resource "aws_iam_user" "guest_user" {
  name          = local.iam_guest_user_name
  force_destroy = true
}

resource "aws_iam_access_key" "guest_user_keys" {
  user = aws_iam_user.guest_user.name
}

data "aws_iam_policy_document" "guest_user_policy" {
  statement {
    effect = "Allow"
    actions = [
      "s3:ListBucket"
    ]
    resources = [
      aws_s3_bucket.data_landing_zone.arn
    ]
  }
  statement {
    effect = "Allow"
    actions = [
      "s3:GetObject"
    ]
    resources = [
      "${aws_s3_bucket.data_landing_zone.arn}/*"
    ]
  }
}

resource "aws_iam_user_policy" "guest_user_policy" {
  name   = local.iam_guest_user_policy
  user   = aws_iam_user.guest_user.name
  policy = data.aws_iam_policy_document.guest_user_policy.json
}

resource "aws_iam_user_login_profile" "guest_user_profile" {
  user                    = aws_iam_user.guest_user.name
  password_reset_required = true
}

data "aws_caller_identity" "current" {}
