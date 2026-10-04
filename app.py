import os
import secrets
from datetime import timedelta

from flask import Flask, request
from flask.sessions import SecureCookieSessionInterface
from werkzeug.middleware.proxy_fix import ProxyFix

from models import init_db
from routes import routes_bp
from reports import reports_bp

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_ROOT = os.path.join(BASE_DIR, "static", "uploads")
LOGO_UPLOAD_DIR = os.path.join(UPLOAD_ROOT, "logos")
FABRIC_UPLOAD_DIR = os.path.join(UPLOAD_ROOT, "fabric_batches")

os.makedirs(LOGO_UPLOAD_DIR, exist_ok=True)
os.makedirs(FABRIC_UPLOAD_DIR, exist_ok=True)

class SchemeAwareSession(SecureCookieSessionInterface):
    """Mark the session cookie Secure only when the request really is HTTPS.
    A hard Secure flag on plain http://LAN-IP made mobile browsers silently drop
    the cookie, so CSRF failed and login looped."""
    def get_cookie_secure(self, app):
        return request.is_secure


app = Flask(__name__)
app.session_interface = SchemeAwareSession()
if os.environ.get("ECOTEXTILE_BEHIND_PROXY", "1") == "1":
    # Cloudflare / ngrok / nginx terminate HTTPS and forward X-Forwarded-Proto.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
app.config.update(
    SECRET_KEY=os.environ.get("ECOTEXTILE_SECRET_KEY") or "dev-only-change-this-secret",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    MAX_CONTENT_LENGTH=8 * 1024 * 1024,
    LOGO_UPLOAD_DIR=LOGO_UPLOAD_DIR,
    FABRIC_UPLOAD_DIR=FABRIC_UPLOAD_DIR,
    ALLOWED_IMAGE_EXTENSIONS={"jpg", "jpeg", "png", "webp"},
)

init_db()
app.register_blueprint(routes_bp)
app.register_blueprint(reports_bp)


@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(self), microphone=()"
    response.headers["Cache-Control"] = "no-store"
    return response


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=os.environ.get("FLASK_DEBUG", "0") == "1", port=int(os.environ.get("PORT", "5000")))
