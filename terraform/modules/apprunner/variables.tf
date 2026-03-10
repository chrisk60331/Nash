variable "app_name" {
  type        = string
  description = "Base application name."
}

variable "environment" {
  type        = string
  description = "Deployment environment."
}

variable "aws_region" {
  type        = string
  description = "AWS region."
}

variable "ecr_repository_url" {
  type        = string
  description = "Full ECR repository URL."
}

variable "image_tag" {
  type        = string
  description = "Docker image tag suffix."
  default     = "latest"
}

variable "container_port" {
  type        = number
  description = "Container port exposed by the service."
  default     = 3080
}

variable "cpu" {
  type        = number
  description = "CPU units for App Runner."
}

variable "memory" {
  type        = number
  description = "Memory (MB) for App Runner."
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
  default     = 20
}

variable "health_check_timeout" {
  type        = number
  description = "Health check timeout in seconds."
  default     = 19
}

variable "health_check_healthy_threshold" {
  type        = number
  description = "Consecutive successes to mark healthy."
  default     = 1
}

variable "health_check_unhealthy_threshold" {
  type        = number
  description = "Consecutive failures to mark unhealthy."
  default     = 5
}

variable "environment_variables" {
  type        = map(string)
  description = "Non-sensitive environment variables."
  default     = {}
}

variable "ssm_secret_arns" {
  type        = map(string)
  description = "Map of secret-name => SSM parameter ARN for runtime secrets."
  default     = {}
}

variable "custom_domain" {
  type        = string
  description = "Custom domain to associate with the App Runner service (e.g. nash.backboard.io). Leave empty to skip."
  default     = ""
}

variable "custom_domain_hellonash" {
  type        = string
  description = "Additional custom domain to associate with the App Runner service (e.g. hellonash.io). Leave empty to skip."
  default     = ""
}

variable "log_retention_days" {
  type        = number
  description = "CloudWatch log retention in days."
  default     = 90
}

variable "alarm_email" {
  type        = string
  description = "Email address to receive CloudWatch alarm notifications. Leave empty to skip alarms."
  default     = ""
}
