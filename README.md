# PayAI — AI Smart Payment Assistant

PayAI is a beginner-friendly Flask web application that combines Google Gemini with PayPal Sandbox checkout. A business user enters customer and service details, generates an AI-assisted quotation, and collects a test payment through PayPal.

> **Educational prototype:** this project is configured for PayPal Sandbox. It is not a production payment platform. Do not enter real card details or use live PayPal credentials.

## Features

- AI-assisted quotation writing using the official Google Gen AI Python SDK.
- A clearly labelled local fallback quotation if no Gemini API key is configured or the AI service is temporarily unavailable.
- Invoice creation and SQLite persistence.
- PayPal JavaScript Checkout button.
- Server-side PayPal Orders v2 order creation and capture.
- Server-side validation that the approved PayPal order matches the stored invoice ID, amount and currency.
- Invoice and payment history endpoints.
- Basic automated tests.

The customer-entered amount is authoritative. Gemini writes explanatory text only; it does not set or modify the amount.

## Technology

- Python 3.10+
- Flask
- Google Gen AI SDK (`google-genai`)
- Gemini API
- PayPal JavaScript SDK
- PayPal REST Orders v2 API
- SQLite
- HTML, CSS and JavaScript

## 1. Requirements

Install Python 3.10 or newer. You also need:
- A free PayPal Developer account.
- A PayPal Sandbox app with a Client ID and Secret.
- A Google AI Studio API key (optional for local fallback mode; required for Gemini-generated quotations).

## 2. Get PayPal Sandbox credentials

1. Visit https://developer.paypal.com/ and sign in.
2. Open **Apps & Credentials**.
3. Select **Sandbox**.
4. Create an app (or use a sandbox app you already created).
5. Copy the Sandbox **Client ID** and **Secret**.
6. In the Developer Dashboard, create or use a Sandbox Personal test account as the buyer. The Sandbox Business account is the merchant.
7. Use the Sandbox Personal account credentials at the PayPal checkout window. Do not use your real PayPal login.

PayPal's official Orders API integration guide: https://developer.paypal.com/whats-an-order/

## 3. Get a Gemini API key

1. Visit https://aistudio.google.com/apikey
2. Create an API key.
3. Copy it into your local `.env` file. Do not publish it.

Google's Python SDK documentation: https://googleapis.github.io/python-genai/

## 4. Install and run (Windows)

Open Command Prompt or PowerShell in the project folder:

```powershell
py -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
```

Open `.env` in a text editor and fill in:
- `PAYPAL_CLIENT_ID`
- `PAYPAL_CLIENT_SECRET`
- `GEMINI_API_KEY`

Keep `PAYPAL_MODE=sandbox`. For a first UI test, Gemini can be left blank; the app will label the generated text as a demo fallback.

Start the app:

```powershell
python app.py
```

Open http://127.0.0.1:5000

## 5. Install and run (macOS / Linux)

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` with your own credentials, then:

```bash
python app.py
```

Open http://127.0.0.1:5000

## 6. Test a Sandbox payment

1. Confirm the header says `SANDBOX ENVIRONMENT`.
2. Create a quotation with a test customer name, email, service description and small amount (for example USD 5.00).
3. The quotation appears in the preview panel.
4. Click the PayPal button.
5. Log in using the Sandbox Personal buyer test account, not your real PayPal account.
6. Approve the payment.
7. The Flask server retrieves the order from PayPal, checks its invoice reference, amount and currency, then captures it.
8. The invoice status should change from `PENDING` to `PAID`.

If the PayPal button does not appear, check the Client ID in `.env`, ensure `PAYPAL_MODE=sandbox`, restart Flask and reload the page.

## 7. Run automated tests

```bash
python -m unittest discover -s tests -v
```

Tests cover health status, quotation creation, invalid amounts and rejection of unknown invoices. PayPal network calls are not performed by these unit tests. Complete the manual Sandbox payment test above for end-to-end verification.

## API routes

| Method | Route | Purpose |
|---|---|---|
| GET | `/` | Web dashboard |
| GET | `/api/health` | Configuration status |
| POST | `/api/quotes` | Generate and save a quotation |
| GET | `/api/invoices` | List recent invoices |
| POST | `/api/paypal/create-order` | Create a PayPal order from a stored invoice |
| POST | `/api/paypal/capture-order` | Verify and capture an approved order |
| GET | `/api/payments` | List recorded payments |

## GitHub publication

Create a new **Public** repository named `payai-smart-payment-assistant`.

From the project folder:

```bash
git init
git add .
git commit -m "Initial PayAI Flask application"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/payai-smart-payment-assistant.git
git push -u origin main
```

Replace `YOUR-USERNAME` with your GitHub username. The `.gitignore` excludes `.env` and local database files. Verify before pushing that no API keys or secrets are in the commit.

The MIT license is included in `LICENSE`.

## Suggested repository structure

```text
payai-smart-payment-assistant/
├── app.py
├── requirements.txt
├── .env.example
├── .gitignore
├── LICENSE
├── README.md
├── templates/
│   └── index.html
├── static/
│   └── style.css
└── tests/
    └── test_app.py
```

## 8. Demo video plan (2 minutes 30 seconds)

**0:00–0:15 — Introduction**
"Hello, this is PayAI, an AI Smart Payment Assistant. It combines Google Gemini and PayPal Sandbox to simplify business quotations and test payments."

**0:15–0:45 — Create a quotation**
Show the dashboard. Enter a customer name, email, service description and agreed amount. Click Generate AI quotation. Explain that Gemini generates the quotation text while the entered price remains fixed.

**0:45–1:15 — Explain the invoice**
Show the quotation preview and invoice ID. Point out the amount and pending status. Show the recent invoices table.

**1:15–1:55 — PayPal Sandbox checkout**
Click the PayPal button. Sign in with the Sandbox Personal buyer account. Approve the test payment. Do not show passwords or secret keys in the recording.

**1:55–2:15 — Payment verification**
Return to PayAI. Show the successful capture message and the invoice status changing to PAID. Explain that the Flask backend verifies the order with PayPal before saving the payment.

**2:15–2:30 — Technology and closing**
Briefly show the GitHub repository and say: "PayAI is built with Python Flask, Google Gemini, PayPal Orders API and SQLite. Thank you."

Upload the recording publicly to YouTube or Vimeo and include the video URL in your project submission.

## Security and production limitations

This is a classroom/demo starter, not production-ready payment software:
- No user authentication or role-based access is implemented.
- Add CSRF protection, rate limiting, secure session management and authenticated access before deployment.
- Add PayPal webhook verification and reconciliation for production.
- Use HTTPS and a managed database for hosted deployment.
- Keep all API credentials in environment variables or a secrets manager.
- Do not enable `PAYPAL_MODE=live` for this demo.
- Review applicable PayPal availability, currency and merchant-account requirements for your country before any real-money use.
