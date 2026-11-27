variable "aws_region" {
  type        = string
  description = "AWS region to deploy resources in"
  default     = "eu-central-1"
}

variable "project_name" {
  type        = string
  description = "Project name for tagging and naming resources"
  default     = "football-data-pipeline"
}

variable "environment" {
  type        = string
  description = "Deployment environment (e.g. dev, prod)"
}

variable "noncurrent_version_retention_days" {
  type        = number
  description = "Days a replaced or deleted object version stays restorable in the landing bucket"
  default     = 90
}
