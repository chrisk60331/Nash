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
    BACKBOARD_API_KEY    = var.backboard_api_key
    BACKBOARD_ASSISTANT_ID = var.backboard_assistant_id
    CREDS_KEY            = var.creds_key
    CREDS_IV             = var.creds_iv
    JWT_SECRET           = var.jwt_secret
    JWT_REFRESH_SECRET   = var.jwt_refresh_secret
    ADMIN_RESET_SECRET   = var.admin_reset_secret
    SSO_SECRET           = var.sso_secret
    STRIPE_SECRET_KEY    = var.stripe_secret_key
    STRIPE_WEBHOOK_SECRET = var.stripe_webhook_secret
  }

  secrets = { for k, v in local._all_secrets : k => v if v != "" }

  environment_variables = merge(
    {
      HOST         = "0.0.0.0"
      PORT         = tostring(var.container_port)
      NODE_ENV     = "production"
      CONSOLE_JSON = "true"
      ENVIRONMENT  = var.environment
      AWS_REGION   = var.aws_region
      ALLOW_REGISTRATION = true
      LOGIN_WINDOW=1
      LOGIN_MAX=50
      ALLOW_UNVERIFIED_EMAIL_LOGIN=true
      SESSION_EXPIRY=1209600000
      REFRESH_TOKEN_EXPIRY=1209600000
    },
    var.domain_client != "" ? { DOMAIN_CLIENT = var.domain_client } : {},
    var.domain_server != "" ? { DOMAIN_SERVER = var.domain_server } : {},
    var.app_title != "" ? { APP_TITLE = var.app_title } : {},
    var.stripe_price_id_plus != "" ? { STRIPE_PRICE_ID_PLUS = var.stripe_price_id_plus } : {},
    var.stripe_price_id_unlimited != "" ? { STRIPE_PRICE_ID_UNLIMITED = var.stripe_price_id_unlimited } : {},
    var.plus_included_tokens != "500000" ? { PLUS_INCLUDED_TOKENS = var.plus_included_tokens } : {},
  )
}

module "ecr" {
  source = "./modules/ecr"

  repository_name      = var.app_name
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

  custom_domain = var.custom_domain
}
