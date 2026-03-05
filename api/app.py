import os

from flask import Flask, send_from_directory
from flask_cors import CORS

from api.config import settings

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "client", "dist")


def create_app() -> Flask:
    has_static = os.path.isdir(STATIC_DIR)
    app = Flask(
        __name__,
        static_folder=STATIC_DIR if has_static else None,
        static_url_path="" if has_static else None,
    )
    app.secret_key = settings.jwt_secret

    CORS(app, supports_credentials=True, origins=[
        settings.domain_client,
        settings.domain_server,
        "http://localhost:3090",
        "http://localhost:3080",
    ])

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

    if has_static:
        @app.route("/", defaults={"path": ""})
        @app.route("/<path:path>")
        def serve_spa(path):
            full_path = os.path.join(STATIC_DIR, path)
            if path and os.path.isfile(full_path):
                return send_from_directory(STATIC_DIR, path)
            return send_from_directory(STATIC_DIR, "index.html")

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host=settings.host, port=settings.port, debug=True)
