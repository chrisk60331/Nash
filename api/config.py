import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    host: str = "localhost"
    port: int = 3080

    backboard_api_key: str 
    backboard_assistant_id: str 
    backboard_auth_assistant_id: str 
    closer_notes_warm_lead_assistant_id: str = ""

    jwt_secret: str
    jwt_refresh_secret: str
    jwt_access_expiry_seconds: int = 15 * 60
    jwt_refresh_expiry_seconds: int = 14 * 24 * 60 * 60

    google_client_id: str
    google_client_secret: str
    google_callback_url: str = "/oauth/google/callback"

    stripe_secret_key: str 
    stripe_webhook_secret: str
    stripe_price_id_plus: str
    stripe_price_id_unlimited: str
    stripe_metered_price_id_plus: str = ""
    stripe_metered_price_id_unlimited: str = ""
    stripe_overage_tokens_per_unit: int = 100_000
    stripe_overage_unit_price_usd: float = 1.0

    token_credits_per_usd: int = 1_000_000
    referral_bonus_usd: float = 5.0

    free_included_tokens: int = 250_000
    plus_included_tokens: int = 500_000
    pro_included_tokens: int = 3_000_000

    app_title: str = "Nash"
    domain_client: str = "http://localhost:3090"
    domain_server: str = "http://localhost:3080"
    help_and_faq_url: str = "/docs"
    status_page_url: str = "https://crimson-rabbit-6111.statusgator.app"
    support_url: str = "mailto:support@backboard.io"
    allow_email_login: bool = True
    allow_registration: bool = True
    allow_social_login: bool = True
    allow_social_registration: bool = True
    allow_shared_links: bool = True
    domain_hellonash: str = "http://www.hellonash.ai"

    model_config = {"env_file": os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")}


settings = Settings()
