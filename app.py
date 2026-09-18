import os
from flask import Flask, send_from_directory
from flask_login import LoginManager
from flask_mail import Mail
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from config import Config
from models import db, User

login_manager = LoginManager()
mail = Mail()
limiter = Limiter(key_func=get_remote_address)

def create_app(config_class=Config):
    app = Flask(__name__, static_folder="static", static_url_path="/static")
    app.config.from_object(config_class)

    # Private local staging area for song uploads awaiting admin review
    os.makedirs(os.path.join(app.config["PENDING_UPLOAD_FOLDER"], "audio"), exist_ok=True)
    os.makedirs(os.path.join(app.config["PENDING_UPLOAD_FOLDER"], "covers"), exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    limiter.init_app(app)

    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "info"

    # Security headers
    @app.after_request
    def add_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        # CSP - adjust as needed
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https:; "
            "media-src 'self' https:; "
            "connect-src 'self';"
        )
        response.headers["Content-Security-Policy"] = csp
        return response

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(user_id)

    # Register blueprints
    from routes.public import bp as public_bp
    from routes.auth import bp as auth_bp
    from routes.artist import bp as artist_bp
    from routes.admin import bp as admin_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(artist_bp, url_prefix="/artist")
    app.register_blueprint(admin_bp, url_prefix="/admin")

    # Context processors
    _genre_cache = {"data": None, "expires": 0}

    @app.context_processor
    def inject_globals():
        import time
        from models import Song, Artist
        now = time.time()
        if _genre_cache["data"] is None or now > _genre_cache["expires"]:
            genres = db.session.query(Song.genre).distinct().all()
            _genre_cache["data"] = [g[0] for g in genres if g[0]]
            _genre_cache["expires"] = now + 300  # 5 minutes - genres change rarely
        return {
            "current_year": __import__("datetime").datetime.now().year,
            "site_name": "Ateker Music",
            "genres": _genre_cache["data"],
        }

    # Error handlers - all render a friendly page and, for 500s, log the
    # real exception server-side without ever showing it to the visitor.
    def _error_page(code, title, message):
        from flask import render_template
        return render_template("errors/error.html", code=code, title=title, message=message), code

    @app.errorhandler(400)
    def bad_request(error):
        return _error_page(400, "Bad request", "We couldn't understand that request.")

    @app.errorhandler(401)
    def unauthorized(error):
        return _error_page(401, "Sign in required", "Please log in to access this page.")

    @app.errorhandler(403)
    def forbidden(error):
        return _error_page(403, "Access forbidden", "You don't have permission to view this page.")

    @app.errorhandler(404)
    def not_found(error):
        return _error_page(404, "Page not found", "The page you're looking for doesn't exist or may have been removed.")

    @app.errorhandler(429)
    def ratelimit_handler(e):
        return _error_page(429, "Too many requests", "Please slow down and try again in a moment.")

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        app.logger.error(f"Unhandled server error: {error}")
        return _error_page(500, "Something went wrong", "We're looking into it. Please try again shortly.")

    # Create tables
    with app.app_context():
        db.create_all()

    return app
