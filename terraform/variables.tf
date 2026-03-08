variable "aws_region" {
  type        = string
  description = "AWS region for deployment."
  default     = "us-west-2"
}

variable "app_name" {
  type        = string
  description = "Base name for App Runner and related resources."
  default     = "nash"
}

variable "environment" {
  type        = string
  description = "Deployment environment (dev, test, staging, prod)."
  validation {
    condition     = contains(["dev", "test", "staging", "prod"], var.environment)
    error_message = "environment must be one of dev, test, staging, prod."
  }
}

variable "container_port" {
  type        = number
  description = "Container port exposed by the service."
  default     = 3080
}

variable "ecr_image_tag" {
  type        = string
  description = "Base image tag for ECR images."
  default     = "latest"
}

variable "cpu" {
  type        = number
  description = "CPU units for App Runner."
  default     = 2048
  validation {
    condition     = contains([256, 512, 1024, 2048, 4096], var.cpu)
    error_message = "cpu must be one of 256, 512, 1024, 2048, 4096."
  }
}

variable "memory" {
  type        = number
  description = "Memory (MB) for App Runner."
  default     = 4096
  validation {
    condition     = var.memory >= 512 && var.memory <= 12288
    error_message = "memory must be between 512 and 12288 MB."
  }
}

variable "min_instances" {
  type        = number
  description = "Minimum App Runner instances."
  default     = 1
}

variable "max_instances" {
  type        = number
  description = "Maximum App Runner instances."
  default     = 2
}

variable "max_concurrency" {
  type        = number
  description = "Maximum requests per instance."
  default     = 100
}

variable "health_check_path" {
  type        = string
  description = "Health check path."
  default     = "/health"
}

variable "health_check_interval" {
  type        = number
  description = "Health check interval in seconds."
  default     = 10
}

variable "health_check_timeout" {
  type        = number
  description = "Health check timeout in seconds."
  default     = 5
}

variable "health_check_healthy_threshold" {
  type        = number
  description = "Number of consecutive successes to mark healthy."
  default     = 1
}

variable "health_check_unhealthy_threshold" {
  type        = number
  description = "Number of consecutive failures to mark unhealthy."
  default     = 5
}

variable "ecr_retain_count" {
  type        = number
  description = "Number of tagged images to retain per environment."
  default     = 10
}

variable "ecr_untagged_expire_days" {
  type        = number
  description = "Days before untagged images expire."
  default     = 7
}

# --- Secrets (stored in SSM) ---

variable "backboard_api_key" {
  type        = string
  description = "Backboard.io API key."
  sensitive   = true
}

variable "backboard_assistant_id" {
  type        = string
  description = "Backboard assistant ID for Nash storage."
  sensitive   = true
}

variable "jwt_secret" {
  type        = string
  description = "JWT signing secret."
  sensitive   = true
}

variable "jwt_refresh_secret" {
  type        = string
  description = "JWT refresh token signing secret."
  sensitive   = true
}

variable "sso_secret" {
  type        = string
  description = "Shared secret for SSO."
  sensitive   = true
  default     = ""
}

# --- Non-sensitive config ---

variable "domain_client" {
  type        = string
  description = "Public client URL (e.g. https://nash.backboard.io)."
  default     = ""
}

variable "domain_server" {
  type        = string
  description = "Public server URL (usually same as domain_client for App Runner)."
  default     = ""
}

variable "app_title" {
  type        = string
  description = "Application title shown in the UI."
  default     = "Nash"
}

variable "custom_domain" {
  type        = string
  description = "Custom domain to associate with App Runner. Leave empty to skip."
  default     = ""
}

# --- Google OAuth ---

variable "google_client_id" {
  type      = string
  sensitive = true
}

variable "google_client_secret" {
  type      = string
  sensitive = true
}

variable "google_callback_url" {
  type    = string
  default = "/oauth/google/callback"
}

# --- Stripe Billing ---

variable "stripe_secret_key" {
  type        = string
  description = "Stripe API secret key."
  sensitive   = true
}

variable "stripe_webhook_secret" {
  type        = string
  description = "Stripe webhook signing secret."
  sensitive   = true
}

variable "stripe_price_id_plus" {
  type        = string
  description = "Stripe Price ID for the Plus subscription tier."
}

variable "stripe_price_id_unlimited" {
  type        = string
  description = "Stripe Price ID for the Unlimited subscription tier."
}

variable "plus_included_tokens" {
  type        = string
  description = "Token allowance for Plus plan."
  default     = "500000"
}

variable "backboard_auth_assistant_id" {
  type        = string
  description = "Backboard assistant ID for the auth store (users, sessions, tokens)."
}

# --- Monitoring ---

variable "log_retention_days" {
  type        = number
  description = "CloudWatch log retention in days."
  default     = 90
}

variable "alarm_email" {
  type        = string
  description = "Email address for CloudWatch alarm notifications. Leave empty to skip."
  default     = ""
}
