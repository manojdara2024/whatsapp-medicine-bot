import os
print("✅ reminder_job started")
import psycopg
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

ACCESS_TOKEN = os.environ["WHATSAPP_ACCESS_TOKEN"]
PHONE_NUMBER_ID = os.environ["WHATSAPP_PHONE_NUMBER_ID"]
TEST_NUMBER = os.environ["TEST_NUMBER"]
DATABASE_URL = os.environ["DATABASE_URL"]
TIMEZONE = os.environ.get("TIMEZONE", "Australia/Sydney")

def send_message(text):
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "to": TEST_NUMBER, "type": "text", "text": {"body": text}}
    requests.post(url, headers=headers, json=payload)

def hhmm_to_minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)

def minutes_to_hhmm(total: int) -> str:
    total = total % (24 * 60)
    return f"{total // 60:02d}:{total % 60:02d}"

now = datetime.now(ZoneInfo(TIMEZONE))
now_hhmm = now.strftime("%H:%M")

with psycopg.connect(DATABASE_URL) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT name, time_hhmm FROM medicines")
        meds = cur.fetchall()

for name, dose_time in meds:
    # 10 mins before
    before_hhmm = minutes_to_hhmm(hhmm_to_minutes(dose_time) - 10)

    if now_hhmm == before_hhmm:
        send_message(f"⏳ Reminder: {name} at {dose_time} (in 10 min)")
    if now_hhmm == dose_time:
        send_message(f"⏰ Reminder: Take {name} now ({dose_time})")
