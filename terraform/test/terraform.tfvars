# NEVER commit terraform.tfvars to git
# Nash test env - no custom domain, uses App Runner default URL

environment = "test"
ecr_repository_name = "nash-test"

# Secrets (same as dev for now)
backboard_api_key      = "espr_cYodyuTRrijktQ8PPhJ963lLefqTgz33f2kohbUDo8w"
backboard_assistant_id = "08c97c97-148c-429b-b9f6-73e0f3a6dacf"
jwt_secret             = "16f8c0ef4a5d391b26034086c628469d3f9f497f08163ab9b40137092f2909ef"
jwt_refresh_secret     = "eaa5191f2914e30b9387fd84e254e4ba6fc51b4654968a9b0803b456a54b8418"

domain_client = "https://nsn5zknjhm.us-west-2.awsapprunner.com"
domain_server = "https://nsn5zknjhm.us-west-2.awsapprunner.com"

sso_secret = "JY6NVLpmxJ36WSE-SuHLoc74KXA-i9aSxl-bywrvocY"

# No custom domain for test - avoids conflict with dev
custom_domain = ""

google_client_id     = "214822149604-pdr5obklov8es58qa7hm136lt624go7a.apps.googleusercontent.com"
google_client_secret = "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"

stripe_price_id_plus      = "price_1T7HNPIJ2nAqB0Fj9HD18mq6"
stripe_price_id_unlimited = "price_1T7HPiIJ2nAqB0FjoZj7B8kA"
stripe_webhook_secret     = "whsec_4LWPNRjigSVbIaQWT2DaJRXUT86iM5QZ"
stripe_secret_key         = "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"

backboard_auth_assistant_id = "d3f4254d-c874-43e6-bf52-9a952a1f772b"
