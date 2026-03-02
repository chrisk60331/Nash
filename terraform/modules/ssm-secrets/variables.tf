variable "app_name" {
  type        = string
  description = "Application name (used in SSM path prefix)."
}

variable "environment" {
  type        = string
  description = "Deployment environment (used in SSM path prefix)."
}

variable "secrets" {
  type        = map(string)
  description = "Map of secret-name => secret-value to store in SSM."
  sensitive   = true
}
