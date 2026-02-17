"""
MuairPusher — main orchestrator.
Intended to run every minute via Railway cron.

Env vars required:
  OPENAI_API_KEY
  NTFY_URL
"""

import json
import os
import pathlib
from datetime import datetime

import pytz

# Load .env file if present (local dev only)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from notifier import send_prayer_notification, send_unavailable_notification
from schedule import get_todays_prayers
from scraper import download_image, get_calendar_image_url
from vision import extract_schedule

UK_TZ = pytz.timezone("Europe/London")

CALENDAR_IMAGE = pathlib.Path("calendar.jpg")
LAST_URL_FILE = pathlib.Path("last_url.txt")
SCHEDULE_FILE = pathlib.Path("schedule.json")
SENT_FILE = pathlib.Path("sent.json")

# Prayer order with the field names in schedule.json
PRAYERS = [
    ("fajr",    "fajr_start",    "fajr_jamaat"),
    ("zuhr",    "zuhr_start",    "zuhr_jamaat"),
    ("asr",     "asr_start",     "asr_jamaat"),
    ("maghrib", "maghrib_start", "maghrib_jamaat"),
    ("isha",    "isha_start",    "isha_jamaat"),
]


def load_last_url() -> str | None:
    if LAST_URL_FILE.exists():
        return LAST_URL_FILE.read_text().strip()
    return None


def save_last_url(url: str) -> None:
    LAST_URL_FILE.write_text(url)


def load_sent() -> dict:
    if SENT_FILE.exists():
        return json.loads(SENT_FILE.read_text())
    return {}


def save_sent(sent: dict) -> None:
    SENT_FILE.write_text(json.dumps(sent))


def mark_sent(date_str: str, prayer: str) -> None:
    sent = load_sent()
    sent.setdefault(date_str, [])
    if prayer not in sent[date_str]:
        sent[date_str].append(prayer)
    save_sent(sent)


def already_sent(date_str: str, prayer: str) -> bool:
    return prayer in load_sent().get(date_str, [])


def refresh_schedule_if_needed() -> None:
    try:
        image_url = get_calendar_image_url()
    except Exception as e:
        print(f"Could not scrape homepage: {e}")
        return

    last_url = load_last_url()
    if image_url == last_url and SCHEDULE_FILE.exists():
        print(f"Calendar unchanged ({image_url}), skipping Vision call.")
        return

    print(f"New/changed calendar URL: {image_url}")
    try:
        download_image(image_url, CALENDAR_IMAGE)
        data = extract_schedule(CALENDAR_IMAGE)
        SCHEDULE_FILE.write_text(json.dumps(data, indent=2))
        save_last_url(image_url)
        print(f"Schedule updated: {data.get('week_label', '?')}")
    except Exception as e:
        print(f"Failed to refresh schedule: {e}")


def main() -> None:
    refresh_schedule_if_needed()

    today_entry = get_todays_prayers()
    if not today_entry:
        print("No schedule entry for today — sending unavailable notification.")
        send_unavailable_notification()
        return

    today_str = today_entry["date"]
    now = datetime.now(UK_TZ)
    current_hhmm = now.strftime("%H:%M")

    for i, (prayer, start_field, jamaat_field) in enumerate(PRAYERS):
        start = today_entry.get(start_field)
        jamaat = today_entry.get(jamaat_field)

        if not start or not jamaat:
            continue

        if current_hhmm != start:
            continue

        if already_sent(today_str, prayer):
            continue

        # Determine next prayer
        next_prayer = None
        next_start = None
        if i + 1 < len(PRAYERS):
            np_key, np_start_field, _ = PRAYERS[i + 1]
            ns = today_entry.get(np_start_field)
            if ns:
                next_prayer = np_key
                next_start = ns

        sunrise = today_entry.get("sunrise") if prayer == "fajr" else None

        send_prayer_notification(
            prayer=prayer,
            start=start,
            jamaat=jamaat,
            next_prayer=next_prayer,
            next_start=next_start,
            sunrise=sunrise,
        )
        mark_sent(today_str, prayer)

    print(f"Tick done at {current_hhmm} UK time.")


if __name__ == "__main__":
    main()
