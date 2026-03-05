import yaml
import os

from flask import Blueprint, jsonify

from api.config import settings

config_bp = Blueprint("config", __name__)

_endpoint_config: dict | None = None

FREE_TIER_PROVIDERS = {"Cohere", "Cerebras", "Featherless"}


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
        models = ep.get("models", {}).get("default", [])
        result[name] = models
        all_models.extend(models)

    result["agents"] = all_models or ["default"]
    return result


@config_bp.route("/api/config", methods=["GET"])
def get_config():
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
        "emailLoginEnabled": False,
        "registrationEnabled": False,
        "socialLoginEnabled": settings.allow_social_login,
        "passwordResetEnabled": False,
        "emailEnabled": False,
        "showBirthdayIcon": False,
        "helpAndFaqURL": settings.help_and_faq_url,
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
        },
        "billing": {
            "enabled": True,
            "freeModels": [p.lower() for p in FREE_TIER_PROVIDERS],
            "priceIdPlus": settings.stripe_price_id_plus,
            "priceIdUnlimited": settings.stripe_price_id_unlimited,
            "plans": {
                "free": {"tokens": settings.free_included_tokens, "label": "Free"},
                "plus": {"tokens": settings.plus_included_tokens, "label": "Plus", "priceId": settings.stripe_price_id_plus},
                "pro": {"tokens": settings.pro_included_tokens, "label": "Pro", "priceId": settings.stripe_price_id_unlimited},
            },
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
    return jsonify({"status": "ok"})
