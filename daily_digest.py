"""Daily rolling 24-hour model-weather summary; Telegram secrets stay in Actions."""
import json
import math
import sys
import urllib.request
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode

from bot import BOT_TOKEN, CHAT_ID, LOCATIONS, send_telegram_message


def get_json(url):
    request = urllib.request.Request(url, headers={"User-Agent": "AURA-Meteo/2.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def series(data, key, end):
    hourly = data["hourly"]
    times = hourly["time"]
    values = hourly[key]
    if len(times) != len(values):
        raise ValueError("Incomplete time series")
    return [(t, v) for t, v in zip(times, values)
            if end - 86400 <= t <= end and number(v)]


def change(data, key, end, unit):
    points = series(data, key, end)
    if len(points) != 25 or points[0][0] != end - 86400 or points[-1][0] != end:
        return "нет полных данных за 24 часа"
    before, after = points[0][1], points[-1][1]
    return f"{before:.1f} → {after:.1f} {unit} ({after-before:+.1f})"


def weather_summary(location, end):
    params = dict(latitude=location["lat"], longitude=location["lon"],
                  hourly="temperature_2m,pressure_msl,wind_gusts_10m,precipitation",
                  past_days=2, forecast_days=1, timezone="GMT", timeformat="unixtime")
    data = get_json("https://api.open-meteo.com/v1/forecast?" + urlencode(params))
    lines = [f"<b>{location['name']}</b>",
             "Температура: " + change(data, "temperature_2m", end, "°C"),
             "Давление: " + change(data, "pressure_msl", end, "гПа")]
    for key, label, unit, operation in (
        ("wind_gusts_10m", "Максимальные порывы", "км/ч", max),
        ("precipitation", "Осадки за сутки", "мм", sum),
    ):
        values = [v for t, v in series(data, key, end) if t > end - 86400]
        lines.append(f"{label}: {operation(values):.1f} {unit}" if len(values) == 24
                     else f"{label}: нет полных данных")
    return "\n".join(lines)


def magnetic_summary(end):
    rows = get_json("https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json")

    if isinstance(rows, dict):
        for key in ("data", "values", "observations", "results"):
            candidate = rows.get(key)
            if isinstance(candidate, list):
                rows = candidate
                break

    if not isinstance(rows, list) or not rows:
        raise ValueError("Missing Kp data")

    values = []

    for row in rows:
        try:
            if isinstance(row, dict):
                time_value = (
                    row.get("time_tag")
                    or row.get("time")
                    or row.get("timestamp")
                    or row.get("date")
                )
                kp_value = (
                    row.get("Kp")
                    if row.get("Kp") is not None
                    else row.get("kp")
                )
                if kp_value is None:
                    kp_value = row.get("kp_index")
            elif isinstance(row, (list, tuple)) and len(row) >= 2:
                time_value, kp_value = row[0], row[1]
            else:
                continue

            if not time_value or kp_value is None:
                continue

            time_text = str(time_value).strip()
            if time_text.lower() in {"time_tag", "time", "timestamp", "date"}:
                continue

            when = datetime.fromisoformat(time_text.replace("Z", "+00:00"))
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)

            kp = float(kp_value)
            if end - 86400 < when.timestamp() <= end and math.isfinite(kp):
                values.append(kp)

        except (TypeError, ValueError, KeyError, IndexError):
            continue

    if not values:
        return "Магнитное поле: нет данных за период"

    return f"Магнитное поле: максимум Kp {max(values):.1f} (получено интервалов: {len(values)})"


def distance(lat1, lon1, lat2, lon2):
    a, b = math.radians(lat1), math.radians(lat2)
    h = math.sin((b-a)/2)**2 + math.cos(a)*math.cos(b)*math.sin(math.radians(lon2-lon1)/2)**2
    return 6371 * 2 * math.asin(math.sqrt(min(1, max(0, h))))


def quake_summary(end):
    data = get_json("https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_week.geojson")
    lines = ["<b>Землетрясения за сутки · USGS</b>"]
    for location in LOCATIONS.values():
        magnitudes = []
        for event in data["features"]:
            props = event["properties"]
            timestamp, magnitude = props.get("time"), props.get("mag")
            if not number(timestamp) or not number(magnitude):
                continue
            if not end - 86400 < timestamp / 1000 <= end:
                continue
            lon, lat = event["geometry"]["coordinates"][:2]
            if distance(location["lat"], location["lon"], lat, lon) <= 500:
                magnitudes.append(magnitude)
        value = f"{len(magnitudes)}, максимум M{max(magnitudes):.1f}" if magnitudes else "в каталоге событий нет"
        lines.append(f"{location['name']}, радиус 500 км: {value}")
    return "\n".join(lines)


def build_message(now=None):
    now = now or datetime.now(timezone.utc)
    end = int(now.timestamp()) // 3600 * 3600
    finish = datetime.fromtimestamp(end, timezone.utc)
    start = finish - timedelta(hours=24)
    sections = ["<b>AURA GEO METEO · изменения за сутки</b>",
                f"{start:%d.%m %H:%M} — {finish:%d.%m %H:%M} UTC"]
    failures = 0
    tasks = [(loc["name"], lambda loc=loc: weather_summary(loc, end)) for loc in LOCATIONS.values()]
    tasks += [("Магнитное поле", lambda: magnetic_summary(end)),
              ("Землетрясения", lambda: quake_summary(end))]
    for label, task in tasks:
        try:
            sections.append(task())
        except Exception as error:
            print(f"[ERROR] {label}: {type(error).__name__}")
            sections.append(f"{label}: источник временно недоступен")
            failures += 1
    sections.append("Погода — модельные данные Open-Meteo, Kp — NOAA SWPC.\nСводка за прошедшие 24 часа, не прогноз.")
    return "\n\n".join(sections), failures


def main():
    if not BOT_TOKEN or not CHAT_ID:
        print("[ERROR] Configure TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in Actions secrets.")
        return 1
    message, failures = build_message()
    if not send_telegram_message(message):
        return 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
