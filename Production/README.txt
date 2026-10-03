EcoTextile Enterprises - Final Production Package

Run locally (Windows CMD):
python -m venv venv && call venv\Scripts\activate.bat && pip install -r requirements.txt && python app.py

Open: http://127.0.0.1:5000

Features included:
- 20 textile enterprise modules
- Tenant-scoped SQLite data
- Admin / Manager / Staff roles and audit trail
- Reports Center with PDF and Excel export
- Secure CSRF and login lockout controls
- Forgot Password with one-time, 30-minute reset tokens
- SMTP password-reset support via environment variables
- Local reset-link fallback when SMTP is not configured
- Company logo and fabric evidence uploads

Optional SMTP environment variables:
MAIL_SERVER
MAIL_PORT (default 587)
MAIL_USERNAME
MAIL_PASSWORD
MAIL_USE_TLS (default 1)
MAIL_FROM

Production:
Set ECOTEXTILE_SECRET_KEY to a strong random secret, ECOTEXTILE_PRODUCTION=1,
and configure SMTP before deploying publicly. Do not use the development secret
or Flask debug mode in production.


NEW MOBILE/CLIENT DEMO FEATURES
- Public User Manual: /manual (also linked from login screen)
- Mobile responsive dashboard with collapsible module navigation
- Product Scanner: mobile camera QR/barcode detection where browser supports BarcodeDetector
- External USB/Bluetooth barcode scanner input with Enter-to-lookup
- Camera access in production generally requires HTTPS


=== Update: Telemetry Delete + Report Import ===
- Module Telemetry Ledger now includes a tenant-scoped Delete action with CSRF validation and audit logging.
- Reports Center now supports CSV/XLSX batch-data import (up to 1,000 rows per import).
- Recommended import columns: Buyer Name, Fabric Type, Quantity KG, QC Grade, Status, Rack, Row, Bin, BOM Cost.
- Flask LAN binding is preserved on 0.0.0.0:5000.
