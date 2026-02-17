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


def _post(title: str, body: str, url: str | None = None) -> None:
    ntfy_url = url or os.environ["NTFY_URL"]
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


def _backend_url() -> str:
    """Derive the muaibackend ntfy URL from the main NTFY_URL."""
    base = os.environ["NTFY_URL"].rsplit("/", 1)[0]
    return f"{base}/muaibackend"


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

    _post(title, "\n".join(lines))
    print(f"Sent: {title}")


def send_schedule_summary(prayers: list) -> None:
    """Post one notification per day to muaibackend whenever a new calendar is detected."""
    url = _backend_url()
    total = len(prayers)
    for i, p in enumerate(prayers, 1):
        date = p.get("date", "?")[-5:]  # MM-DD
        day = (p.get("day") or "")
        fajr    = fmt_12h(p["fajr_start"])    if p.get("fajr_start")    else "—"
        fajr_j  = fmt_12h(p["fajr_jamaat"])   if p.get("fajr_jamaat")   else "—"
        sunrise = fmt_12h(p["sunrise"])        if p.get("sunrise")       else "—"
        zuhr    = fmt_12h(p["zuhr_start"])     if p.get("zuhr_start")    else "—"
        zuhr_j  = fmt_12h(p["zuhr_jamaat"])    if p.get("zuhr_jamaat")   else "—"
        asr     = fmt_12h(p["asr_start"])      if p.get("asr_start")     else "—"
        asr_j   = fmt_12h(p["asr_jamaat"])     if p.get("asr_jamaat")    else "—"
        mghrb   = fmt_12h(p["maghrib_start"])  if p.get("maghrib_start") else "—"
        mghrb_j = fmt_12h(p["maghrib_jamaat"]) if p.get("maghrib_jamaat") else "—"
        isha    = fmt_12h(p["isha_start"])     if p.get("isha_start")    else "—"
        isha_j  = fmt_12h(p["isha_jamaat"])    if p.get("isha_jamaat")   else "—"
        body = (
            f"🕋 Fajr    {fajr} (J {fajr_j})\n"
            f"🌄 Sunrise {sunrise}\n"
            f"☀️ Zuhr    {zuhr} (J {zuhr_j})\n"
            f"⛅ Asr     {asr} (J {asr_j})\n"
            f"🌅 Maghrib {mghrb} (J {mghrb_j})\n"
            f"🌙 Isha    {isha} (J {isha_j})"
        )
        _post(f"📅 {date} {day} ({i}/{total})", body, url=url)
    print(f"Sent to muaibackend: {total} daily notifications")


def send_unavailable_notification() -> None:
    _post(
        "⚠️ Prayer Schedule Unavailable",
        "No schedule found. Will retry next check.",
    )
    print("Sent: schedule unavailable notification")
