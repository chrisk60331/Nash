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

data "aws_caller_identity" "current" {}

resource "aws_iam_role_policy" "instance_ssm" {
  name = "${local.service_name}-ssm-access"
  role = aws_iam_role.instance.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["ssm:GetParameter", "ssm:GetParameters"]
        Resource = "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter/${var.app_name}/${var.environment}/*"
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

# --- Custom Domain ---

resource "aws_apprunner_custom_domain_association" "this" {
  count                = var.custom_domain != "" ? 1 : 0
  domain_name          = var.custom_domain
  service_arn          = aws_apprunner_service.this.arn
  enable_www_subdomain = false
}

resource "aws_apprunner_custom_domain_association" "hellonash" {
  count                = var.custom_domain_hellonash != "" ? 1 : 0
  domain_name          = var.custom_domain_hellonash
  service_arn          = aws_apprunner_service.this.arn
  enable_www_subdomain = false
}

# --- CloudWatch: Log retention ---
# App Runner creates this log group automatically on first deploy.
# Terraform adopts it here to enforce the retention policy.

resource "aws_cloudwatch_log_group" "application" {
  name              = "/aws/apprunner/${local.service_name}/${aws_apprunner_service.this.service_id}/logs/application"
  retention_in_days = var.log_retention_days

  lifecycle {
    prevent_destroy = true
  }
}

# --- CloudWatch: SNS topic for alerts (conditional) ---

resource "aws_sns_topic" "alerts" {
  count = var.alarm_email != "" ? 1 : 0
  name  = "${local.service_name}-alerts"
}

resource "aws_sns_topic_subscription" "email" {
  count     = var.alarm_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.alerts[0].arn
  protocol  = "email"
  endpoint  = var.alarm_email
}

# --- CloudWatch: Metric filters (JSON audit log events) ---

resource "aws_cloudwatch_log_metric_filter" "login_failures" {
  name           = "${local.service_name}-login-failures"
  log_group_name = aws_cloudwatch_log_group.application.name
  pattern        = "{ $.event = \"auth.login.failure\" }"

  metric_transformation {
    name          = "LoginFailures"
    namespace     = "Nash/${var.environment}"
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_log_metric_filter" "rate_limit_blocks" {
  name           = "${local.service_name}-rate-limit-blocks"
  log_group_name = aws_cloudwatch_log_group.application.name
  pattern        = "{ $.event = \"rate_limit.exceeded\" }"

  metric_transformation {
    name          = "RateLimitBlocks"
    namespace     = "Nash/${var.environment}"
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_log_metric_filter" "server_errors" {
  name           = "${local.service_name}-server-errors"
  log_group_name = aws_cloudwatch_log_group.application.name
  pattern        = "{ $.event = \"http.error\" }"

  metric_transformation {
    name          = "ServerErrors"
    namespace     = "Nash/${var.environment}"
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_log_metric_filter" "account_lockouts" {
  name           = "${local.service_name}-account-lockouts"
  log_group_name = aws_cloudwatch_log_group.application.name
  pattern        = "{ $.event = \"auth.login.locked\" }"

  metric_transformation {
    name          = "AccountLockouts"
    namespace     = "Nash/${var.environment}"
    value         = "1"
    default_value = "0"
  }
}

# --- CloudWatch: Alarms (conditional on alarm_email) ---

resource "aws_cloudwatch_metric_alarm" "login_failures" {
  count               = var.alarm_email != "" ? 1 : 0
  alarm_name          = "${local.service_name}-high-login-failures"
  alarm_description   = "≥10 login failures in 5 minutes — possible brute force or credential stuffing"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "LoginFailures"
  namespace           = "Nash/${var.environment}"
  period              = 300
  statistic           = "Sum"
  threshold           = 10
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts[0].arn]
  ok_actions          = [aws_sns_topic.alerts[0].arn]
}

resource "aws_cloudwatch_metric_alarm" "rate_limit_blocks" {
  count               = var.alarm_email != "" ? 1 : 0
  alarm_name          = "${local.service_name}-high-rate-limit-blocks"
  alarm_description   = "≥20 rate limit blocks in 5 minutes — possible DoS"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "RateLimitBlocks"
  namespace           = "Nash/${var.environment}"
  period              = 300
  statistic           = "Sum"
  threshold           = 20
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts[0].arn]
  ok_actions          = [aws_sns_topic.alerts[0].arn]
}

resource "aws_cloudwatch_metric_alarm" "server_errors" {
  count               = var.alarm_email != "" ? 1 : 0
  alarm_name          = "${local.service_name}-server-errors"
  alarm_description   = "≥5 server errors (5xx) in 5 minutes"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "ServerErrors"
  namespace           = "Nash/${var.environment}"
  period              = 300
  statistic           = "Sum"
  threshold           = 5
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts[0].arn]
  ok_actions          = [aws_sns_topic.alerts[0].arn]
}

# App Runner native 5xx alarm (does not depend on application logs)
resource "aws_cloudwatch_metric_alarm" "apprunner_5xx" {
  count               = var.alarm_email != "" ? 1 : 0
  alarm_name          = "${local.service_name}-apprunner-5xx"
  alarm_description   = "≥10 App Runner 5xx responses in 5 minutes"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "5xxStatusResponses"
  namespace           = "AWS/AppRunner"
  period              = 300
  statistic           = "Sum"
  threshold           = 10
  treat_missing_data  = "notBreaching"

  dimensions = {
    ServiceName = local.service_name
    ServiceId   = aws_apprunner_service.this.service_id
  }

  alarm_actions = [aws_sns_topic.alerts[0].arn]
  ok_actions    = [aws_sns_topic.alerts[0].arn]
}
