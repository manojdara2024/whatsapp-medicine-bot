# -*- coding: utf-8 -*-

from flask import Flask, request
import requests, os, time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from threading import Thread
import psycopg

app = Flask(__name__)

ACCESS_TOKEN = os.environ["WHATSAPP_ACCESS_TOKEN"]
PHONE_NUMBER_ID = os.environ["WHATSAPP_PHONE_NUMBER_ID"]
VERIFY_TOKEN = os.environ["WHATSAPP_VERIFY_TOKEN"]
TEST_NUMBER = os.environ["TEST_NUMBER"]

TIMEZONE = os.environ.get("TIMEZONE", "Australia/Sydney")
ALERT_OFFSET_MINUTES = int(os.environ.get("ALERT_OFFSET_MINUTES", "10"))
DATABASE_URL = os.environ["DATABASE_URL"]

def get_conn():
    return psycopg.connect(DATABASE_URL)  # supports postgresql:// URLs [2](https://www.psycopg.org/psycopg3/docs/api/connections.html)

def init_db():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS medicines (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    time_hhmm TEXT NOT NULL
                );
            """)
init_db()

def send_message(text: str, to_number: str = None):
    to_number = to_number or TEST_NUMBER
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "to": to_number, "type": "text", "text": {"body": text}}
    requests.post(url, headers=headers, json=payload)

@app.route("/webhook", methods=["GET"])
def verify():
    if request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge"), 200
    return "Invalid token", 403

def add_med(name, time_str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO medicines(name, time_hhmm) VALUES (%s,%s)", (name, time_str))

def list_meds():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name, time_hhmm FROM medicines ORDER BY id")
            return cur.fetchall()

def delete_med(name):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM medicines WHERE LOWER(name)=LOWER(%s)", (name,))

def clear_meds():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM medicines")

@app.route("/webhook", methods=["POST"])
def receive():
    data = request.get_json(silent=True) or {}
    try:
        value = data["entry"][0]["changes"][0]["value"]
        msgs = value.get("messages")
        if not msgs:
            return "OK", 200

        msg = msgs[0]
        if msg.get("type") != "text":
            send_message("📷 Non-text received. Use ADD / LIST for now.")
            return "OK", 200

        text = msg["text"]["body"].strip()

        if text.upper().startswith("ADD "):
            parts = text.split()
            if len(parts) != 3:
                send_message('❗ Usage: ADD <MedicineName> <HH:MM>\nExample: ADD Metformin 08:00')
                return "OK", 200

            _, name, time_str = parts
            try:
                datetime.strptime(time_str, "%H:%M")
            except ValueError:
                send_message("❗ Time must be HH:MM (24-hour). Example: 08:00")
                return "OK", 200

            add_med(name, time_str)
            send_message(f"✅ Added {name} at {time_str}")
            return "OK", 200

        if text.upper() == "LIST":
            meds = list_meds()
            if not meds:
                send_message("📋 No medicines added yet.\nAdd one using: ADD Metformin 08:00")
                return "OK", 200
            lines = ["📋 Current medicines:"]
            for i, (n, t) in enumerate(meds, start=1):
                lines.append(f"{i}. {n} at {t}")
            send_message("\n".join(lines))
            return "OK", 200

        if text.upper().startswith("DELETE "):
            target = text.split(maxsplit=1)[1].strip() if len(text.split()) > 1 else ""
            if not target:
                send_message("❗ Usage: DELETE <MedicineName>")
                return "OK", 200
            delete_med(target)
            send_message(f"🗑️ Deleted {target}")
            return "OK", 200

        if text.upper() == "CLEAR":
            clear_meds()
            send_message("🧹 Cleared all medicines.")
            return "OK", 200

        send_message("🤖 Commands: ADD / LIST / DELETE / CLEAR")
        return "OK", 200

    except Exception as e:
        send_message(f"⚠️ Error: {e}")
        return "OK", 200

def reminder_loop():
    tz = ZoneInfo(TIMEZONE)
    sent_cache = set()

    while True:
        now = datetime.now(tz)
        now_hhmm = now.strftime("%H:%M")

        meds = list_meds()
        for name, dose_time in meds:
            try:
                dose_dt = datetime.combine(now.date(), datetime.strptime(dose_time, "%H:%M").time(), tzinfo=tz)
                remind_dt = dose_dt - timedelta(minutes=ALERT_OFFSET_MINUTES)
                if abs((now - remind_dt).total_seconds()) <= 30:
                    key = (now.date().isoformat(), name, dose_time)
                    if key not in sent_cache:
                        send_message(f"⏰ Reminder: Take {name} at {dose_time}")
                        sent_cache.add(key)
            except Exception:
                continue

        time.sleep(30)

Thread(target=reminder_loop, daemon=True).start()

@app.route("/", methods=["GET"])
def home():
    return "OK", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)
