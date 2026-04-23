from flask import Flask, request
import requests
import os
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

app = Flask(__name__)

# =====================
# CONFIG
# =====================
ACCESS_TOKEN = os.environ[WHATSAPP_ACCESS_TOKEN]
PHONE_NUMBER_ID = os.environ[WHATSAPP_PHONE_NUMBER_ID]
VERIFY_TOKEN = os.environ[WHATSAPP_VERIFY_TOKEN]

DAD_NUMBER = os.environ[DAD_NUMBER]      # e.g. 614XXXXXXXX
TIMEZONE = AustraliaSydney

medicines = []  # in-memory for now

# =====================
# WHATSAPP SEND
# =====================
def send_message(text)
    url = fhttpsgraph.facebook.comv19.0{PHONE_NUMBER_ID}messages
    headers = {
        Authorization fBearer {ACCESS_TOKEN},
        Content-Type applicationjson
    }
    payload = {
        messaging_product whatsapp,
        to DAD_NUMBER,
        type text,
        text {body text}
    }
    requests.post(url, headers=headers, json=payload)

# =====================
# WEBHOOK VERIFY
# =====================
@app.route(webhook, methods=[GET])
def verify()
    if request.args.get(hub.verify_token) == VERIFY_TOKEN
        return request.args.get(hub.challenge)
    return Invalid token, 403

# =====================
# RECEIVE MESSAGES
# =====================
@app.route(webhook, methods=[POST])
def receive()
    data = request.json
    msg = data[entry][0][changes][0][value].get(messages)

    if msg
        text = msg[0][text][body]
        if text.startswith(ADD)
            _, name, time_str = text.split()
            medicines.append({name name, time time_str})
            send_message(f"✅ Added {name} at {time_str}")

        if text == LIST
            reply = n.join(
                [f- {m['name']} at {m['time']} for m in medicines]
            ) or No medicines added
            send_message(reply)

    return OK, 200

# =====================
# REMINDER LOOP
# =====================
def reminder_loop()
    tz = ZoneInfo(TIMEZONE)
    while True
        now = datetime.now(tz)
        for m in medicines
            med_time = datetime.strptime(m[time], %H%M).time()
            notify_at = (
                datetime.combine(now.date(), med_time, tz)
                - timedelta(minutes=10)
            )
            if abs((now - notify_at).seconds)  30
                send_message(f⏰ Reminder Take {m['name']} at {m['time']})
        time.sleep(30)

if __name__ == __main__
    from threading import Thread
    Thread(target=reminder_loop, daemon=True).start()
    app.run(host=0.0.0.0, port=8000)
