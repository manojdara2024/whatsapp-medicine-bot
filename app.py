# -*- coding: utf-8 -*-

from flask import Flask, request
import requests
import os
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from threading import Thread

app = Flask(__name__)

# =====================
# CONFIG (Render Env Vars)
# =====================
ACCESS_TOKEN = os.environ["WHATSAPP_ACCESS_TOKEN"]
PHONE_NUMBER_ID = os.environ["WHATSAPP_PHONE_NUMBER_ID"]
VERIFY_TOKEN = os.environ["WHATSAPP_VERIFY_TOKEN"]

# Your dad's WhatsApp number in digits with country code (no +), e.g. 614XXXXXXXX
DAD_NUMBER = os.environ["DAD_NUMBER"]

TIMEZONE = os.environ.get("TIMEZONE", "Australia/Sydney")
ALERT_OFFSET_MINUTES = int(os.environ.get("ALERT_OFFSET_MINUTES", "10"))

# In-memory list for now (later we can make this persistent in SQLite)
# Format: {"name": "Metformin", "time": "08:00"}
medicines = []

# =====================
# WHATSAPP SEND
# =====================
def send_message(text: str, to_number: str = None):
    """
    Sends a WhatsApp text message using Cloud API.
    """
    to_number = to_number or DAD_NUMBER

    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": text}
    }

    # Best-effort send; you can print response for debugging if needed
    requests.post(url, headers=headers, json=payload)

# =====================
# WEBHOOK VERIFY (Meta calls this first)
# =====================
@app.route("/webhook", methods=["GET"])
def verify():
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if token == VERIFY_TOKEN:
        return challenge, 200
    return "Invalid token", 403

# =====================
# RECEIVE MESSAGES (Meta sends inbound messages here)
# =====================
@app.route("/webhook", methods=["POST"])
def receive():
    data = request.get_json(silent=True) or {}

    try:
        value = data["entry"][0]["changes"][0]["value"]
        msgs = value.get("messages")
        if not msgs:
            return "OK", 200

        msg = msgs[0]
        msg_type = msg.get("type")

        # Only handling text for MVP
        if msg_type != "text":
            send_message("📷 I received a non-text message. For now, please use commands like ADD or LIST.")
            return "OK", 200

        text = msg["text"]["body"].strip()

        # Commands:
        # ADD Metformin 08:00
        # LIST
        # DELETE Metformin
        # CLEAR
        if text.upper().startswith("ADD "):
            parts = text.split()
            if len(parts) != 3:
                send_message('❗ Usage: ADD <MedicineName> <HH:MM>\nExample: ADD Metformin 08:00')
                return "OK", 200

            _, name, time_str = parts

            # Basic time validation
            try:
                datetime.strptime(time_str, "%H:%M")
            except ValueError:
                send_message('❗ Time must be HH:MM (24-hour). Example: 08:00')
                return "OK", 200

            medicines.append({"name": name, "time": time_str})
            send_message(f"✅ Added {name} at {time_str}")
            return "OK", 200

        if text.upper() == "LIST":
            if not medicines:
                send_message("📋 No medicines added yet.\nAdd one using: ADD Metformin 08:00")
                return "OK", 200

            reply_lines = ["📋 Current medicines:"]
            for i, m in enumerate(medicines, start=1):
                reply_lines.append(f"{i}. {m['name']} at {m['time']}")
            send_message("\n".join(reply_lines))
            return "OK", 200

        if text.upper().startswith("DELETE "):
            parts = text.split(maxsplit=1)
            if len(parts) != 2:
                send_message("❗ Usage: DELETE <MedicineName>\nExample: DELETE Metformin")
                return "OK", 200

            target = parts[1].strip()
            before = len(medicines)
            medicines[:] = [m for m in medicines if m["name"].lower() != target.lower()]
            after = len(medicines)

            if after < before:
                send_message(f"🗑️ Deleted {target}")
            else:
                send_message(f"❗ Could not find {target}. Use LIST to see names.")
            return "OK", 200

        if text.upper() == "CLEAR":
            medicines.clear()
            send_message("🧹 Cleared all medicines.")
            return "OK", 200

        # Default help message
        send_message(
            "🤖 Commands:\n"
            "• ADD <MedicineName> <HH:MM>  (Example: ADD Metformin 08:00)\n"
            "• LIST\n"
            "• DELETE <MedicineName>\n"
            "• CLEAR"
        )
        return "OK", 200

    except Exception as e:
        # If payload format differs, don’t crash the webhook
        send_message(f"⚠️ Error processing message: {e}")
        return "OK", 200

# =====================
# REMINDER LOOP (10 min before)
# =====================
def reminder_loop():
    tz = ZoneInfo(TIMEZONE)

    # To avoid sending same reminder repeatedly within the minute, keep a short memory
    # Key: (date_str, name, dose_time) -> last_sent_iso
    sent_cache = {}

    while True:
        now = datetime.now(tz)

        for m in list(medicines):
            try:
                # Dose time today in tz
                dose_time_obj = datetime.strptime(m["time"], "%H:%M").time()
                dose_dt = datetime.combine(now.date(), dose_time_obj, tzinfo=tz)

                remind_dt = dose_dt - timedelta(minutes=ALERT_OFFSET_MINUTES)

                # Fire if we're within a 30-second window around remind time
                if abs((now - remind_dt).total_seconds()) <= 30:
                    key = (now.date().isoformat(), m["name"], m["time"])

                    # Prevent duplicate sends in case loop runs twice within same window
                    if key not in sent_cache:
                        send_message(f"⏰ Reminder: Take {m['name']} at {m['time']}")
                        sent_cache[key] = now.isoformat()

            except Exception:
                # Skip bad entries safely
                continue

        time.sleep(30)

# Start reminder thread once
Thread(target=reminder_loop, daemon=True).start()

@app.route("/", methods=["GET"])
def home():
    return "OK", 200

if __name__ == "__main__":
    # Render provides PORT env var; default for local dev
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)
