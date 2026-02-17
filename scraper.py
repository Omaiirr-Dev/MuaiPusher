import pathlib
import requests
from bs4 import BeautifulSoup

SITE_URL = "https://muai.org.uk"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def get_calendar_image_url() -> str:
    resp = requests.get(SITE_URL, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    for a in soup.find_all("a", href=True):
        if "Prayer Times Calendar" in a.get_text():
            return a["href"]

    raise ValueError("Prayer Times Calendar link not found on homepage")


def download_image(url: str, dest: pathlib.Path) -> None:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    print(f"Saved calendar image to {dest}")


if __name__ == "__main__":
    image_url = get_calendar_image_url()
    print(f"Found calendar image: {image_url}")

    out_path = pathlib.Path("calendar.jpg")
    download_image(image_url, out_path)
    # TODO: feed out_path to GPT-4 Vision, push to NTFY
