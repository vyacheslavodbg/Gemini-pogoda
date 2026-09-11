import os
import json
import urllib.request
from datetime import datetime, timezone

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

LOCATIONS = {
    "varna": {
        "name": "Варна",
        "lat": 43.2141,
        "lon": 27.9147
    },
    "odesa": {
        "name": "Одесса",
        "lat": 46.4825,
        "lon": 30.7233
    }
}


def send_telegram_message(text):
    if not BOT_TOKEN:
        print("[ERROR] TELEGRAM_BOT_TOKEN is missing.")
        return False

    if not CHAT_ID:
        print("[ERROR] TELEGRAM_CHAT_ID is missing.")
        return False

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    try:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json"
            },
            method="POST"
        )

        with urllib.request.urlopen(request, timeout=20) as response:
            result = json.loads(response.read().decode("utf-8"))

        if result.get("ok"):
            print("[SUCCESS] Telegram message sent.")
            return True

        print(f"[ERROR] Telegram API error: {result}")
        return False

    except Exception as error:
        print(f"[ERROR] Telegram request failed: {error}")
        return False


def get_weather(location):
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={location['lat']}"
        f"&longitude={location['lon']}"
        "&current=temperature_2m,relative_humidity_2m,"
        "apparent_temperature,precipitation,rain,showers,snowfall,"
        "weather_code,wind_speed_10m,wind_gusts_10m"
        "&timezone=auto"
    )

    try:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "AURA-Meteo-Bot/1.0"
            }
        )

        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))

    except Exception as error:
        print(
            f"[ERROR] Failed to get weather "
            f"for {location['name']}: {error}"
        )
        return None


def check_location(location):
    data = get_weather(location)

    if not data or "current" not in data:
        return []

    current = data["current"]

    temperature = current.get("temperature_2m")
    apparent = current.get("apparent_temperature")
    precipitation = current.get("precipitation", 0) or 0
    rain = current.get("rain", 0) or 0
    showers = current.get("showers", 0) or 0
    snowfall = current.get("snowfall", 0) or 0
    wind = current.get("wind_speed_10m", 0) or 0
    gusts = current.get("wind_gusts_10m", 0) or 0
    weather_code = current.get("weather_code")

    alerts = []

    # Сильный ветер
    if gusts >= 70:
        alerts.append(
            f"💨 Очень сильный ветер: порывы до "
            f"<b>{gusts:.0f} км/ч</b>"
        )
    elif gusts >= 50:
        alerts.append(
            f"💨 Сильный ветер: порывы до "
            f"<b>{gusts:.0f} км/ч</b>"
        )

    # Очень низкая температура
    if temperature is not None and temperature <= -10:
        alerts.append(
            f"🥶 Очень низкая температура: "
            f"<b>{temperature:.1f}°C</b>"
        )

    # Очень высокая температура
    if temperature is not None and temperature >= 35:
        alerts.append(
            f"🔥 Очень высокая температура: "
            f"<b>{temperature:.1f}°C</b>"
        )

    # Осадки
    if precipitation >= 5:
        alerts.append(
            f"🌧 Сильные осадки: <b>{precipitation:.1f} мм</b>"
        )

    # Сильный дождь
    if rain >= 5 or showers >= 5:
        alerts.append(
            f"☔ Сильный дождь: "
            f"<b>{max(rain, showers):.1f} мм</b>"
        )

    # Снег
    if snowfall >= 2:
        alerts.append(
            f"❄️ Снег: <b>{snowfall:.1f} см</b>"
        )

    # Коды опасной погоды Open-Meteo
    dangerous_codes = {
        65: "Сильный дождь",
        67: "Сильный ледяной дождь",
        75: "Сильный снег",
        82: "Сильные ливни",
        95: "Гроза",
        96: "Гроза с градом",
        99: "Сильная гроза с градом"
    }

    if weather_code in dangerous_codes:
        condition = dangerous_codes[weather_code]

        # Не дублируем дождь, если уже есть конкретное предупреждение
        if not any(condition in alert for alert in alerts):
            alerts.append(f"⚠️ {condition}")

    if alerts:
        message = (
            f"<b>⚠️ AURA METEO</b>\n\n"
            f"<b>{location['name']}</b>\n"
            f"Температура: {temperature:.1f}°C\n"
            f"Ощущается: {apparent:.1f}°C\n"
            f"Ветер: {wind:.0f} км/ч\n"
            f"Порывы: {gusts:.0f} км/ч\n\n"
            + "\n".join(f"• {alert}" for alert in alerts)
        )

        return [message]

    return []


def main():
    print("Checking meteo conditions...")

    if not BOT_TOKEN:
        print("[ERROR] TELEGRAM_BOT_TOKEN is missing.")
        return

    if not CHAT_ID:
        print("[ERROR] TELEGRAM_CHAT_ID is missing.")
        return

    all_alerts = []

    for location in LOCATIONS.values():
        alerts = check_location(location)
        all_alerts.extend(alerts)

    if all_alerts:
        for message in all_alerts:
            send_telegram_message(message)
    else:
        print("No alert conditions detected.")

    print("Execution completed.")
    if __name__ == "__main__":
    main()
