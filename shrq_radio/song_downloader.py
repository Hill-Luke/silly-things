import requests
from bs4 import BeautifulSoup
import os
import json
import html
from pathlib import Path

# Define base and download directories using pathlib
BASE_DIR = Path(__file__).resolve().parent / "shrq_radio"
DOWNLOAD_DIR = BASE_DIR / "data/music"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

def get_mp3_info():
    url = "https://kutkutx.studio/category/song-of-the-day"
    res = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(res.content, "html.parser")

    button = soup.find("a", class_="listen-button")
    if not button:
        return None, None

    raw_params = button.get("data-params")
    if not raw_params:
        return None, None

    decoded_json = html.unescape(raw_params)
    params = json.loads(decoded_json)

    mp3_url = params.get("mp3_url")
    song_name = params.get("name", "kutx_song_of_the_day")
    return mp3_url, song_name

def sanitize_filename(name):
    return (
        name.lower()
        .replace("–", "-")
        .replace("’", "")
        .replace("'", "")
        .replace("(", "")
        .replace(")", "")
        .replace(" ", "_")
        .replace("/", "-")
        + ".mp3"
    )

def download_mp3(mp3_url, song_name):
    filename = sanitize_filename(song_name)
    save_path = DOWNLOAD_DIR / filename

    print(f"🎧 Downloading from: {mp3_url}")
    res = requests.get(mp3_url, headers=HEADERS)

    if res.status_code == 200:
        DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
        with open(save_path, "wb") as f:
            f.write(res.content)
        print(f"✅ Saved to: {save_path}")
    else:
        print(f"❌ Download failed. Status code: {res.status_code}")

if __name__ == "__main__":
    mp3_url, song_name = get_mp3_info()
    if mp3_url:
        print(f"📀 Song found: {song_name}")
        download_mp3(mp3_url, song_name)
    else:
        print("❌ Could not find MP3 info.")
