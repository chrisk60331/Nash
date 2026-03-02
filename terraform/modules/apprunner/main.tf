locals {
  service_name = "${var.app_name}-${var.environment}"
}

# --- IAM: ECR access role (for App Runner to pull images) ---

data "aws_iam_policy_document" "ecr_access_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["build.apprunner.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ecr_access" {
  name               = "${local.service_name}-ecr-access"
  assume_role_policy = data.aws_iam_policy_document.ecr_access_assume.json
}

resource "aws_iam_role_policy_attachment" "ecr_access" {
  role       = aws_iam_role.ecr_access.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess"
}

# --- IAM: Instance role (for SSM access at runtime) ---

data "aws_iam_policy_document" "instance_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["tasks.apprunner.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "instance" {
  name               = "${local.service_name}-instance"
  assume_role_policy = data.aws_iam_policy_document.instance_assume.json
}

resource "aws_iam_role_policy" "instance_ssm" {
  name = "${local.service_name}-ssm-access"
  role = aws_iam_role.instance.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["ssm:GetParameter", "ssm:GetParameters"]
        Resource = values(var.ssm_secret_arns)
      }
    ]
  })
}

# --- Auto-scaling ---

resource "aws_apprunner_auto_scaling_configuration_version" "this" {
  auto_scaling_configuration_name = "${local.service_name}-scaling"
  min_size                        = var.min_instances
  max_size                        = var.max_instances
  max_concurrency                 = var.max_concurrency
}

# --- App Runner Service ---

resource "aws_apprunner_service" "this" {
  service_name = local.service_name

  auto_scaling_configuration_arn = aws_apprunner_auto_scaling_configuration_version.this.arn

  source_configuration {
    authentication_configuration {
      access_role_arn = aws_iam_role.ecr_access.arn
    }

    image_repository {
      image_identifier      = "${var.ecr_repository_url}:${var.environment}-${var.image_tag}"
      image_repository_type = "ECR"

      image_configuration {
        port = tostring(var.container_port)

        runtime_environment_variables = var.environment_variables

        runtime_environment_secrets = {
          for k, arn in var.ssm_secret_arns : k => arn
        }
      }
    }

    auto_deployments_enabled = false
  }

  instance_configuration {
    cpu               = tostring(var.cpu)
    memory            = tostring(var.memory)
    instance_role_arn = aws_iam_role.instance.arn
  }

  health_check_configuration {
    protocol            = "HTTP"
    path                = var.health_check_path
    interval            = var.health_check_interval
    timeout             = var.health_check_timeout
    healthy_threshold   = var.health_check_healthy_threshold
    unhealthy_threshold = var.health_check_unhealthy_threshold
  }
}
