#!/usr/bin/env python3
# server/payments.py  --  PocketMall Stripe payment server
import os, sqlite3, hashlib, json
from pathlib import Path
from flask import Flask, request, jsonify, abort
import stripe

app = Flask(__name__)

# --- Config (set via environment variables) ---
stripe.api_key          = os.environ["STRIPE_SECRET_KEY"]
WEBHOOK_SECRET         = os.environ["STRIPE_WEBHOOK_SECRET"]
BASE_URL                = os.environ.get("BASE_URL", "https://pocketmint.crystal-kitsune-studios.com")
DB_PATH                 = Path(os.environ.get("DB_PATH", "licenses.db"))

# Prices (Stripe Price IDs — create these in your Stripe dashboard)
APP_PRICES = {
    "pixelcraft":  os.environ.get("PRICE_PIXELCRAFT",  "price_PIXELCRAFT_ID"),
    "pocketdraw":  os.environ.get("PRICE_POCKETDRAW",  "price_POCKETDRAW_ID"),
}

# --- DB ---
def init_db():
    with sqlite3.connect(DB_PATH) as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS licenses (
                device_id TEXT NOT NULL,
                app_id    TEXT NOT NULL,
                session_id TEXT,
                paid      INTEGER DEFAULT 0,
                created   TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (device_id, app_id)
            )
        """)

init_db()

def get_db(): return sqlite3.connect(DB_PATH)

# --- Helpers ---
def is_licensed(device_id, app_id):
    with get_db() as c:
        row = c.execute(
            "SELECT paid FROM licenses WHERE device_id=? AND app_id=?",
            (device_id, app_id)
        ).fetchone()
    return row and row[0] == 1

def mark_paid(session_id):
    with get_db() as c:
        c.execute(
            "UPDATE licenses SET paid=1 WHERE session_id=?",
            (session_id,)
        )

# --- Routes ---

@app.route("/api/purchase", methods=["POST"])
def purchase():
    data      = request.json or {}
    app_id    = data.get("app_id", "")
    device_id = data.get("device_id", "")
    if not app_id or not device_id:
        return jsonify({"error": "missing app_id or device_id"}), 400
    if app_id not in APP_PRICES:
        return jsonify({"error": "unknown app"}), 404
    if is_licensed(device_id, app_id):
        return jsonify({"already_licensed": True}), 200

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{"price": APP_PRICES[app_id], "quantity": 1}],
        mode="payment",
        success_url=f"{BASE_URL}/purchase-success?session_id=CHECKOUT_SESSION_ID",
        cancel_url=f"{BASE_URL}/pocketmall",
        metadata={"device_id": device_id, "app_id": app_id},
    )
    # Store pending license
    with get_db() as c:
        c.execute(
            "INSERT OR REPLACE INTO licenses (device_id, app_id, session_id, paid) VALUES (?,?,?,0)",
            (device_id, app_id, session.id)
        )
    return jsonify({"checkout_url": session.url, "session_id": session.id})


@app.route("/api/check-license", methods=["GET"])
def check_license():
    device_id = request.args.get("device_id", "")
    app_id    = request.args.get("app_id", "")
    if not device_id or not app_id:
        return jsonify({"error": "missing params"}), 400
    return jsonify({"licensed": is_licensed(device_id, app_id)})


@app.route("/api/stripe-webhook", methods=["POST"])
def stripe_webhook():
    payload = request.data
    sig     = request.headers.get("Stripe-Signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig, WEBHOOK_SECRET)
    except Exception as e:
        abort(400, str(e))
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        mark_paid(session["id"])
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
