locals {
  secret_keys = nonsensitive(toset(keys(var.secrets)))
}

resource "aws_ssm_parameter" "secret" {
  for_each = local.secret_keys

  name        = "/${var.app_name}/${var.environment}/${each.key}"
  description = "${each.key} for ${var.app_name}-${var.environment}"
  type        = "SecureString"
  value       = var.secrets[each.key]

  tags = {
    App         = var.app_name
    Environment = var.environment
  }
}
