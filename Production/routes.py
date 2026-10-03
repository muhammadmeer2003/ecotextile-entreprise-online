import hashlib
import os
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin
import smtplib
from email.message import EmailMessage
from functools import wraps

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from models import db_connection

routes_bp = Blueprint("routes", __name__)

LOGIN_TRACKER = {}
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_SECONDS = 15 * 60

MODULES = [
    {"id": 1, "name": "Production & Batch Control", "code": "PROD", "description": "Create production batches, DPP tokens, quantities and fabric evidence."},
    {"id": 2, "name": "Procurement & Suppliers", "code": "PROC", "description": "Log supplier references, purchase commitments and inbound material actions."},
    {"id": 3, "name": "Bill of Materials", "code": "BOM", "description": "Track material components, consumption assumptions and costing checkpoints."},
    {"id": 4, "name": "Cutting & Planning", "code": "CUT", "description": "Record cutting-plan references, marker efficiency and planning notes."},
    {"id": 5, "name": "Dyeing & Processing", "code": "DYE", "description": "Capture wet-processing jobs, chemistry references and process telemetry."},
    {"id": 6, "name": "Finishing & Treatment", "code": "FIN", "description": "Track finishing jobs, treatment references and completion evidence."},
    {"id": 7, "name": "Quality Control", "code": "QC", "description": "Update batch quality checkpoints and record inspection outcomes."},
    {"id": 8, "name": "Production Planning", "code": "PPC", "description": "Log planning references, capacity signals and schedule decisions."},
    {"id": 9, "name": "Maintenance & OEE", "code": "OEE", "description": "Capture maintenance work, downtime and equipment telemetry."},
    {"id": 10, "name": "Warehouse & Rack Mapping", "code": "WH", "description": "Assign rack, row and bin coordinates to a production batch."},
    {"id": 11, "name": "Inventory & Stock", "code": "INV", "description": "Record stock movements, counts and inventory control notes."},
    {"id": 12, "name": "Sales & Order Desk", "code": "SLS", "description": "Log customer/order desk actions and commercial follow-ups."},
    {"id": 13, "name": "CBAM & Carbon Telemetry", "code": "CBAM", "description": "Calculate the configured emissions metric and target tax estimate."},
    {"id": 14, "name": "Sustainability & DPP", "code": "DPP", "description": "Track digital product passport evidence and sustainability checkpoints."},
    {"id": 15, "name": "Compliance & Audit", "code": "AUDIT", "description": "Log compliance controls, audit evidence and corrective actions."},
    {"id": 16, "name": "Finance & Costing", "code": "FINC", "description": "Record financial checkpoints, cost references and budget controls."},
    {"id": 17, "name": "HR & Workforce", "code": "HR", "description": "Capture workforce operational references, shifts and staffing notes."},
    {"id": 18, "name": "Dispatch & Logistics", "code": "LOG", "description": "Record dispatch references, carrier actions and shipment telemetry."},
    {"id": 19, "name": "Customer Service", "code": "CS", "description": "Log customer tickets, escalations and resolution checkpoints."},
    {"id": 20, "name": "Executive Control Tower", "code": "CTRL", "description": "Consolidate executive telemetry, risk signals and management actions."},
]


def csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def valid_csrf():
    supplied = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
    expected = session.get("csrf_token")
    return bool(supplied and expected and secrets.compare_digest(supplied, expected))


def login_key():
    forwarded = request.headers.get("X-Forwarded-For", "")
    ip = forwarded.split(",")[0].strip() if forwarded else request.remote_addr or "unknown"
    email = request.form.get("email", "").strip().lower()
    return f"{ip}|{email}"


def is_locked(key):
    state = LOGIN_TRACKER.get(key)
    if not state:
        return False, 0
    now = time.time()
    remaining = int(state["locked_until"] - now)
    if remaining > 0:
        return True, remaining
    LOGIN_TRACKER.pop(key, None)
    return False, 0


def register_failed_login(key):
    now = time.time()
    state = LOGIN_TRACKER.setdefault(key, {"failures": 0, "locked_until": 0})
    state["failures"] += 1
    if state["failures"] >= MAX_FAILED_ATTEMPTS:
        state["locked_until"] = now + LOCKOUT_SECONDS
        state["failures"] = 0


def clear_failed_login(key):
    LOGIN_TRACKER.pop(key, None)


def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    with db_connection() as connection:
        return connection.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()


def audit_event(action, entity_type=None, entity_id=None, details=None):
    uid = session.get("user_id")
    ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or request.remote_addr or "unknown"
    with db_connection() as connection:
        # A stale browser session must never make logout fail. If the user row
        # no longer exists, keep the audit record with a NULL user_id.
        if uid is not None:
            exists = connection.execute("SELECT 1 FROM users WHERE id=?", (uid,)).fetchone()
            if not exists:
                uid = None
        connection.execute(
            "INSERT INTO audit_logs (user_id, action, entity_type, entity_id, details, ip_address) VALUES (?, ?, ?, ?, ?, ?)",
            (uid, action, entity_type, str(entity_id) if entity_id is not None else None, details, ip),
        )


def role_required(*roles):
    allowed = {r.upper() for r in roles}
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = current_user()
            if not user:
                session.clear()
                flash("Your secure session is no longer valid. Please sign in again.", "warning")
                return redirect(url_for("routes.login"))
            if user["role"].upper() not in allowed:
                flash("You do not have permission to access this area.", "error")
                return redirect(url_for("routes.dashboard"))
            return view(*args, **kwargs)
        return wrapped
    return decorator


def authenticated(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Your secure session has expired. Please sign in again.", "warning")
            return redirect(url_for("routes.login"))
        return view(*args, **kwargs)
    return wrapped


def save_image(file_storage, destination, allowed):
    if not file_storage or not file_storage.filename:
        return None
    filename = secure_filename(file_storage.filename)
    extension = filename.rsplit(".", 1)[1].lower() if "." in filename else ""
    if extension not in allowed:
        raise ValueError("Only JPG, JPEG, PNG, or WEBP image files are accepted.")
    final_name = f"{uuid.uuid4().hex}.{extension}"
    os.makedirs(destination, exist_ok=True)
    file_storage.save(os.path.join(destination, final_name))
    return final_name


def image_url(folder, filename):
    if not filename:
        return None
    # Do not emit a broken image URL when a database references an image
    # that was not carried over with the project folder.
    full_path = os.path.join(current_app.static_folder, "uploads", folder, filename)
    if not os.path.isfile(full_path):
        return None
    return url_for("static", filename=f"uploads/{folder}/{filename}")


def fallback_avatar(label):
    return label


def create_dpp_hash(user_id, buyer, fabric, quantity):
    seed = f"{user_id}|{buyer}|{fabric}|{quantity}|{time.time_ns()}|{secrets.token_hex(16)}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def module_for(module_id):
    return next((module for module in MODULES if module["id"] == module_id), MODULES[0])


def log_module_event(user_id, module_id, reference, value, notes):
    with db_connection() as connection:
        connection.execute(
            "INSERT INTO module_logs (user_id, module_id, reference, value, notes) VALUES (?, ?, ?, ?, ?)",
            (user_id, module_id, reference, value, notes),
        )


@routes_bp.app_context_processor
def inject_globals():
    return {"csrf_token": csrf_token}




def send_password_reset_email(recipient, reset_url):
    host = current_app.config.get("MAIL_SERVER") or os.environ.get("MAIL_SERVER")
    username = current_app.config.get("MAIL_USERNAME") or os.environ.get("MAIL_USERNAME")
    password = current_app.config.get("MAIL_PASSWORD") or os.environ.get("MAIL_PASSWORD")
    port = int(current_app.config.get("MAIL_PORT") or os.environ.get("MAIL_PORT", "587"))
    use_tls = str(current_app.config.get("MAIL_USE_TLS", os.environ.get("MAIL_USE_TLS", "1"))).lower() in {"1", "true", "yes", "on"}
    sender = current_app.config.get("MAIL_FROM") or os.environ.get("MAIL_FROM") or username
    if not host or not sender:
        return False
    msg = EmailMessage()
    msg["Subject"] = "EcoTextile Enterprises — Password Reset"
    msg["From"] = sender
    msg["To"] = recipient
    msg.set_content(f"A password reset was requested for your EcoTextile account.\n\nOpen this link within 30 minutes to create a new password:\n{reset_url}\n\nIf you did not request this, you can ignore this email.")
    with smtplib.SMTP(host, port, timeout=15) as smtp:
        if use_tls:
            smtp.starttls()
        if username and password:
            smtp.login(username, password)
        smtp.send_message(msg)
    return True


@routes_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        if not valid_csrf():
            flash("Security token expired. Refresh the page and try again.", "error")
            return redirect(url_for("routes.forgot_password"))
        email = request.form.get("email", "").strip().lower()
        if not email or "@" not in email:
            flash("Please enter a valid work email.", "error")
            return redirect(url_for("routes.forgot_password"))
        generic = "If that email is registered, a password reset link has been sent."
        with db_connection() as connection:
            user = connection.execute("SELECT id,email FROM users WHERE email=?", (email,)).fetchone()
            if not user:
                flash(generic, "success")
                return redirect(url_for("routes.login"))
            raw_token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
            expires = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
            connection.execute("DELETE FROM password_reset_tokens WHERE user_id=? AND used_at IS NULL", (user["id"],))
            connection.execute("INSERT INTO password_reset_tokens (user_id,token_hash,expires_at) VALUES (?,?,?)", (user["id"], token_hash, expires))
        reset_url = urljoin(request.host_url, url_for("routes.reset_password", token=raw_token))
        try:
            sent = send_password_reset_email(user["email"], reset_url)
        except Exception:
            sent = False
        if sent:
            flash(generic, "success")
        else:
            # Safe local-development fallback: show the link only when SMTP is not configured.
            smtp_configured = bool(current_app.config.get("MAIL_SERVER") or os.environ.get("MAIL_SERVER"))
            if smtp_configured:
                flash("We could not send the reset email right now. Please check the mail configuration and try again.", "error")
            else:
                flash("SMTP is not configured. For local testing, use this reset link: " + reset_url, "success")
        return redirect(url_for("routes.login"))
    return render_template("forgot_password.html")


@routes_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    with db_connection() as connection:
        reset = connection.execute("SELECT id,user_id,expires_at,used_at FROM password_reset_tokens WHERE token_hash=?", (token_hash,)).fetchone()
    valid = False
    if reset and not reset["used_at"]:
        try:
            valid = datetime.fromisoformat(reset["expires_at"]) > datetime.now(timezone.utc)
        except ValueError:
            valid = False
    if not valid:
        flash("This password reset link is invalid or has expired. Please request a new one.", "error")
        return redirect(url_for("routes.forgot_password"))
    if request.method == "POST":
        if not valid_csrf():
            flash("Security token expired. Refresh the page and try again.", "error")
            return redirect(url_for("routes.reset_password", token=token))
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        if len(password) < 8:
            flash("New password must be at least 8 characters.", "error")
            return redirect(url_for("routes.reset_password", token=token))
        if password != confirm:
            flash("Passwords do not match.", "error")
            return redirect(url_for("routes.reset_password", token=token))
        with db_connection() as connection:
            fresh = connection.execute("SELECT user_id FROM password_reset_tokens WHERE id=? AND token_hash=? AND used_at IS NULL", (reset["id"], token_hash)).fetchone()
            if not fresh:
                flash("This reset link has already been used. Please request a new one.", "error")
                return redirect(url_for("routes.forgot_password"))
            connection.execute("UPDATE users SET password_hash=? WHERE id=?", (generate_password_hash(password), fresh["user_id"]))
            connection.execute("UPDATE password_reset_tokens SET used_at=? WHERE user_id=? AND used_at IS NULL", (datetime.now(timezone.utc).isoformat(), fresh["user_id"]))
        flash("Password changed successfully. You can now sign in with your new password.", "success")
        return redirect(url_for("routes.login"))
    return render_template("reset_password.html")


@routes_bp.route("/", methods=["GET"])
def index():
    if session.get("user_id"):
        return redirect(url_for("routes.dashboard"))
    return redirect(url_for("routes.login"))


@routes_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("routes.dashboard"))
    if request.method == "POST":
        if not valid_csrf():
            flash("Security token expired. Refresh the page and try again.", "error")
            return redirect(url_for("routes.login"))
        key = login_key()
        locked, remaining = is_locked(key)
        if locked:
            flash(f"System lock active for this login identity. Try again in {remaining // 60 + 1} minute(s).", "error")
            return redirect(url_for("routes.login"))

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        with db_connection() as connection:
            user = connection.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

        if not user or not check_password_hash(user["password_hash"], password):
            register_failed_login(key)
            locked, _ = is_locked(key)
            if locked:
                flash("Five consecutive unauthorized attempts detected. This login identity is locked for 15 minutes.", "error")
            else:
                flash("Invalid work email or private key.", "error")
            return redirect(url_for("routes.login"))

        clear_failed_login(key)
        session.clear()
        session.permanent = True
        session["user_id"] = user["id"]
        session["company"] = user["company_name"]
        session["company_logo_path"] = user["company_logo_path"]
        session["role"] = user["role"]
        session["csrf_token"] = secrets.token_urlsafe(32)
        audit_event("LOGIN", "USER", user["id"], "Successful login")
        return redirect(url_for("routes.dashboard"))

    return render_template("login.html")


@routes_bp.route("/manual", methods=["GET"])
def user_manual():
    """Public client-facing demo and user manual."""
    return render_template("manual.html")


@routes_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        if not valid_csrf():
            flash("Security token expired. Refresh the page and try again.", "error")
            return redirect(url_for("routes.register"))
        company_name = request.form.get("company_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        logo = request.files.get("company_logo")

        if len(company_name) < 2 or len(email) < 5 or "@" not in email or len(password) < 8:
            flash("Company name, valid work email, and an 8+ character private key are required.", "error")
            return redirect(url_for("routes.register"))

        logo_filename = None
        try:
            logo_filename = save_image(logo, current_app.config["LOGO_UPLOAD_DIR"], current_app.config["ALLOWED_IMAGE_EXTENSIONS"])
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("routes.register"))

        with db_connection() as connection:
            try:
                cursor = connection.execute(
                    "INSERT INTO users (company_name, email, password_hash, company_logo_path) VALUES (?, ?, ?, ?)",
                    (company_name, email, generate_password_hash(password), logo_filename),
                )
                user_id = cursor.lastrowid
            except Exception as exc:
                if logo_filename:
                    try:
                        os.remove(os.path.join(current_app.config["LOGO_UPLOAD_DIR"], logo_filename))
                    except OSError:
                        pass
                if "UNIQUE constraint failed: users.email" in str(exc):
                    flash("That work email is already registered.", "error")
                else:
                    flash("Registration could not be completed. Please review the submitted data.", "error")
                return redirect(url_for("routes.register"))

        session.clear()
        session.permanent = True
        session["user_id"] = user_id
        session["company"] = company_name
        session["company_logo_path"] = logo_filename
        session["role"] = "ADMIN"
        session["csrf_token"] = secrets.token_urlsafe(32)
        audit_event("REGISTER", "COMPANY", user_id, "Company profile created; initial account role ADMIN")
        flash("Company node registered successfully.", "success")
        return redirect(url_for("routes.dashboard"))

    return render_template("register.html")


@routes_bp.route("/logout", methods=["POST"])
def logout():
    if valid_csrf():
        if session.get("user_id"):
            audit_event("LOGOUT", "USER", session.get("user_id"), "User signed out")
        session.clear()
    return redirect(url_for("routes.login"))


@routes_bp.route("/delete_order/<int:order_id>", methods=["POST"])
@authenticated
def delete_order(order_id):
    if not valid_csrf():
        flash("Security token validation failed.", "error")
        return redirect(url_for("routes.dashboard", module=1))
    user_id = session["user_id"]
    with db_connection() as connection:
        order = connection.execute("SELECT * FROM orders WHERE id=? AND user_id=?", (order_id, user_id)).fetchone()
        if not order:
            flash("Batch node was not found in your tenant ledger.", "error")
            return redirect(url_for("routes.dashboard", module=1))
        connection.execute("DELETE FROM orders WHERE id=?", (order_id,))
    audit_event("DELETE", "BATCH", order_id, "Production batch deleted")
    flash(f"Batch #{order_id} was deleted from the enterprise ledger.", "success")
    return redirect(url_for("routes.dashboard", module=1))


@routes_bp.route("/delete_module_log/<int:log_id>", methods=["POST"])
@authenticated
def delete_module_log(log_id):
    if not valid_csrf():
        flash("Security token validation failed.", "error")
        return redirect(url_for("routes.dashboard"))

    user_id = session["user_id"]
    with db_connection() as connection:
        log = connection.execute(
            "SELECT id, module_id, reference FROM module_logs WHERE id=? AND user_id=?",
            (log_id, user_id),
        ).fetchone()
        if not log:
            flash("Telemetry entry was not found in your tenant ledger.", "error")
            return redirect(url_for("routes.dashboard"))
        connection.execute(
            "DELETE FROM module_logs WHERE id=? AND user_id=?",
            (log_id, user_id),
        )

    audit_event(
        "DELETE",
        "MODULE_EVENT",
        log_id,
        f"Module {log['module_id']} telemetry entry deleted; Reference {log['reference']}",
    )
    flash(f"Telemetry entry #{log_id} deleted successfully.", "success")
    return redirect(url_for("routes.dashboard"))


@routes_bp.route("/dashboard", methods=["GET", "POST"])
@authenticated
def dashboard():
    user_id = session["user_id"]
    active_module = request.args.get("module", 1, type=int)
    if active_module not in range(1, 21):
        active_module = 1

    if request.method == "POST":
        if not valid_csrf():
            flash("Security token validation failed. Refresh the page and retry.", "error")
            return redirect(url_for("routes.dashboard", module=active_module))
        action = request.form.get("action", "")
        try:
            if action == "create_order":
                buyer = request.form.get("buyer_name", "").strip()
                fabric = request.form.get("fabric_type", "").strip()
                quantity = float(request.form.get("quantity_kg", "0"))
                qc_grade = request.form.get("qc_grade", "PENDING").strip().upper() or "PENDING"
                bom_cost = float(request.form.get("total_bom_cost", "0") or 0)
                image = request.files.get("fabric_image")
                if not buyer or not fabric or quantity <= 0 or bom_cost < 0:
                    raise ValueError("Buyer, fabric type, positive quantity, and a valid BOM cost are required.")
                image_filename = save_image(image, current_app.config["FABRIC_UPLOAD_DIR"], current_app.config["ALLOWED_IMAGE_EXTENSIONS"])
                dpp_hash = create_dpp_hash(user_id, buyer, fabric, quantity)
                with db_connection() as connection:
                    connection.execute(
                        "INSERT INTO orders (user_id, buyer_name, fabric_type, quantity_kg, dpp_hash, order_status, qc_grade, total_bom_cost, fabric_image_path) VALUES (?, ?, ?, ?, ?, 'ACTIVE', ?, ?, ?)",
                        (user_id, buyer, fabric, quantity, dpp_hash, qc_grade, bom_cost, image_filename),
                    )
                audit_event("CREATE", "BATCH", dpp_hash[:16], f"Production batch created for buyer {buyer}")
                flash("Production batch created and DPP hash generated.", "success")

            elif action == "warehouse_update":
                order_id = int(request.form.get("order_id", "0"))
                rack = request.form.get("warehouse_rack", "").strip()
                row = request.form.get("warehouse_row", "").strip()
                bin_code = request.form.get("warehouse_bin", "").strip()
                with db_connection() as connection:
                    cursor = connection.execute(
                        "UPDATE orders SET warehouse_rack=?, warehouse_row=?, warehouse_bin=? WHERE id=? AND user_id=?",
                        (rack, row, bin_code, order_id, user_id),
                    )
                if cursor.rowcount == 0:
                    raise ValueError("The selected batch does not belong to this tenant.")
                log_module_event(user_id, 10, f"BATCH-{order_id}", f"{rack}-{row}-{bin_code}", "Warehouse coordinate update")
                audit_event("UPDATE", "BATCH", order_id, f"Warehouse mapped to {rack}-{row}-{bin_code}")
                flash("Warehouse rack/row/bin mapping saved.", "success")

            elif action == "cbam_calculate":
                order_id = int(request.form.get("order_id", "0"))
                electricity = float(request.form.get("electricity", "0"))
                fuel = float(request.form.get("fuel", "0"))
                if electricity < 0 or fuel < 0:
                    raise ValueError("Energy inputs cannot be negative.")
                emissions_metric = (electricity * 0.45) + (fuel * 2.68)
                target_tax_usd = emissions_metric * 0.085
                with db_connection() as connection:
                    order = connection.execute("SELECT id FROM orders WHERE id=? AND user_id=?", (order_id, user_id)).fetchone()
                    if not order:
                        raise ValueError("The selected batch was not found in this tenant.")
                    connection.execute(
                        "INSERT INTO cbam_logs (order_id, emissions_metric, target_tax_usd) VALUES (?, ?, ?)",
                        (order_id, emissions_metric, target_tax_usd),
                    )
                log_module_event(user_id, 13, f"BATCH-{order_id}", f"${target_tax_usd:.4f}", f"Emissions metric {emissions_metric:.4f}")
                audit_event("CALCULATE", "CBAM", order_id, f"Emissions {emissions_metric:.4f}; target tax {target_tax_usd:.4f}")
                flash(f"CBAM telemetry calculated: emissions {emissions_metric:.4f}; target tax ${target_tax_usd:.4f}.", "success")

            elif action == "qc_update":
                order_id = int(request.form.get("order_id", "0"))
                grade = request.form.get("qc_grade", "PENDING").strip().upper()
                status = request.form.get("order_status", "ACTIVE").strip().upper()
                allowed_grades = {"A", "B", "C", "REJECTED", "PENDING"}
                allowed_status = {"ACTIVE", "IN PRODUCTION", "READY", "HOLD", "CANCELLED"}
                if grade not in allowed_grades or status not in allowed_status:
                    raise ValueError("Invalid QC grade or order status.")
                with db_connection() as connection:
                    cursor = connection.execute(
                        "UPDATE orders SET qc_grade=?, order_status=? WHERE id=? AND user_id=?",
                        (grade, status, order_id, user_id),
                    )
                if cursor.rowcount == 0:
                    raise ValueError("The selected batch was not found in this tenant.")
                log_module_event(user_id, 7, f"BATCH-{order_id}", grade, f"Order status {status}")
                audit_event("UPDATE", "QC", order_id, f"Grade {grade}; status {status}")
                flash("Quality and batch status updated.", "success")

            elif action == "module_event":
                module_id = int(request.form.get("module_id", "0"))
                reference = request.form.get("reference", "").strip()
                value = request.form.get("value", "").strip()
                notes = request.form.get("notes", "").strip()
                if module_id not in range(2, 21) or module_id in {7, 10, 13}:
                    raise ValueError("Use the dedicated processing panel for this module.")
                if not reference or not value:
                    raise ValueError("Reference and value are required for an operational module event.")
                log_module_event(user_id, module_id, reference, value, notes)
                audit_event("CREATE", "MODULE_EVENT", module_id, f"Reference {reference}")
                flash(f"Module {module_id} operational event logged.", "success")
            else:
                raise ValueError("Unknown dashboard action.")
        except (ValueError, TypeError) as exc:
            flash(str(exc), "error")
        except Exception:
            flash("The requested operation could not be committed to the enterprise ledger.", "error")
        return redirect(url_for("routes.dashboard", module=active_module))

    with db_connection() as connection:
        orders = connection.execute(
            "SELECT o.*, u.company_name FROM orders o JOIN users u ON u.id=o.user_id WHERE o.user_id=? ORDER BY o.id DESC",
            (user_id,),
        ).fetchall()
        logs = connection.execute(
            "SELECT ml.*, m.name AS module_name FROM module_logs ml JOIN (SELECT 1 AS id, 'Production & Batch Control' AS name UNION ALL SELECT 2, 'Procurement & Suppliers' UNION ALL SELECT 3, 'Bill of Materials' UNION ALL SELECT 4, 'Cutting & Planning' UNION ALL SELECT 5, 'Dyeing & Processing' UNION ALL SELECT 6, 'Finishing & Treatment' UNION ALL SELECT 7, 'Quality Control' UNION ALL SELECT 8, 'Production Planning' UNION ALL SELECT 9, 'Maintenance & OEE' UNION ALL SELECT 10, 'Warehouse & Rack Mapping' UNION ALL SELECT 11, 'Inventory & Stock' UNION ALL SELECT 12, 'Sales & Order Desk' UNION ALL SELECT 13, 'CBAM & Carbon Telemetry' UNION ALL SELECT 14, 'Sustainability & DPP' UNION ALL SELECT 15, 'Compliance & Audit' UNION ALL SELECT 16, 'Finance & Costing' UNION ALL SELECT 17, 'HR & Workforce' UNION ALL SELECT 18, 'Dispatch & Logistics' UNION ALL SELECT 19, 'Customer Service' UNION ALL SELECT 20, 'Executive Control Tower') m ON m.id=ml.module_id WHERE ml.user_id=? ORDER BY ml.id DESC LIMIT 60",
            (user_id,),
        ).fetchall()
        cbam = connection.execute(
            "SELECT c.*, o.buyer_name, o.fabric_type FROM cbam_logs c JOIN orders o ON o.id=c.order_id WHERE o.user_id=? ORDER BY c.id DESC LIMIT 30",
            (user_id,),
        ).fetchall()

    order_rows = []
    for order in orders:
        row = dict(order)
        row["image_url"] = image_url("fabric_batches", row.get("fabric_image_path"))
        row["avatar"] = fallback_avatar("FAB Node")
        row["short_hash"] = row["dpp_hash"][:12].upper()
        order_rows.append(row)

    return render_template(
        "dashboard.html",
        company=session.get("company", "EcoTextile Partner Mills"),
        role=session.get("role", "STAFF"),
        company_logo=image_url("logos", session.get("company_logo_path")),
        modules=MODULES,
        active_module=active_module,
        active_module_data=module_for(active_module),
        orders=order_rows,
        module_logs=logs,
        cbam_logs=cbam,
        order_count=len(order_rows),
        active_count=sum(1 for row in order_rows if row["order_status"] == "ACTIVE"),
        total_kg=sum(float(row["quantity_kg"]) for row in order_rows),
    )


@routes_bp.route("/api/scan", methods=["POST"])
@authenticated
def api_scan():
    if not valid_csrf():
        return jsonify({"ok": False, "message": "Security token validation failed."}), 403
    payload = request.get_json(silent=True) or {}
    code = str(payload.get("code", "")).strip()
    if not code:
        return jsonify({"ok": False, "message": "Scan value is required."}), 400
    user_id = session["user_id"]
    with db_connection() as connection:
        order = connection.execute(
            "SELECT * FROM orders WHERE user_id=? AND (dpp_hash=? OR CAST(id AS TEXT)=? OR dpp_hash LIKE ?)",
            (user_id, code, code, f"{code}%"),
        ).fetchone()
    if not order:
        return jsonify({"ok": False, "message": "No product/batch node matched that scan value."}), 404
    data = dict(order)
    data["dpp_hash"] = data["dpp_hash"]
    data["fabric_image"] = image_url("fabric_batches", data.get("fabric_image_path"))
    data["fallback_avatar"] = "FAB Node"
    return jsonify({"ok": True, "product": data})


@routes_bp.route("/admin/users", methods=["GET", "POST"])
@authenticated
@role_required("ADMIN")
def admin_users():
    if request.method == "POST":
        if not valid_csrf():
            flash("Security token validation failed.", "error")
            return redirect(url_for("routes.admin_users"))
        action = request.form.get("action", "")
        if action == "change_role":
            user_id = request.form.get("user_id", type=int)
            role = request.form.get("role", "").upper()
            if role not in {"ADMIN", "MANAGER", "STAFF"} or not user_id:
                flash("Invalid user role request.", "error")
                return redirect(url_for("routes.admin_users"))
            if user_id == session.get("user_id") and role != "ADMIN":
                flash("You cannot remove your own Admin role.", "error")
                return redirect(url_for("routes.admin_users"))
            with db_connection() as connection:
                target = connection.execute("SELECT id,email FROM users WHERE id=?", (user_id,)).fetchone()
                if not target:
                    flash("User not found.", "error")
                    return redirect(url_for("routes.admin_users"))
                connection.execute("UPDATE users SET role=? WHERE id=?", (role, user_id))
            audit_event("ROLE_CHANGE", "USER", user_id, f"Role changed to {role}")
            flash("User role updated.", "success")
        elif action == "create_user":
            company_name = request.form.get("company_name", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            role = request.form.get("role", "STAFF").upper()
            if len(company_name) < 2 or "@" not in email or len(password) < 8 or role not in {"ADMIN", "MANAGER", "STAFF"}:
                flash("Company name, valid email, 8+ character password, and valid role are required.", "error")
                return redirect(url_for("routes.admin_users"))
            try:
                with db_connection() as connection:
                    cursor = connection.execute("INSERT INTO users (company_name,email,password_hash,company_logo_path,role) VALUES (?,?,?,?,?)", (company_name,email,generate_password_hash(password),None,role))
                    new_id = cursor.lastrowid
                audit_event("CREATE", "USER", new_id, f"User {email} created with role {role}")
                flash("User account created successfully.", "success")
            except Exception:
                flash("Could not create user. The email may already be registered.", "error")
        else:
            flash("Unknown admin action.", "error")
        return redirect(url_for("routes.admin_users"))

    with db_connection() as connection:
        users = connection.execute("SELECT id,company_name,email,role FROM users ORDER BY id").fetchall()
        audits = connection.execute("SELECT a.*, u.email FROM audit_logs a LEFT JOIN users u ON u.id=a.user_id WHERE a.user_id IN (SELECT id FROM users WHERE company_name=(SELECT company_name FROM users WHERE id=?)) ORDER BY a.id DESC LIMIT 100", (session.get("user_id"),)).fetchall()
    return render_template("admin_users.html", users=users, audits=audits, company=session.get("company"), role=session.get("role"))
