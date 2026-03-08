"""CSRF protection for cookie-authenticated endpoints.

All API endpoints that use the Authorization: Bearer header are inherently
CSRF-safe — cross-site requests cannot set custom headers. The only endpoints
that rely on the refreshToken cookie for authentication are:
  - GET/POST /api/auth/refresh
  - GET/POST /api/auth/logout

For these, the SameSite=Lax cookie attribute already blocks cross-site POST
requests. The remaining vector is cross-site GET navigation which could carry
the cookie. We address this with two complementary checks:

  1. Sec-Fetch-Site header (set automatically by all modern browsers):
     Reject requests where Sec-Fetch-Site is explicitly "cross-site".
     Allow "same-origin", "same-site", "none", and absent (curl / API clients).

  2. Origin / Referer header cross-check for POST requests:
     When a POST arrives with an Origin header that doesn't match the server
     domain, reject it. This covers older browsers that predate Sec-Fetch-Site.

Usage:
    from api.middleware.csrf import csrf_protect

    @bp.route("/api/auth/refresh", methods=["POST"])
    @csrf_protect
    def refresh(): ...
"""
import functools
import logging

from flask import request, jsonify

from api.config import settings

logger = logging.getLogger(__name__)

_ALLOWED_FETCH_SITES = {"same-origin", "same-site", "none", ""}


def csrf_protect(f):
    """Decorator that blocks cross-site requests to cookie-authenticated endpoints."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        # Check 1: Sec-Fetch-Site (modern browsers always set this)
        fetch_site = request.headers.get("Sec-Fetch-Site", "").lower()
        if fetch_site not in _ALLOWED_FETCH_SITES:
            logger.warning(
                "[csrf] blocked cross-site request: path=%s Sec-Fetch-Site=%s",
                request.path, fetch_site,
            )
            return jsonify({"error": "Cross-site request blocked"}), 403

        # Check 2: Origin header mismatch on state-changing methods
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            origin = request.headers.get("Origin", "")
            if origin:
                allowed_origins = {
                    settings.domain_client.rstrip("/"),
                    settings.domain_server.rstrip("/"),
                    "http://localhost:3090",
                    "http://localhost:3080",
                }
                if origin.rstrip("/") not in allowed_origins:
                    logger.warning(
                        "[csrf] blocked mismatched origin: path=%s origin=%s",
                        request.path, origin,
                    )
                    return jsonify({"error": "Cross-site request blocked"}), 403

        return f(*args, **kwargs)
    return decorated
