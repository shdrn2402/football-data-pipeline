output "loader_access_key_id" {
  description = "AWS Access Key ID for data ingestion"
  value       = aws_iam_access_key.data_loader_keys.id
}

output "loader_secret_access_key" {
  description = "AWS Secret Access Key for data ingestion"
  value       = aws_iam_access_key.data_loader_keys.secret
  sensitive   = true
}

output "guest_access_key_id" {
  description = "AWS Access Key ID for guest user"
  value       = aws_iam_access_key.guest_user_keys.id
}

output "guest_secret_access_key" {
  description = "AWS Secret Access Key for guest user"
  value       = aws_iam_access_key.guest_user_keys.secret
  sensitive   = true
}

output "guest_console_password" {
  description = "AWS Console password for guest user"
  value       = aws_iam_user_login_profile.guest_user_profile.password
  sensitive   = true
}

output "console_login_url" {
  description = "AWS Console login URL"
  value       = "https://${data.aws_caller_identity.current.account_id}.signin.aws.amazon.com/console"
}

output "s3_bucket_name" {
  description = "S3 bucket name for data landing zone"
  value       = aws_s3_bucket.data_landing_zone.bucket
}
