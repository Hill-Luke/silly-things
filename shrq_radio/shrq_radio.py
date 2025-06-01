import datetime
import random
import os
import json
import re
import requests
import asyncio
from pathlib import Path
from pydub.utils import which
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3
import edge_tts
import pygame
import nest_asyncio
import ollama
from pydub.utils import which




# Force pydub to find ffmpeg/ffprobe by setting environment vars
ffmpeg_path = Path("C:/ffmpeg-7.1.1-essentials_build/bin/ffmpeg.exe")
ffprobe_path = Path("C:/ffmpeg-7.1.1-essentials_build/bin/ffprobe.exe")

os.environ["PATH"] = f"{ffmpeg_path.parent};" + os.environ["PATH"]
os.environ["FFMPEG_BINARY"] = str(ffmpeg_path)
os.environ["FFPROBE_BINARY"] = str(ffprobe_path)

# ✅ Optional sanity check
if not ffmpeg_path.exists():
    raise FileNotFoundError("ffmpeg not found at expected location.")
if not ffprobe_path.exists():
    raise FileNotFoundError("ffprobe not found at expected location.")
from pydub import AudioSegment

AudioSegment.converter = str(ffmpeg_path)
AudioSegment.ffprobe = str(ffprobe_path)


nest_asyncio.apply()
pygame.mixer.init()

# ------------------------
# Paths and Config
# ------------------------
BASE_DIR = Path(__file__).resolve().parent / "shrq_radio"
MUSIC_DIR = BASE_DIR / "data/music"
NPR_DIR = BASE_DIR / "data/npr_ntnl"
TPR_DIR = BASE_DIR / "data/tpr_local"
RESPONSES_DIR = BASE_DIR / "data/dj_responses"
OUTPUT_DIR = BASE_DIR / "output"

NPR_URL = "http://public.npr.org/anon.npr-mp3/npr/news/newscast.mp3?_kip_ipx=1006340484-1748098441"
TPR_URL = "https://cpa.ds.npr.org/s188/audio/2025/05/tpr-news-now-0516.mp3"

# ------------------------
# Ensure folder structure
# ------------------------
def ensure_folder_structure(base):
    for folder in [MUSIC_DIR, NPR_DIR, TPR_DIR, RESPONSES_DIR, OUTPUT_DIR]:
        folder.mkdir(parents=True, exist_ok=True)

# ------------------------
# Download helper
# ------------------------
def download_mp3(url, save_path):
    try:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            with open(save_path, "wb") as file:
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        file.write(chunk)
            print(f"✅ Downloaded: {save_path}")
        else:
            print(f"❌ Failed to download: {url} (status {response.status_code})")
    except Exception as e:
        print(f"❌ Error: {e}")

# ------------------------
# TTS Synthesis
# ------------------------
async def synthesize_and_save(text, out_path):
    communicate = edge_tts.Communicate(text, voice="en-US-AndrewNeural")
    await communicate.save(str(out_path))

# ------------------------
# Extract MP3 metadata
# ------------------------
def extract_metadata(file_path):
    try:
        audio = MP3(file_path, ID3=EasyID3)
        return {
            "title": audio.get("title", ["Unknown"])[0],
            "artist": audio.get("artist", ["Unknown"])[0],
            "album": audio.get("album", ["Unknown"])[0],
        }
    except:
        return {"title": "Unknown", "artist": "Unknown", "album": "Unknown"}

# ------------------------
# Main function
# ------------------------
async def main():
    ensure_folder_structure(BASE_DIR)
    timestamp = datetime.datetime.now().strftime("%Y_%m_%d")
    with open("timestamp.log", "w") as f:
        f.write(timestamp)
    print(f"Current date and time saved to timestamp.log: {timestamp}")

    npr_path = NPR_DIR / f"npr_audio_{timestamp}.mp3"
    tpr_path = TPR_DIR / f"tpr_audio_{timestamp}.mp3"

    print("Downloading NPR audio...")
    download_mp3(NPR_URL, npr_path)
    print("Downloading TPR audio...")
    download_mp3(TPR_URL, tpr_path)

    # Random playlist
    music_files = list(MUSIC_DIR.glob("*.mp3"))
    if len(music_files) < 10:
        print("❌ Not enough songs in the music folder. Please add more.")
        return

    songs = random.sample(music_files, 10)
    news_clip = random.choice([npr_path, tpr_path])
    playlist = songs + [news_clip]
    random.shuffle(playlist)

    print("\nFinal Playlist:")
    for i, track in enumerate(playlist):
        print(f"{i+1}. {track.name}")

    client = ollama.Client(host='http://127.0.0.1:11434')
    dj_response_map = {}
    response_paths = {}
    response_counter = 0

    for i, track in enumerate(playlist):
        if track == npr_path:
            prompt = "Say: 'Up next, some national news from NPR'"
        elif track == tpr_path:
            prompt = "Say: 'Up next, some local news from Texas Public Radio'"
        elif random.random() < 0.5:
            continue
        else:
            md = extract_metadata(track)
            prompt = (
                f"You will act as a radio DJ for S-H-R-Q with a fun and upbeat tone. Do not simulate sound effects or music. "
                f"Say: 'Up next: here is {md['title']} by {md['artist']} from the album {md['album']}. You're listening to S-H-R-Q Radio!'"
            )

        result = client.chat(model='deepseek-r1:14b', messages=[{"role": "user", "content": prompt}])
        clean = re.sub(r"<think>.*?</think>", "", result['message']['content'], flags=re.DOTALL).strip()

        response_counter += 1
        response_path = RESPONSES_DIR / f"response_{response_counter}.mp3"
        await synthesize_and_save(clean, response_path)

        dj_response_map[i] = response_counter
        response_paths[i] = response_path

    # Signoff
    signoff_prompt = (
        "You are signing off for the day as a DJ on S-H-R-Q. Give a fun, friendly farewell, no sound effects."
    )
    signoff_result = client.chat(model='deepseek-r1:14b', messages=[{"role": "user", "content": signoff_prompt}])
    signoff_text = re.sub(r"<think>.*?</think>", "", signoff_result['message']['content'], flags=re.DOTALL).strip()
    signoff_path = RESPONSES_DIR / "response_signoff.mp3"
    await synthesize_and_save(signoff_text, signoff_path)

    with open(BASE_DIR / "dj_response_map.json", "w") as f:
        json.dump(dj_response_map, f)

    # Stitch final mix
    AudioSegment.converter = which("ffmpeg")
    AudioSegment.ffprobe = which("ffprobe")

    final_mix = AudioSegment.silent(duration=0)
    for i, track in enumerate(playlist):
        if i in response_paths:
            final_mix += AudioSegment.from_file(response_paths[i]) + AudioSegment.silent(duration=500)
        final_mix += AudioSegment.from_file(track) + AudioSegment.silent(duration=1000)

    if signoff_path.exists():
        final_mix += AudioSegment.from_file(signoff_path)

    out_path = OUTPUT_DIR / f"shrq_radio_broadcast_{timestamp}.mp3"
    final_mix.export(out_path, format="mp3")
    print(f"\n✅ Broadcast saved to: {out_path}")

if __name__ == "__main__":
    asyncio.run(main())
