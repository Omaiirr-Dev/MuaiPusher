import json
import pathlib
from datetime import datetime, timedelta

import pytz

SCHEDULE_FILE = pathlib.Path("schedule.json")
UK_TZ = pytz.timezone("Europe/London")


def save_schedule(data: dict) -> None:
    SCHEDULE_FILE.write_text(json.dumps(data, indent=2))


def load_schedule() -> dict | None:
    if not SCHEDULE_FILE.exists():
        return None
    return json.loads(SCHEDULE_FILE.read_text())


def get_todays_prayers() -> dict | None:
    schedule = load_schedule()
    if not schedule:
        return None
    today = datetime.now(UK_TZ).strftime("%Y-%m-%d")
    for entry in schedule.get("prayers", []):
        if entry.get("date") == today:
            return entry
    return None


def time_until(target_hhmm: str) -> str:
    """Return 'Xh Ym' from now (UK time) until the given HH:MM time today."""
    now = datetime.now(UK_TZ)
    h, m = map(int, target_hhmm.split(":"))
    target = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    delta = target - now
    total_minutes = int(delta.total_seconds() // 60)
    hours, mins = divmod(total_minutes, 60)
    if hours > 0:
        return f"{hours}h {mins:02d}m"
    return f"{mins}m"


def fmt_12h(hhmm: str) -> str:
    """Convert 24h HH:MM to 12h h:MM AM/PM."""
    h, m = map(int, hhmm.split(":"))
    period = "AM" if h < 12 else "PM"
    h12 = h % 12 or 12
    return f"{h12}:{m:02d} {period}"
