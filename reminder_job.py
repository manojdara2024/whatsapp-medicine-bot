import os
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
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": TEST_NUMBER,
        "type": "text",
        "text": {"body": text}
    }
    requests.post(url, headers=headers, json=payload)

now = datetime.now(ZoneInfo(TIMEZONE))
now_hhmm = now.strftime("%H:%M")

with psycopg.connect(DATABASE_URL) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT name, time_hhmm FROM medicines")
        meds = cur.fetchall()

for name, time_hhmm in meds:
    if time_hhmm == now_hhmm:
        send_message(f"⏰ Reminder: Take {name} now")