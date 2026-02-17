import json
import os
import pathlib

import pytesseract
from PIL import Image
from openai import OpenAI

PARSE_PROMPT = """You are parsing raw OCR text extracted from an Islamic prayer timetable image.
The text may contain noise, misaligned columns, or OCR errors — use context to correct them.
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
- Extract EVERY day row in the text — do not stop early. Include all days visible.
- All times in 24-hour HH:MM format.
- Dates in YYYY-MM-DD format. Infer the year and month from any header text visible.
- If a Jamaat cell contains a ditto mark (" or '' or the word ditto) it means unchanged from the previous day — resolve it to the last known Jamaat time for that prayer.
- Never output a ditto mark in the JSON — always output an actual time.
- OCR text may have garbled characters — use surrounding context (column position, adjacent values) to infer correct times.
- If no timetable can be found at all, return exactly: {"error": "not_found"}
"""


def ocr_image(image_path: pathlib.Path) -> str:
    """Run Tesseract OCR on the image and return raw extracted text."""
    img = Image.open(image_path)
    # Convert to grayscale to improve OCR accuracy on coloured timetable backgrounds
    img = img.convert("L")
    text = pytesseract.image_to_string(img, config="--psm 6")
    return text


def parse_text_to_schedule(ocr_text: str) -> dict:
    """Send OCR text to GPT-4o-mini and return parsed schedule dict."""
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": PARSE_PROMPT},
            {"role": "user", "content": ocr_text},
        ],
        max_tokens=8000,
    )

    raw = response.choices[0].message.content.strip()

    # Strip markdown code fences if model ignores instructions
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    data = json.loads(raw)

    if "error" in data:
        raise ValueError(f"Could not parse timetable from OCR text: {data['error']}")

    return data


def extract_schedule(image_path: pathlib.Path) -> dict:
    """Full pipeline: OCR image → parse text → return structured schedule."""
    print("Running Tesseract OCR...")
    ocr_text = ocr_image(image_path)
    print(f"OCR output (first 500 chars):\n{ocr_text[:500]}\n---")

    print("Sending OCR text to GPT-4o-mini for parsing...")
    return parse_text_to_schedule(ocr_text)
