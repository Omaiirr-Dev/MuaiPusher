"""
MuairPusher — persistent worker.
Runs continuously on Railway as a long-running service (not a cron job).
Sleeps until each prayer start time, fires the notification, then sleeps until the next.
Checks for a new calendar image every 7 days (mosque updates ~weekly).

Env vars required:
  GEMINI_API_KEY
  NTFY_URL
"""

import json
import pathlib
import time
from datetime import datetime, timedelta

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
LAST_FETCH_FILE = pathlib.Path("last_fetch.txt")
SCHEDULE_FILE = pathlib.Path("schedule.json")

REFRESH_INTERVAL_DAYS = 7

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


def days_since_last_fetch() -> float:
    if not LAST_FETCH_FILE.exists():
        return float("inf")
    last = datetime.fromisoformat(LAST_FETCH_FILE.read_text().strip())
    return (datetime.now(UK_TZ) - last).total_seconds() / 86400


def save_fetch_timestamp() -> None:
    LAST_FETCH_FILE.write_text(datetime.now(UK_TZ).isoformat())


def refresh_schedule(force: bool = False) -> None:
    """Scrape the homepage and update schedule.json if due or URL changed."""
    days = days_since_last_fetch()
    if not force and days < REFRESH_INTERVAL_DAYS and SCHEDULE_FILE.exists():
        print(f"Last fetch was {days:.1f} days ago — next check in {REFRESH_INTERVAL_DAYS - days:.1f} days.")
        return

    try:
        image_url = get_calendar_image_url()
    except Exception as e:
        print(f"Could not scrape homepage: {e}")
        return

    last_url = load_last_url()
    if image_url == last_url and SCHEDULE_FILE.exists() and not force:
        print("Calendar URL unchanged, skipping Gemini call.")
        save_fetch_timestamp()
        return

    print(f"Fetching new calendar: {image_url}")
    try:
        download_image(image_url, CALENDAR_IMAGE)
        new_data = extract_schedule(CALENDAR_IMAGE)

        # Merge with existing schedule so old dates aren't lost mid-month
        existing = json.loads(SCHEDULE_FILE.read_text()) if SCHEDULE_FILE.exists() else {"prayers": []}
        existing_by_date = {e["date"]: e for e in existing.get("prayers", [])}
        for entry in new_data.get("prayers", []):
            existing_by_date[entry["date"]] = entry  # new entries overwrite, old ones kept
        merged_prayers = sorted(existing_by_date.values(), key=lambda e: e["date"])

        merged = {"week_label": new_data.get("week_label", ""), "prayers": merged_prayers}
        SCHEDULE_FILE.write_text(json.dumps(merged, indent=2))
        save_last_url(image_url)
        save_fetch_timestamp()
        print(f"Schedule merged: {len(merged_prayers)} days total ({new_data.get('week_label', '?')})")
    except Exception as e:
        print(f"Failed to refresh schedule: {e}")


def prayer_dt_today(hhmm: str) -> datetime:
    """Return a timezone-aware datetime for the given HH:MM today in UK time."""
    now = datetime.now(UK_TZ)
    h, m = map(int, hhmm.split(":"))
    return now.replace(hour=h, minute=m, second=0, microsecond=0)


def sleep_until(dt: datetime) -> None:
    """Block until the given datetime, printing a countdown."""
    now = datetime.now(UK_TZ)
    seconds = (dt - now).total_seconds()
    if seconds > 0:
        print(f"Sleeping {seconds/3600:.2f}h until {dt.strftime('%H:%M')} UK time...")
        time.sleep(seconds)


def run_day() -> None:
    """Handle all prayers for today, sleeping between each one."""
    today_entry = get_todays_prayers()

    if not today_entry:
        print("No schedule for today — sending unavailable notification.")
        send_unavailable_notification()
        # Retry in 30 minutes in case the mosque uploads the calendar later
        time.sleep(30 * 60)
        return

    print(f"Schedule loaded for {today_entry['date']}")
    now = datetime.now(UK_TZ)

    for i, (prayer, start_field, jamaat_field) in enumerate(PRAYERS):
        start = today_entry.get(start_field)
        jamaat = today_entry.get(jamaat_field)

        if not start or not jamaat:
            continue

        prayer_time = prayer_dt_today(start)

        # Skip prayers that have already passed today
        if prayer_time < now:
            print(f"Skipping {prayer} ({start}) — already passed.")
            continue

        # Sleep precisely until this prayer's start time
        sleep_until(prayer_time)

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


def sleep_until_midnight() -> None:
    """Sleep until just after UK midnight so we refresh for the new day."""
    now = datetime.now(UK_TZ)
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=1, second=0, microsecond=0)
    sleep_until(tomorrow)


def main() -> None:
    print("MuairPusher started.")
    while True:
        refresh_schedule()  # Only calls Gemini if 7 days have passed
        run_day()
        sleep_until_midnight()


if __name__ == "__main__":
    main()
