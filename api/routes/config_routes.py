import yaml
import os
import tomllib

from flask import Blueprint, jsonify

from api.config import settings
from api.services.org_security_service import get_org_security_config

config_bp = Blueprint("config", __name__)

def _read_version() -> str:
    try:
        pyproject_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "pyproject.toml",
        )
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
        return data.get("project", {}).get("version", "unknown")
    except Exception:
        return "unknown"

_VERSION = _read_version()

_endpoint_config: dict | None = None

FREE_TIER_PROVIDERS = {"Cohere", "Cerebras", "Featherless"}
MODEL_TIERS = ("free", "fast", "powerful")


def _load_endpoint_config() -> dict:
    global _endpoint_config
    if _endpoint_config is not None:
        return _endpoint_config

    yaml_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "librechat.yaml")
    try:
        with open(yaml_path, "r") as f:
            _endpoint_config = yaml.safe_load(f)
    except FileNotFoundError:
        _endpoint_config = {}
    return _endpoint_config


def _build_endpoints_response() -> dict:
    cfg = _load_endpoint_config()
    custom_endpoints = cfg.get("endpoints", {}).get("custom", [])

    result = {}
    all_models = []
    for ep in custom_endpoints:
        name = ep.get("name", "")
        models = ep.get("models", {}).get("default", [])
        result[name] = {
            "type": "custom",
            "name": name,
            "modelDisplayLabel": ep.get("modelDisplayLabel", name),
            "models": models,
            "titleConvo": ep.get("titleConvo", True),
            "titleModel": ep.get("titleModel", ""),
        }
        all_models.extend(models)

    result["agents"] = {
        "type": "agents",
        "name": "agents",
        "disableBuilder": False,
        "models": all_models or ["default"],
    }

    return result


def _build_models_response() -> dict:
    cfg = _load_endpoint_config()
    custom_endpoints = cfg.get("endpoints", {}).get("custom", [])

    result = {}
    all_models = []
    for ep in custom_endpoints:
        name = ep.get("name", "")
        models = _extract_model_entries(ep)
        result[name] = models
        all_models.extend(models)

    result["agents"] = all_models or ["default"]
    return result


def _extract_model_entries(endpoint_config: dict) -> list[dict]:
    raw_models = endpoint_config.get("models", {}).get("default", [])
    selector_tiers = endpoint_config.get("selectorTiers", {})

    normalized_tiers = {
        tier: set(selector_tiers.get(tier, []))
        for tier in MODEL_TIERS
    }

    models = []
    for raw_model in raw_models:
        if isinstance(raw_model, dict):
            model_name = raw_model.get("name", "")
            explicit_tiers = raw_model.get("tiers", []) or []
        else:
            model_name = raw_model
            explicit_tiers = []

        if not model_name:
            continue

        tiers = set(explicit_tiers)
        for tier in MODEL_TIERS:
            if model_name in normalized_tiers[tier]:
                tiers.add(tier)

        model_entry = {"name": model_name}
        if tiers:
            model_entry["tiers"] = [tier for tier in MODEL_TIERS if tier in tiers]
        models.append(model_entry)

    return models


@config_bp.route("/api/config", methods=["GET"])
def get_config():
    org_security_config = get_org_security_config()
    return jsonify({
        "appTitle": settings.app_title,
        "socialLogins": ["google"],
        "discordLoginEnabled": False,
        "facebookLoginEnabled": False,
        "githubLoginEnabled": False,
        "googleLoginEnabled": True,
        "openidLoginEnabled": False,
        "appleLoginEnabled": False,
        "samlLoginEnabled": False,
        "openidLabel": "",
        "openidImageUrl": "",
        "openidAutoRedirect": False,
        "samlLabel": "",
        "samlImageUrl": "",
        "serverDomain": settings.domain_server,
        "emailLoginEnabled": settings.allow_email_login,
        "registrationEnabled": settings.allow_registration,
        "socialLoginEnabled": settings.allow_social_login,
        "passwordResetEnabled": False,
        "emailEnabled": False,
        "showBirthdayIcon": False,
        "helpAndFaqURL": settings.help_and_faq_url,
        "statusPageURL": settings.status_page_url,
        "supportURL": settings.support_url,
        "requireMfaForAllUsers": org_security_config.requireMfaForAllUsers,
        "sharedLinksEnabled": settings.allow_shared_links,
        "publicSharedLinksEnabled": settings.allow_shared_links,
        "instanceProjectId": "nash-2",
        "interface": {
            "webSearch": True,
            "endpointsMenu": True,
            "modelSelect": True,
            "parameters": True,
            "sidePanel": True,
            "presets": True,
            "bookmarks": True,
            "agents": {"use": True, "create": True, "share": False, "public": False},
            "prompts": True,
            "multiConvo": False,
            "artifacts": False,
            "codeBrowser": False,
            "fileCitations": True,
            "remoteAgents": {"use": False, "create": False, "share": False, "public": False},
            "privacyPolicy": {
                "externalUrl": "/privacy",
            },
            "termsOfService": {
                "externalUrl": "/terms",
                "modalAcceptance": True,
                "modalTitle": "Terms of Service",
                "modalContent": (
                    "By using Nash, you agree to our [Terms of Service](/terms) and "
                    "[Privacy Policy](/privacy).\n\n"
                    "**Key points:**\n"
                    "- You must be 13 or older to use Nash\n"
                    "- Don't use Nash to generate harmful or illegal content\n"
                    "- We don't sell your data or use your conversations to train AI models\n"
                    "- AI responses may be inaccurate — always verify important information\n"
                    "- Paid plans renew monthly and can be cancelled anytime\n\n"
                    "You can read our full [Terms of Service](/terms) and [Privacy Policy](/privacy) "
                    "for complete details."
                ),
            },
        },
        "billing": {
            "enabled": True,
            "freeModels": [p.lower() for p in FREE_TIER_PROVIDERS],
            "priceIdPlus": settings.stripe_price_id_plus,
            "priceIdUnlimited": settings.stripe_price_id_unlimited,
            "plans": {
                "free": {
                    "tokens": settings.free_included_tokens,
                    "label": "Free",
                    "overageEnabled": False,
                },
                "plus": {
                    "tokens": settings.plus_included_tokens,
                    "label": "Plus",
                    "priceId": settings.stripe_price_id_plus,
                    "overageEnabled": bool(settings.stripe_metered_price_id_plus),
                    "overagePriceId": settings.stripe_metered_price_id_plus,
                    "overageTokensPerUnit": settings.stripe_overage_tokens_per_unit,
                    "overageUnitPriceUsd": settings.stripe_overage_unit_price_usd,
                },
                "pro": {
                    "tokens": settings.pro_included_tokens,
                    "label": "Pro",
                    "priceId": settings.stripe_price_id_unlimited,
                    "overageEnabled": bool(settings.stripe_metered_price_id_unlimited),
                    "overagePriceId": settings.stripe_metered_price_id_unlimited,
                    "overageTokensPerUnit": settings.stripe_overage_tokens_per_unit,
                    "overageUnitPriceUsd": settings.stripe_overage_unit_price_usd,
                },
            },
        },
        "balance": {
            "enabled": True,
            "tokenCreditsPerUsd": settings.token_credits_per_usd,
        },
        "referrals": {
            "enabled": True,
            "rewardUsd": settings.referral_bonus_usd,
        },
    })


@config_bp.route("/api/endpoints", methods=["GET"])
def get_endpoints():
    return jsonify(_build_endpoints_response())


@config_bp.route("/api/models", methods=["GET"])
def get_models():
    return jsonify(_build_models_response())


@config_bp.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "version": _VERSION})
