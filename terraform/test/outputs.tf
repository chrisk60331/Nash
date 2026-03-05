output "service_url" {
  description = "App Runner service URL."
  value       = module.apprunner.service_url
}

output "service_arn" {
  description = "App Runner service ARN."
  value       = module.apprunner.service_arn
}

output "ecr_repository_url" {
  description = "ECR repository URL."
  value       = module.ecr.repository_url
}

output "ecr_push_commands" {
  description = "Helper commands to build and push the image."
  value = [
    "aws ecr get-login-password --region ${var.aws_region} | docker login --username AWS --password-stdin ${module.ecr.repository_url}",
    "docker build -t ${var.app_name} .",
    "docker tag ${var.app_name}:latest ${module.ecr.repository_url}:${var.environment}-${var.ecr_image_tag}",
    "docker push ${module.ecr.repository_url}:${var.environment}-${var.ecr_image_tag}"
  ]
}

output "ssm_parameter_arns" {
  description = "SSM parameter ARNs for all secrets."
  value       = module.ssm_secrets.arns
}
