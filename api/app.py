import json
import os

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.exceptions import TooManyRequests

from api.config import settings
from api.middleware.rate_limit import limiter
from api.services import audit_service

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "client", "dist")

import logging
logging.basicConfig(level=logging.INFO)

def create_app() -> Flask:
    logging.info("starting app")
    has_static = os.path.isdir(STATIC_DIR)
    app = Flask(__name__)
    logging.info("app created")
    app.secret_key = settings.jwt_secret
    limiter.init_app(app)
    logging.info("secret key set")
    CORS(app, supports_credentials=True, origins=[
        settings.domain_client,
        settings.domain_server,
        "http://localhost:3090",
        "http://localhost:3080",
    ])
    logging.info("cors set")
    from api.routes.config_routes import config_bp
    from api.routes.auth import auth_bp
    from api.routes.user import user_bp
    from api.routes.conversations import conversations_bp
    from api.routes.messages import messages_bp
    from api.routes.chat import chat_bp
    from api.routes.presets import presets_bp
    from api.routes.folders import folders_bp
    from api.routes.tags import tags_bp
    from api.routes.search import search_bp
    from api.routes.files import files_bp
    from api.routes.agents import agents_bp
    from api.routes.memories import memories_bp
    from api.routes.billing import billing_bp
    from api.routes.share import share_bp
    from api.routes.misc import misc_bp
    from api.routes.init import init_bp
    from api.routes.referrals import referrals_bp
    logging.info("routes imported")

    @app.route("/api/health")
    def health():
        import asyncio
        from api.services.async_runner import run_async
        try:
            run_async(asyncio.sleep(0), timeout=2)
        except Exception:
            return jsonify({"status": "degraded", "reason": "event_loop_stuck"}), 503
        return jsonify({"status": "ok"})

    @app.errorhandler(429)
    def ratelimit_handler(e):
        audit_service.emit(
            "rate_limit.exceeded",
            result="blocked",
            limit=str(getattr(e, "description", "")),
        )
        return jsonify({"message": "Too many requests. Please slow down and try again."}), 429

    @app.after_request
    def log_server_errors(response):
        if response.status_code >= 500:
            from flask import request as req
            audit_service.emit(
                "http.error",
                result="fail",
                status_code=response.status_code,
                path=req.path,
                method=req.method,
            )
        return response
    app.register_blueprint(config_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(conversations_bp)
    app.register_blueprint(messages_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(presets_bp)
    app.register_blueprint(folders_bp)
    app.register_blueprint(tags_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(files_bp)
    app.register_blueprint(agents_bp)
    app.register_blueprint(memories_bp)
    app.register_blueprint(billing_bp)
    app.register_blueprint(share_bp)
    app.register_blueprint(misc_bp)
    app.register_blueprint(init_bp)
    app.register_blueprint(referrals_bp)
    logging.info("routes registered")
    if has_static:
        @app.route("/", defaults={"path": ""})
        @app.route("/<path:path>")
        def serve_spa(path):
            full_path = os.path.join(STATIC_DIR, path)
            if path and os.path.isfile(full_path):
                return send_from_directory(STATIC_DIR, path)
            return send_from_directory(STATIC_DIR, "index.html")
    logging.info("spa registered")
    return app


if __name__ == "__main__":
    logging.info("starting app")
    app = create_app()
    logging.info("app created")
    app.run(host=settings.host, port=settings.port, debug=True)
    logging.info("app started")