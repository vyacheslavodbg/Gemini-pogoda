import os
import json
import urllib.request
import math
from datetime import datetime, timezone

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

LOCATIONS = {
    "varna": {"name": "Варна", "lat": 43.2141, "lon": 27.9147},
    "odesa": {"name": "Одесса", "lat": 46.4825, "lon": 30.7233}
}

def send_telegram_message(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("[SKIP] TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing.")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            print("[SUCCESS] Telegram message sent.")
    except Exception as e:
        print(f"[ERROR] Failed to send message: {e}")

def main():
    print("Checking meteo conditions...")
    # Monitoring logic here
    print("Execution complete.")

if __name__ == "__main__":
    main()