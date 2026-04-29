# -*- coding: utf-8 -*-

import os
import requests
import psycopg
from datetime import datetime, timedelta, UTC
from zoneinfo import ZoneInfo
from urllib.parse import quote_plus

# ------------------------
# Env vars (Cron Job)
# ------------------------
ACCESS_TOKEN = os.environ["WHATSAPP_ACCESS_TOKEN"]
PHONE_NUMBER_ID = os.environ["WHATSAPP_PHONE_NUMBER_ID"]
TEST_NUMBER = os.environ["TEST_NUMBER"]
DATABASE_URL = os.environ["DATABASE_URL"]

TIMEZONE = os.environ.get("TIMEZONE", "Australia/Sydney")
GRAPH_VERSION = os.environ.get("GRAPH_VERSION", "v19.0")

ALERT_OFFSET_MIN = int(os.environ.get("ALERT_OFFSET_MIN", "10"))  # 10-min before
WINDOW_MIN = int(os.environ.get("WINDOW_MIN", "6"))               # safe for */2 cron drift
WINDOW = timedelta(minutes=WINDOW_MIN)

# ------------------------
# WhatsApp send
# ------------------------
def send_whatsapp(text: str):
    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": TEST_NUMBER,
        "type": "text",
        "text": {"body": text},
    }
    resp = requests.post(url, headers=headers, json=payload)
    print("WhatsApp response:", resp.status_code, resp.text)


def send_whatsapp_image(image_url: str, caption: str) -> bool:
    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": TEST_NUMBER,
        "type": "image",
        "image": {
            "link": image_url,
            "caption": caption,
        },
    }

    resp = requests.post(url, headers=headers, json=payload)
    print("WhatsApp image response:", resp.status_code, resp.text)
    return resp.status_code == 200


def build_image_card_url(med_name: str, hhmm: str) -> str:
    title = quote_plus(med_name.upper())
    line2 = quote_plus("TIME TO TAKE MEDICINE")
    time = quote_plus(f"⏰ {hhmm}")

    return (
        "https://res.cloudinary.com/demo/image/text/"
        f"arial_60_bold:{title}\n{line2}\n{time}.png"
    )
    
# ------------------------
# DB helpers
# ------------------------
def ensure_tables(conn):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS reminder_log (
                reminder_date DATE NOT NULL,
                med_name TEXT NOT NULL,
                kind TEXT NOT NULL,
                PRIMARY KEY (reminder_date, med_name, kind)
            );
        """)

def already_sent(conn, med_name: str, kind: str, reminder_date):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM reminder_log WHERE reminder_date=%s AND med_name=%s AND kind=%s LIMIT 1",
            (reminder_date, med_name, kind),
        )
        return cur.fetchone() is not None

def log_sent(conn, med_name: str, kind: str, reminder_date):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO reminder_log(reminder_date, med_name, kind) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
            (reminder_date, med_name, kind),
        )

# ------------------------
# Main
# ------------------------
print("🟢 CRON START UTC:", datetime.now(UTC).isoformat())

now = datetime.now(ZoneInfo(TIMEZONE))
print("🕒 Local now:", now.isoformat(), "TZ=", TIMEZONE)

reminder_date = now.date()

# IMPORTANT: keep everything inside this WITH block so conn stays open
with psycopg.connect(DATABASE_URL) as conn:
    ensure_tables(conn)

    with conn.cursor() as cur:
        cur.execute("SELECT name, time_hhmm FROM medicines")
        medicines = cur.fetchall()

    print("📋 medicines:", medicines)

    for name, hhmm in medicines:
        # Build today's dose datetime in local timezone
        h, m = map(int, hhmm.split(":"))
        med_dt = now.replace(hour=h, minute=m, second=0, microsecond=0)
        before_dt = med_dt - timedelta(minutes=ALERT_OFFSET_MIN)

        # ------------------------
        # 10-min before window
        # ------------------------
        if before_dt <= now < before_dt + WINDOW:
            if not already_sent(conn, name, "before", reminder_date):
                print(f"🔔 Sending 10‑min reminder for {name}")

                image_url = build_image_card_url(name, hhmm)
                print("🖼 Image URL:", image_url)

                sent = send_whatsapp_image(
                    image_url,
                    caption=f"💊 {name}\n⏰ In {ALERT_OFFSET_MIN} minutes"
                )

                if not sent:
                    print("⚠️ Image failed, falling back to text")
                    send_whatsapp(f"💊 {name}\n⏰ In {ALERT_OFFSET_MIN} minutes")

                log_sent(conn, name, "before", reminder_date)
            else:
                print(f"⏭️ Skipping duplicate BEFORE reminder for {name}")

        # ------------------------
        # exact time window
        # NOTE: use IF (not ELIF) so BEFORE doesn't block EXACT in edge cases
        # ------------------------
        if med_dt <= now < med_dt + WINDOW:
            if not already_sent(conn, name, "exact", reminder_date):
                print(f"💊 Sending exact‑time reminder for {name}")

                image_url = build_image_card_url(name, hhmm)
                print("🖼 Image URL:", image_url)

                sent = send_whatsapp_image(
                    image_url,
                    caption=f"💊 {name}\n⏰ Time to take now"
                )

                if not sent:
                    print("⚠️ Image failed, falling back to text")
                    send_whatsapp(f"💊 {name}\n⏰ Time to take now")

                log_sent(conn, name, "exact", reminder_date)
            else:
                print(f"⏭️ Skipping duplicate EXACT reminder for {name}")
