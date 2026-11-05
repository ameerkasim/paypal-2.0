import os
import json
import uuid
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone

import requests
from flask import Flask, jsonify, render_template, request
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "dev-only-change-me")
DATABASE = os.getenv("DATABASE_PATH", "payai.db")
CURRENCY = os.getenv("PAYPAL_CURRENCY", "USD").upper()
PAYPAL_MODE = os.getenv("PAYPAL_MODE", "sandbox").lower()
PAYPAL_BASE = (
    "https://api-m.sandbox.paypal.com"
    if PAYPAL_MODE == "sandbox"
    else "https://api-m.paypal.com"
)

def db():
    import sqlite3
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection

def init_db():
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS invoices (
                id TEXT PRIMARY KEY,
                customer_name TEXT NOT NULL,
                customer_email TEXT NOT NULL,
                description TEXT NOT NULL,
                amount TEXT NOT NULL,
                currency TEXT NOT NULL,
                ai_quote TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING',
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id TEXT NOT NULL UNIQUE,
                paypal_order_id TEXT NOT NULL UNIQUE,
                capture_id TEXT,
                status TEXT NOT NULL,
                amount TEXT NOT NULL,
                currency TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(invoice_id) REFERENCES invoices(id)
            )
        """)

def money(value):
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError):
        raise ValueError("Enter a valid amount.")
    if not amount.is_finite() or amount <= 0 or amount > Decimal("10000.00"):
        raise ValueError("Amount must be greater than 0 and no more than 10,000.")
    return amount

def generate_ai_quote(description, amount, customer_name):
    """Generate a quote explanation. The customer-entered amount remains authoritative."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return (
            f"Hello {customer_name},\n\n"
            f"Thank you for your enquiry about: {description}.\n"
            f"The proposed total is {CURRENCY} {amount:.2f}. "
            "This quotation covers the requested service as described. "
            "Please review the scope with the provider before payment.\n\n"
            "This is a locally generated demo quotation because GEMINI_API_KEY is not configured."
        ), "fallback"

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        prompt = f"""
You are PayAI, a concise business quotation writing assistant.
Create a professional quotation explanation using the details below.
Do not change, recalculate, discount, or invent the amount. Do not claim taxes
or deliverables that were not specified. State that the provider must confirm
scope and applicable taxes before accepting payment.
Customer: {customer_name}
Service requested: {description}
Fixed quoted amount: {CURRENCY} {amount:.2f}
Return plain text, 100 words maximum.
"""
        response = client.models.generate_content(model=model, contents=prompt)
        text = (response.text or "").strip()
        if not text:
            raise RuntimeError("Gemini returned an empty response.")
        return text, "gemini"
    except Exception:
        app.logger.exception("Gemini request failed")
        return (
            f"Quotation for {customer_name}\n\nService: {description}\n"
            f"Fixed amount: {CURRENCY} {amount:.2f}\n\n"
            "AI quotation generation was unavailable. This fallback text does not "
            "represent a Gemini-generated response."
        ), "fallback"

def paypal_access_token():
    client_id = os.getenv("PAYPAL_CLIENT_ID")
    secret = os.getenv("PAYPAL_CLIENT_SECRET")
    if not client_id or not secret:
        raise RuntimeError("PayPal Sandbox credentials are not configured.")
    response = requests.post(
        f"{PAYPAL_BASE}/v1/oauth2/token",
        auth=(client_id, secret),
        headers={"Accept": "application/json", "Accept-Language": "en_US"},
        data={"grant_type": "client_credentials"},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()["access_token"]

def paypal_request(method, path, payload=None, request_id=None):
    token = paypal_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    if request_id:
        headers["PayPal-Request-Id"] = request_id
    response = requests.request(
        method, f"{PAYPAL_BASE}{path}", headers=headers,
        json=payload, timeout=25
    )
    if not response.ok:
        app.logger.error("PayPal API error %s: %s", response.status_code, response.text[:1000])
        raise RuntimeError(f"PayPal returned HTTP {response.status_code}. Check server logs and Sandbox credentials.")
    return response.json()

@app.get("/")
def index():
    paypal_client_id = os.getenv("PAYPAL_CLIENT_ID", "")
    return render_template(
        "index.html",
        paypal_client_id=paypal_client_id,
        currency=CURRENCY,
        paypal_mode=PAYPAL_MODE,
    )

@app.get("/api/health")
def health():
    return jsonify({
        "ok": True,
        "paypal_mode": PAYPAL_MODE,
        "paypal_configured": bool(os.getenv("PAYPAL_CLIENT_ID") and os.getenv("PAYPAL_CLIENT_SECRET")),
        "gemini_configured": bool(os.getenv("GEMINI_API_KEY")),
        "currency": CURRENCY,
    })

@app.post("/api/quotes")
def create_quote():
    data = request.get_json(silent=True) or {}
    name = str(data.get("customer_name", "")).strip()[:80]
    email = str(data.get("customer_email", "")).strip()[:120]
    description = str(data.get("description", "")).strip()[:500]
    try:
        amount = money(data.get("amount"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if not name or not email or "@" not in email or not description:
        return jsonify({"error": "Enter a customer name, valid email and service description."}), 400

    quote, ai_source = generate_ai_quote(description, amount, name)
    invoice_id = str(uuid.uuid4())[:12].upper()
    created_at = datetime.now(timezone.utc).isoformat()
    with db() as conn:
        conn.execute("""
            INSERT INTO invoices
            (id, customer_name, customer_email, description, amount, currency, ai_quote, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'PENDING', ?)
        """, (invoice_id, name, email, description, str(amount), CURRENCY, quote, created_at))

    return jsonify({
        "invoice_id": invoice_id,
        "customer_name": name,
        "description": description,
        "amount": str(amount),
        "currency": CURRENCY,
        "quote": quote,
        "ai_source": ai_source,
        "status": "PENDING",
    }), 201

@app.get("/api/invoices")
def list_invoices():
    with db() as conn:
        rows = conn.execute("""
            SELECT id, customer_name, description, amount, currency, status, created_at
            FROM invoices ORDER BY created_at DESC LIMIT 50
        """).fetchall()
    return jsonify([dict(row) for row in rows])

@app.post("/api/paypal/create-order")
def create_paypal_order():
    data = request.get_json(silent=True) or {}
    invoice_id = str(data.get("invoice_id", "")).strip()
    with db() as conn:
        invoice = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
        payment = conn.execute("SELECT * FROM payments WHERE invoice_id = ?", (invoice_id,)).fetchone()

    if not invoice:
        return jsonify({"error": "Invoice not found. Generate a quotation first."}), 404
    if invoice["status"] == "PAID" or payment:
        return jsonify({"error": "This invoice has already been paid."}), 409

    payload = {
        "intent": "CAPTURE",
        "purchase_units": [{
            "reference_id": invoice_id,
            "custom_id": invoice_id,
            "description": invoice["description"][:127],
            "amount": {
                "currency_code": invoice["currency"],
                "value": invoice["amount"],
            },
        }],
        "application_context": {
            "brand_name": "PayAI Demo",
            "user_action": "PAY_NOW",
            "shipping_preference": "NO_SHIPPING",
        },
    }
    try:
        order = paypal_request("POST", "/v2/checkout/orders", payload, str(uuid.uuid4()))
        return jsonify({"id": order["id"]})
    except Exception as exc:
        app.logger.exception("Could not create PayPal order")
        return jsonify({"error": str(exc)}), 502

@app.post("/api/paypal/capture-order")
def capture_paypal_order():
    data = request.get_json(silent=True) or {}
    order_id = str(data.get("order_id", "")).strip()
    invoice_id = str(data.get("invoice_id", "")).strip()
    if not order_id or not invoice_id:
        return jsonify({"error": "Missing PayPal order or invoice ID."}), 400

    with db() as conn:
        invoice = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
        existing = conn.execute("SELECT * FROM payments WHERE invoice_id = ?", (invoice_id,)).fetchone()

    if not invoice:
        return jsonify({"error": "Invoice not found."}), 404
    if existing:
        return jsonify({"status": "COMPLETED", "message": "Payment was already recorded."})

    try:
        # Verify the order with PayPal before capturing. Never trust browser-supplied amounts.
        order = paypal_request("GET", f"/v2/checkout/orders/{order_id}")
        purchase_units = order.get("purchase_units", [])
        if not purchase_units or purchase_units[0].get("custom_id") != invoice_id:
            return jsonify({"error": "PayPal order does not match this invoice."}), 400
        order_amount = purchase_units[0].get("amount", {})
        if (order_amount.get("currency_code") != invoice["currency"]
                or order_amount.get("value") != invoice["amount"]):
            return jsonify({"error": "PayPal order amount does not match this invoice."}), 400
        if order.get("status") == "COMPLETED":
            capture_response = order
        else:
            capture_response = paypal_request(
                "POST", f"/v2/checkout/orders/{order_id}/capture", {}, str(uuid.uuid4())
            )

        if capture_response.get("status") != "COMPLETED":
            return jsonify({"error": "PayPal has not marked this payment as completed.",
                            "paypal_status": capture_response.get("status")}), 402

        capture_id = None
        try:
            capture_id = capture_response["purchase_units"][0]["payments"]["captures"][0]["id"]
        except (KeyError, IndexError, TypeError):
            pass

        with db() as conn:
            conn.execute("UPDATE invoices SET status = 'PAID' WHERE id = ?", (invoice_id,))
            conn.execute("""
                INSERT OR IGNORE INTO payments
                (invoice_id, paypal_order_id, capture_id, status, amount, currency, created_at)
                VALUES (?, ?, ?, 'COMPLETED', ?, ?, ?)
            """, (invoice_id, order_id, capture_id, invoice["amount"], invoice["currency"],
                  datetime.now(timezone.utc).isoformat()))
        return jsonify({"status": "COMPLETED", "capture_id": capture_id,
                        "invoice_id": invoice_id, "amount": invoice["amount"],
                        "currency": invoice["currency"]})
    except Exception as exc:
        app.logger.exception("PayPal capture failed")
        return jsonify({"error": str(exc)}), 502

@app.get("/api/payments")
def list_payments():
    with db() as conn:
        rows = conn.execute("""
            SELECT invoice_id, paypal_order_id, capture_id, status, amount, currency, created_at
            FROM payments ORDER BY created_at DESC LIMIT 50
        """).fetchall()
    return jsonify([dict(row) for row in rows])

init_db()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=os.getenv("FLASK_DEBUG") == "1")
