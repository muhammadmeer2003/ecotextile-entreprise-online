import os
import secrets
from datetime import timedelta

from flask import Flask

from models import init_db
from routes import routes_bp
from reports import reports_bp

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_ROOT = os.path.join(BASE_DIR, "static", "uploads")
LOGO_UPLOAD_DIR = os.path.join(UPLOAD_ROOT, "logos")
FABRIC_UPLOAD_DIR = os.path.join(UPLOAD_ROOT, "fabric_batches")

os.makedirs(LOGO_UPLOAD_DIR, exist_ok=True)
os.makedirs(FABRIC_UPLOAD_DIR, exist_ok=True)

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("ECOTEXTILE_SECRET_KEY") or "dev-only-change-this-secret",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("ECOTEXTILE_PRODUCTION", "0") == "1",
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
