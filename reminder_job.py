# -*- coding: utf-8 -*-
import os
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

print("✅ NEW VERSION RUNNING")
print("🟢 CRON START UTC:", datetime.utcnow().isoformat())


# ------------------------
ACCESS_TOKEN = os.environ["WHATSAPP_ACCESS_TOKEN"]
PHONE_NUMBER_ID = os.environ["WHATSAPP_PHONE_NUMBER_ID"]
TEST_NUMBER = os.environ["TEST_NUMBER"]
DATABASE_URL = os.environ["DATABASE_URL"]

TIMEZONE = os.environ.get("TIMEZONE", "Australia/Sydney")

# Alert behavior
ALERT_OFFSET_MIN = int(os.environ.get("ALERT_OFFSET_MIN", "10"))  # 10 min before
WINDOW_MIN = int(os.environ.get("WINDOW_MIN", "4"))               # safe for */2 cron drift

GRAPH_VERSION = os.environ.get("GRAPH_VERSION", "v19.0")

# ------------------------
# Helpers
# ------------------------
def send_message(text: str):
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


def hhmm_to_minutes(hhmm: str) -> int:
    h, m = map(int, hhmm.split(":"))
    return h * 60 + m


def minutes_to_hhmm(total: int) -> str:
    total %= 24 * 60
    return f"{total // 60:02d}:{total % 60:02d}"


def within_minutes(target_hhmm: str, now: datetime, window_minutes: int) -> bool:
    h, m = map(int, target_hhmm.split(":"))
    target = now.replace(hour=h, minute=m, second=0, microsecond=0)
    return abs((now - target).total_seconds()) <= window_minutes * 60


def ensure_log_table(conn):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS reminder_log (
                day TEXT NOT NULL,
                med_name TEXT NOT NULL,
                dose_time TEXT NOT NULL,
                kind TEXT NOT NULL,
                PRIMARY KEY (day, med_name, dose_time, kind)
            );
        """)


def should_send(conn, day: str, med_name: str, dose_time: str, kind: str) -> bool:
    """
    Returns True only once per day per (med_name, dose_time, kind).
    Prevents duplicates when cron runs multiple times in the window.
    """
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO reminder_log(day, med_name, dose_time, kind)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        """, (day, med_name, dose_time, kind))
        return cur.rowcount == 1


# ------------------------
# Main
# ------------------------

print("🟢 CRON START UTC:", datetime.utcnow().isoformat())


now = datetime.now(ZoneInfo(TIMEZONE))
today = now.date().isoformat()
now_hhmm = now.strftime("%H:%M")

print("🕒 Local now:", now.isoformat(), "TZ=", TIMEZONE)

with psycopg.connect(DATABASE_URL) as conn:
    ensure_log_table(conn)

    with conn.cursor() as cur:
        cur.execute("SELECT name, time_hhmm FROM medicines")
        meds = cur.fetchall()

    print("📋 medicines:", meds)


import psycopg
from datetime import datetime
from zoneinfo import ZoneInfo

# ------------------------
