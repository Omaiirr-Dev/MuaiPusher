import os

import requests

from schedule import fmt_12h, time_until

PRAYER_EMOJIS = {
    "fajr": "🕋",
    "zuhr": "☀️",
    "asr": "⛅",
    "maghrib": "🌅",
    "isha": "🌙",
}

PRAYER_NAMES = {
    "fajr": "Fajr",
    "zuhr": "Zuhr",
    "asr": "Asr",
    "maghrib": "Maghrib",
    "isha": "Isha",
}


def _post(title: str, body: str) -> None:
    ntfy_url = os.environ["NTFY_URL"]
    requests.post(
        ntfy_url,
        data=body.encode("utf-8"),
        headers={
            "Title": title.encode("utf-8"),
            "Priority": "default",
            "Content-Type": "text/plain; charset=utf-8",
        },
        timeout=10,
    )


def send_prayer_notification(
    prayer: str,
    start: str,
    jamaat: str,
    next_prayer: str | None,
    next_start: str | None,
    sunrise: str | None = None,
) -> None:
    emoji = PRAYER_EMOJIS[prayer]
    name = PRAYER_NAMES[prayer]
    title = f"{emoji} {name} has started • {fmt_12h(start)}"

    lines = [f"(Jamaat {fmt_12h(jamaat)})"]

    if prayer == "fajr" and sunrise:
        lines[0] += f" - [Sunrise {fmt_12h(sunrise)}]"

    if next_prayer and next_start:
        next_name = PRAYER_NAMES[next_prayer]
        until = time_until(next_start)
        lines.append(f"⏰ {until} until {next_name} • {fmt_12h(next_start)}")
    else:
        lines.append("⏰ Next prayer time not yet available")

    lines.append("")
    lines.append("MADINATUL ULOOM")

    _post(title, "\n".join(lines))
    print(f"Sent: {title}")


def send_unavailable_notification() -> None:
    _post(
        "⚠️ Prayer Schedule Unavailable",
        "No schedule found. Will retry next check.\n\nMADINATUL ULOOM",
    )
    print("Sent: schedule unavailable notification")
