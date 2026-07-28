# -*- coding: utf-8 -*-

from flask import Flask, request
import requests, os
from datetime import datetime
import sqlite3

app = Flask(__name__)

ACCESS_TOKEN = os.environ["WHATSAPP_ACCESS_TOKEN"]
PHONE_NUMBER_ID = os.environ["WHATSAPP_PHONE_NUMBER_ID"]
VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN", "test123")
TEST_NUMBER = os.environ["TEST_NUMBER"]

DB_FILE = "/var/data/medicine.db"


def get_conn():
    return sqlite3.connect(DB_FILE)


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS medicines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                time_hhmm TEXT NOT NULL
            )
        """)
        conn.commit()


init_db()


def send_message(text: str, to_number: str = None):
    to_number = to_number or TEST_NUMBER

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

    response = requests.post(
        url,
        headers=headers,
        json=payload
    )

    print("WhatsApp Status:", response.status_code, flush=True)
    print("WhatsApp Response:", response.text, flush=True)

    return response


@app.route("/test")
def test():

    response = send_message("✅ Test message from Render")

    return f"{response.status_code} - {response.text}", 200


@app.route("/", methods=["GET"])
def home():
    return "OK", 200


@app.route("/webhook", methods=["GET"])
def verify():
    if request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge"), 200

    return "Invalid token", 403


def add_med(name, time_str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO medicines(name, time_hhmm) VALUES (?, ?)",
            (name, time_str)
        )
        conn.commit()


def list_meds():
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT name, time_hhmm FROM medicines ORDER BY id"
        )
        return cur.fetchall()


def delete_med(name):
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM medicines WHERE LOWER(name)=LOWER(?)",
            (name,)
        )
        conn.commit()


def clear_meds():
    with get_conn() as conn:
        conn.execute("DELETE FROM medicines")
        conn.commit()


@app.route("/webhook", methods=["POST"])
def receive():

    data = request.get_json(silent=True) or {}

    print("🔥 WEBHOOK RECEIVED", flush=True)
    print(data, flush=True)

    try:
        value = data["entry"][0]["changes"][0]["value"]
        msgs = value.get("messages")

        if not msgs:
            print("No messages found", flush=True)
            return "OK", 200

        msg = msgs[0]
        sender = msg["from"]

        if msg.get("type") != "text":
            send_message(
                "📷 Non-text received. Use ADD / LIST for now.",
                sender
            )
            return "OK", 200

        text = msg["text"]["body"].strip()

        print("Received text:", text, flush=True)
        print("Sender:", sender, flush=True)

        if text.upper().startswith("DONE"):
            send_message(
                "✅ Great job! You've taken your medicine 💪",
                sender
            )
            return "OK", 200

        if text.upper().startswith("ADD "):

            parts = text.split()

            if len(parts) != 3:
                send_message(
                    "Usage: ADD MedicineName HH:MM",
                    sender
                )
                return "OK", 200

            _, name, time_str = parts

            try:
                datetime.strptime(time_str, "%H:%M")
            except ValueError:
                send_message(
                    "Time must be HH:MM. Example: 08:00",
                    sender
                )
                return "OK", 200

            add_med(name, time_str)

            send_message(
                f"✅ Added {name} at {time_str}",
                sender
            )

            return "OK", 200

        if text.upper() == "LIST":

            meds = list_meds()

            if not meds:
                send_message(
                    "📋 No medicines added yet.",
                    sender
                )
                return "OK", 200

            lines = ["📋 Current medicines:"]

            for i, (n, t) in enumerate(meds, start=1):
                lines.append(f"{i}. {n} at {t}")

            send_message(
                "\n".join(lines),
                sender
            )

            return "OK", 200

        if text.upper().startswith("DELETE "):

            target = text.split(maxsplit=1)[1].strip()

            delete_med(target)

            send_message(
                f"🗑️ Deleted {target}",
                sender
            )

            return "OK", 200

        if text.upper() == "CLEAR":

            clear_meds()

            send_message(
                "🧹 Cleared all medicines.",
                sender
            )

            return "OK", 200

        send_message(
            "Commands:\nADD\nLIST\nDELETE\nCLEAR",
            sender
        )

        return "OK", 200

    except Exception as e:
        print("ERROR:", str(e), flush=True)
        return "OK", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)
