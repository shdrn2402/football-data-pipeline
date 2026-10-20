locals {
  s3_landing_bucket_name = "${var.project_name}-landing-zone-${var.environment}"
  iam_data_loader_name   = "${var.project_name}-data-loader-${var.environment}"
  iam_data_loader_policy = "${var.project_name}-data-loader-policy-${var.environment}"
  iam_guest_user_name    = "${var.project_name}-guest-user-${var.environment}"
  iam_guest_user_policy  = "${var.project_name}-guest-user-policy-${var.environment}"

  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}
