output "service_url" {
  description = "App Runner service URL."
  value       = aws_apprunner_service.this.service_url
}

output "service_arn" {
  description = "App Runner service ARN."
  value       = aws_apprunner_service.this.arn
}

output "service_id" {
  description = "App Runner service ID."
  value       = aws_apprunner_service.this.service_id
}

output "custom_domain_dns_records" {
  description = "DNS CNAME records required for custom domain validation."
  value       = var.custom_domain != "" ? aws_apprunner_custom_domain_association.this[0].certificate_validation_records : []
}
