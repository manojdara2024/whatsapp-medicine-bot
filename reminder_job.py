import os
import requests
import psycopg

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# ======================
# Configuration
# ======================
TIMEZONE = os.getenv("TIMEZONE", "Australia/Sydney")
DATABASE_URL = os.getenv("DATABASE_URL")

WHATSAPP_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
TO_PHONE = os.getenv("TEST_NUMBER")


# ======================
# Helpers
# ======================
def send_whatsapp(message: str):
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": TO_PHONE,
        "type": "text",
        "text": {"body": message},
    }
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()


# ======================
# Job start
# ======================
print("🟢 CRON START UTC:", datetime.now(ZoneInfo("UTC")).isoformat())

now = datetime.now(ZoneInfo(TIMEZONE))
print(f"🕒 Local now: {now.isoformat()} TZ= {TIMEZONE}")

# ======================
# Database read
# ======================

with psycopg.connect(DATABASE_URL) as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT name, time_hhmm
            FROM public.medicines
        """)
        medicines = cur.fetchall()

print("📋 medicines:", medicines)


WINDOW = timedelta(minutes=2)

for name, med_time in medicines:
    try:
        hh, mm = map(int, med_time.split(":"))
    except ValueError:
        print(f"⚠️ Invalid time format for {name}: {med_time}")
        continue

    med_dt = now.replace(
        hour=hh,
        minute=mm,
        second=0,
        microsecond=0
    )

    before_dt = med_dt - timedelta(minutes=10)

    if before_dt <= now < before_dt + WINDOW:
        print(f"🔔 Sending 10‑min reminder for {name}")
        send_whatsapp(f"⏰ Reminder: Take {name} in 10 minutes")

    elif med_dt <= now < med_dt + WINDOW:
        print(f"💊 Sending exact‑time reminder for {name}")
        send_whatsapp(f"💊 Time to take {name}")


print("✅ CRON RUN COMPLETE")
