import base64
import json
import os
import pathlib

from openai import OpenAI

PROMPT = """You are extracting an Islamic prayer timetable from an image. It may cover a full month.
Return ONLY valid JSON with no extra text, no markdown code fences, no prose.

Required structure:
{
  "week_label": "Sha'ban 1447 / Feb–Mar 2026",
  "prayers": [
    {
      "date": "2026-02-17",
      "day": "Monday",
      "fajr_start": "05:54",
      "fajr_jamaat": "06:45",
      "sunrise": "07:34",
      "zuhr_start": "12:26",
      "zuhr_jamaat": "13:00",
      "asr_start": "15:22",
      "asr_jamaat": "15:45",
      "maghrib_start": "17:11",
      "maghrib_jamaat": "17:16",
      "isha_start": "18:45",
      "isha_jamaat": "20:00"
    }
  ]
}

Rules:
- Extract EVERY row in the image — do not stop early. Include all days visible.
- All times in 24-hour HH:MM format.
- Dates in YYYY-MM-DD format. Infer the year and month from the calendar header.
- If a Jamaat cell contains a ditto mark (" or '' or ditto) it means the Jamaat time is unchanged from the previous day — use the last known Jamaat time for that prayer instead.
- Never output a ditto mark in the JSON — always resolve it to an actual time.
- If you cannot find a timetable, return exactly: {"error": "not_found"}
"""


def extract_schedule(image_path: pathlib.Path) -> dict:
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    image_data = base64.b64encode(image_path.read_bytes()).decode("utf-8")
    suffix = image_path.suffix.lstrip(".").lower()
    mime = f"image/{'jpeg' if suffix in ('jpg', 'jpeg') else suffix}"

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{image_data}"},
                    },
                ],
            }
        ],
        max_tokens=16000,
    )

    raw = response.choices[0].message.content.strip()

    # Strip markdown code fences if model ignores instructions
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    data = json.loads(raw)

    if "error" in data:
        raise ValueError(f"Vision could not parse timetable: {data['error']}")

    return data
