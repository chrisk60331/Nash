variable "repository_name" {
  type        = string
  description = "ECR repository name."
}

variable "environment" {
  type        = string
  description = "Deployment environment (used for tag prefix in lifecycle)."
}

variable "retain_count" {
  type        = number
  description = "Number of tagged images to retain per environment."
  default     = 10
}

variable "untagged_expire_days" {
  type        = number
  description = "Days before untagged images expire."
  default     = 7
}
