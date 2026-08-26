# Netfi Billing System

A cloud-ready hotspot billing and management system for MikroTik networks.

## Included in this first working foundation
- Admin login
- Customer records
- Internet packages
- Voucher creation and redemption tracking
- Active session tracking
- SQLite database for simple startup
- REST endpoints prepared for MikroTik/payment integrations

## Run locally
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:8000`.

The first administrator is created from `NETFI_ADMIN_EMAIL` and `NETFI_ADMIN_PASSWORD`. If those variables are absent, the local development defaults are `admin@netfi.local` and `ChangeMe123!`.

**Change the default password before any public deployment.**

## Production
Set `NETFI_SECRET_KEY`, `NETFI_ADMIN_EMAIL`, `NETFI_ADMIN_PASSWORD`, and `DATABASE_URL` or mount persistent storage before production deployment.
