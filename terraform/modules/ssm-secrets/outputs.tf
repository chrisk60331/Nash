output "arns" {
  description = "Map of secret-name => SSM parameter ARN."
  value       = { for k, v in aws_ssm_parameter.secret : k => v.arn }
}

output "names" {
  description = "Map of secret-name => SSM parameter name (path)."
  value       = { for k, v in aws_ssm_parameter.secret : k => v.name }
}
