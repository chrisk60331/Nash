terraform {
  required_version = ">= 1.4.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

locals {
  service_name = "${var.app_name}-${var.environment}"

  _all_secrets = {
    BACKBOARD_API_KEY      = var.backboard_api_key
    BACKBOARD_ASSISTANT_ID = var.backboard_assistant_id
    JWT_SECRET             = var.jwt_secret
    JWT_REFRESH_SECRET     = var.jwt_refresh_secret
    SSO_SECRET             = var.sso_secret
    STRIPE_SECRET_KEY      = var.stripe_secret_key
    STRIPE_WEBHOOK_SECRET  = var.stripe_webhook_secret
    GOOGLE_CLIENT_ID       = var.google_client_id
    GOOGLE_CLIENT_SECRET   = var.google_client_secret
  }

  secrets = { for k, v in local._all_secrets : k => v if v != "" }

  environment_variables = merge(
    {
      HOST                       = "0.0.0.0"
      PORT                       = tostring(var.container_port)
      ENVIRONMENT                = var.environment
      AWS_REGION                 = var.aws_region
      GOOGLE_CALLBACK_URL        = var.google_callback_url
      ALLOW_SOCIAL_LOGIN         = "true"
      ALLOW_SOCIAL_REGISTRATION  = "true"
      ALLOW_SHARED_LINKS         = "true"
      STRIPE_PRICE_ID_PLUS       = var.stripe_price_id_plus
      STRIPE_PRICE_ID_UNLIMITED  = var.stripe_price_id_unlimited
      STRIPE_OVERAGE_TOKENS_PER_UNIT = var.stripe_overage_tokens_per_unit
      STRIPE_METERED_PRICE_ID_PLUS = var.stripe_metered_price_id_plus
      STRIPE_METERED_PRICE_ID_UNLIMITED = var.stripe_metered_price_id_unlimited
      PLUS_INCLUDED_TOKENS       = var.plus_included_tokens
      BACKBOARD_AUTH_ASSISTANT_ID = var.backboard_auth_assistant_id
      HELP_AND_FAQ_URL            = "/docs"
      CLOSER_NOTES_WARM_LEAD_ASSISTANT_ID="190c9e11-27c0-4e9e-855a-87136aa7e509"

    },
    var.domain_client != "" ? { DOMAIN_CLIENT = var.domain_client } : {},
    var.domain_server != "" ? { DOMAIN_SERVER = var.domain_server } : {},
    var.app_title != "" ? { APP_TITLE = var.app_title } : {},
  )
}

module "ecr" {
  source = "./modules/ecr"

  repository_name      = "${var.app_name}-${var.environment}"
  environment          = var.environment
  retain_count         = var.ecr_retain_count
  untagged_expire_days = var.ecr_untagged_expire_days
}

module "ssm_secrets" {
  source = "./modules/ssm-secrets"

  app_name    = var.app_name
  environment = var.environment
  secrets     = local.secrets
}

module "apprunner" {
  source = "./modules/apprunner"

  app_name           = var.app_name
  environment        = var.environment
  aws_region         = var.aws_region
  ecr_repository_url = module.ecr.repository_url
  image_tag          = var.ecr_image_tag
  container_port     = var.container_port
  cpu                = var.cpu
  memory             = var.memory
  min_instances      = var.min_instances
  max_instances      = var.max_instances
  max_concurrency    = var.max_concurrency

  health_check_path                = var.health_check_path
  health_check_interval            = var.health_check_interval
  health_check_timeout             = var.health_check_timeout
  health_check_healthy_threshold   = var.health_check_healthy_threshold
  health_check_unhealthy_threshold = var.health_check_unhealthy_threshold

  environment_variables = local.environment_variables
  ssm_secret_arns       = module.ssm_secrets.arns

  custom_domain           = var.custom_domain
  custom_domain_hellonash = var.custom_domain_hellonash
  log_retention_days      = var.log_retention_days
  alarm_email        = var.alarm_email
}
