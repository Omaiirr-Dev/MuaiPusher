import json
import os
import pathlib

from google import genai
from google.genai import types

PARSE_PROMPT = """You are parsing an Islamic prayer timetable image from a UK mosque.
Return ONLY valid JSON with no extra text, no markdown code fences, no prose.

Required structure:
{
  "week_label": "Sha'ban 1447 / Jan–Feb 2026",
  "prayers": [
    {
      "date": "2026-01-20",
      "day": "Tuesday",
      "fajr_start": "06:26",
      "fajr_jamaat": "07:15",
      "sunrise": "08:06",
      "zuhr_start": "12:23",
      "zuhr_jamaat": "13:00",
      "asr_start": "14:48",
      "asr_jamaat": "15:15",
      "maghrib_start": "16:32",
      "maghrib_jamaat": "16:37",
      "isha_start": "18:12",
      "isha_jamaat": "20:00"
    }
  ]
}

Rules:
- Extract EVERY day row in the image — do not stop early. Include all days visible.
- All times in 24-hour HH:MM format.
- Dates in YYYY-MM-DD format. Infer the year and month from any header text visible.
- If a Jamaat cell contains a ditto mark (" or '' or the word ditto) it means unchanged from the previous day — resolve it to the last known Jamaat time for that prayer.
- Never output a ditto mark in the JSON — always output an actual time.
- If no timetable can be found at all, return exactly: {"error": "not_found"}
"""


def extract_schedule(image_path: pathlib.Path) -> dict:
    """Send image directly to Gemini Vision and return parsed schedule dict."""
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    print("Sending image to Gemini 2.0 Flash Lite for parsing...")
    img_bytes = image_path.read_bytes()

    response = client.models.generate_content(
        model="gemini-2.0-flash-lite",
        contents=[
            PARSE_PROMPT,
            types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"),
        ],
        config=types.GenerateContentConfig(max_output_tokens=8000),
    )

    raw = response.text.strip()
    print(f"Gemini raw response (first 300 chars):\n{raw[:300]}\n---")

    # Strip markdown code fences if model ignores instructions
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    data = json.loads(raw)

    if "error" in data:
        raise ValueError(f"Could not parse timetable: {data['error']}")

    # Carry forward any null jamaat values (Gemini sometimes returns null for ditto rows)
    JAMAAT_FIELDS = ["fajr_jamaat", "zuhr_jamaat", "asr_jamaat", "maghrib_jamaat", "isha_jamaat"]
    last_known = {}
    for entry in data.get("prayers", []):
        for field in JAMAAT_FIELDS:
            if entry.get(field):
                last_known[field] = entry[field]
            elif field in last_known:
                entry[field] = last_known[field]

    return data
