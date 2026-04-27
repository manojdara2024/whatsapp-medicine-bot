import os
import requests
import psycopg
from datetime import datetime
from zoneinfo import ZoneInfo


# ------------------------
# Environment variables
# ------------------------
WHATSAPP_ACCESS_TOKEN = os.environ["WHATSAPP_ACCESS_TOKEN"]
WHATSAPP_PHONE_NUMBER_ID = os.environ["WHATSAPP_PHONE_NUMBER_ID"]
TEST_NUMBER = os.environ["TEST_NUMBER"]
DATABASE_URL = os.environ["DATABASE_URL"]
TIMEZONE = os.environ.get("TIMEZONE", "Australia/Sydney")


# ------------------------
# Helper functions
# ------------------------
def send_message(text: str):
    url = f"https://graph.facebook.com/v19.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
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


