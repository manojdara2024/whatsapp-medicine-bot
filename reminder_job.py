# -*- coding: utf-8 -*-

import os
import sqlite3
import requests
from datetime import datetime, timedelta, UTC
from zoneinfo import ZoneInfo

# ------------------------
# Env vars (Cron Job)
# ------------------------
ACCESS_TOKEN = os.environ["WHATSAPP_ACCESS_TOKEN"]
PHONE_NUMBER_ID = os.environ["WHATSAPP_PHONE_NUMBER_ID"]
TEST_NUMBER = os.environ["TEST_NUMBER"]

TIMEZONE = os.environ.get("TIMEZONE", "Australia/Sydney")
GRAPH_VERSION = os.environ.get("GRAPH_VERSION", "v19.0")

ALERT_OFFSET_MIN = int(os.environ.get("ALERT_OFFSET_MIN", "10"))  # 10‑min before
WINDOW_MIN = int(os.environ.get("WINDOW_MIN", "6"))               # cron drift window
WINDOW = timedelta(minutes=WINDOW_MIN)

DB_FILE = "medicine.db"


def get_conn():
    return sqlite3.connect(DB_FILE)


# ------------------------
# WhatsApp send (TEXT ONLY)
# ------------------------
def send_whatsapp(text: str):
    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{PHONE_NUMBER_ID}/messages"

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": TEST_NUMBER,
        "type": "text",
        "text": {"body": text},
    }

    resp = requests.post(url, headers=headers, json=payload)

    print("WhatsApp response:", resp.status_code, resp.text)
    return resp.status_code == 200


# ------------------------
# Text Card Builder
# ------------------------
def build_text_card(med_name: str, hhmm: str, mode: str) -> str:
    """
    mode = "before" | "exact"
    """

    if mode == "exact":
        header = "🚨 💊 *MEDICINE REMINDER* 🚨"
        action = "✅ Take now"
        habit = "💧 Drink water"
        ack = "👉 Reply *DONE* after taking"
    else:
        header = "💊 *MEDICINE REMINDER*"
        action = f"⏳ In {ALERT_OFFSET_MIN} minutes"
        habit = ""
        ack = ""

    parts = [
        header,
        "———————————————",
        f"*{med_name.upper()}*",
        "",
        f"⏰ *{hhmm}*",
        action,
    ]

    if habit:
        parts.append(habit)

    if ack:
        parts.append(ack)

    parts.append("———————————————")

    return "\n".join(parts)


# ------------------------
# DB helpers
# ------------------------
def ensure_tables(conn):

    conn.execute("""
        CREATE TABLE IF NOT EXISTS medicines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            time_hhmm TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS reminder_log (
            reminder_date TEXT NOT NULL,
            med_name TEXT NOT NULL,
            kind TEXT NOT NULL,
            PRIMARY KEY (reminder_date, med_name, kind)
        )
    """)

    conn.commit()


def already_sent(conn, med_name, kind, reminder_date):
    cur = conn.execute(
        """
        SELECT 1
        FROM reminder_log
        WHERE reminder_date = ?
          AND med_name = ?
          AND kind = ?
        LIMIT 1
        """,
        (str(reminder_date), med_name, kind),
    )

    return cur.fetchone() is not None


def log_sent(conn, med_name, kind, reminder_date):
    conn.execute(
        """
        INSERT OR IGNORE INTO reminder_log
        (reminder_date, med_name, kind)
        VALUES (?, ?, ?)
        """,
        (str(reminder_date), med_name, kind),
    )

    conn.commit()


# ------------------------
# Main
# ------------------------
print("🟢 CRON START UTC:", datetime.now(UTC).isoformat())

now = datetime.now(ZoneInfo(TIMEZONE))
print("🕒 Local now:", now.isoformat(), "TZ=", TIMEZONE)

reminder_date = now.date()

with get_conn() as conn:

    ensure_tables(conn)

    cur = conn.execute(
        "SELECT name, time_hhmm FROM medicines"
    )

    medicines = cur.fetchall()

    print("📋 medicines:", medicines)

    for name, hhmm in medicines:

        h, m = map(int, hhmm.split(":"))

        med_dt = now.replace(
            hour=h,
            minute=m,
            second=0,
            microsecond=0
        )

        before_dt = med_dt - timedelta(minutes=ALERT_OFFSET_MIN)

        # 10‑min BEFORE reminder
        if before_dt <= now < before_dt + WINDOW:

            if not already_sent(
                conn,
                name,
                "before",
                reminder_date
            ):
                print(f"🔔 Sending 10‑min reminder for {name}")

                send_whatsapp(
                    build_text_card(name, hhmm, "before")
                )

                log_sent(
                    conn,
                    name,
                    "before",
                    reminder_date
                )

        # EXACT‑TIME reminder
        if med_dt <= now < med_dt + WINDOW:

            if not already_sent(
                conn,
                name,
                "exact",
                reminder_date
            ):
                print(f"💊 Sending exact‑time reminder for {name}")

                send_whatsapp(
                    build_text_card(name, hhmm, "exact")
                )

                log_sent(
                    conn,
                    name,
                    "exact",
                    reminder_date
                )
