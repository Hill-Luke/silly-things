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
from pydub import AudioSegment
from edge_tts.exceptions import NoAudioReceived
import wave
import sys
from piper import PiperVoice, SynthesisConfig
import subprocess
import tempfile
import xml.etree.ElementTree as ET
# ------------------------
# FFMPEG Setup (Mac)
# ------------------------
ffmpeg_path = Path(which("ffmpeg"))
ffprobe_path = Path(which("ffprobe"))

os.environ["PATH"] = f"{ffmpeg_path.parent};" + os.environ["PATH"]
os.environ["FFMPEG_BINARY"] = str(ffmpeg_path)
os.environ["FFPROBE_BINARY"] = str(ffprobe_path)

if not ffmpeg_path.exists():
    raise FileNotFoundError("ffmpeg not found at expected location.")


AudioSegment.converter = str(ffmpeg_path)
AudioSegment.ffprobe = str(ffprobe_path)

nest_asyncio.apply()
pygame.mixer.init()

# ------------------------
# Paths and Config
# ------------------------
BASE_DIR = Path(__file__).resolve().parent / "shrq_radio"
TTS_DIR = Path(__file__).resolve().parent / "TTS_tests"
MUSIC_DIR = BASE_DIR / "data/music"
NPR_DIR = BASE_DIR / "data/npr_ntnl"
TPR_DIR = BASE_DIR / "data/tpr_local"
RESPONSES_DIR = BASE_DIR / "data/dj_responses"
OUTPUT_DIR = BASE_DIR / "output"
JINGLE_DIR = BASE_DIR / "jingles"


NPR_URL = "http://public.npr.org/anon.npr-mp3/npr/news/newscast.mp3?_kip_ipx=1006340484-1748098441"

SHRQ_THEME = JINGLE_DIR / "shrq_tagline.mp3"
STRANGE_TASTE = JINGLE_DIR / "shrq_strange_taste.mp3"
DONT_COMPLAIN = JINGLE_DIR / "shrq_dont_complain.mp3"
CANT_DEFUND = JINGLE_DIR / "shrq_cant_defund.mp3"

jingles=[SHRQ_THEME,STRANGE_TASTE,DONT_COMPLAIN,CANT_DEFUND]


#TPR_URL = "https://cpa.ds.npr.org/s188/audio/2025/05/tpr-news-now-0516.mp3"

# ------------------------
# Ensure folder structure
# ------------------------
def ensure_folder_structure(base):
    for folder in [MUSIC_DIR, NPR_DIR, TPR_DIR, RESPONSES_DIR, OUTPUT_DIR]:
        folder.mkdir(parents=True, exist_ok=True)


# ------------------------
# Getting latest TPR
# ------------------------

def get_latest_tpr_url():
    rss_feed = "https://www.tpr.org/podcast/tpr-news-now/rss.xml"
    response = requests.get(rss_feed)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch TPR RSS feed (status code {response.status_code})")

    root = ET.fromstring(response.content)
    for item in root.findall(".//item"):
        enclosure = item.find("enclosure")
        if enclosure is not None:
            url = enclosure.attrib.get("url")
            if url and url.endswith(".mp3"):
                return url

    raise Exception("No valid TPR MP3 link found in the RSS feed.")

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


# TTS Parameters

syn_config=SynthesisConfig(
    volume=1.2,             # Slight boost for presence in radio context
    length_scale=1.05,      # Closer to natural speed, less robotic
    noise_scale=0.667,      # Introduces some tonal variation (intonation)
    noise_w_scale=0.8,      # Adds variation in pronunciation and rhythm
    normalize_audio=True,   # Ensures consistent output loudness
)



async def synthesize_and_save(text, out_path):
    if not text.strip():
        raise ValueError("TTS input text is empty. Cannot synthesize.")

    print(f"[TTS] Synthesizing:\n{text}")
    print(f"[TTS] Saving to: {out_path}")

    # Load the voice model once (outside this function if performance becomes an issue)
    voice = PiperVoice.load(f"{TTS_DIR}/en_US-ryan-high.onnx")

    # Create a temporary WAV file to write the raw audio
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
        wav_path = tmp_wav.name
        with wave.open(wav_path, "wb") as wav_file:
            voice.synthesize_wav(text, wav_file, syn_config=syn_config)

    # Convert WAV to MP3 using ffmpeg
    subprocess.run([
        "ffmpeg", "-y",
        "-i", wav_path,
        "-codec:a", "libmp3lame",
        "-qscale:a", "2",
        str(out_path)
    ], check=True)

    # Clean up temporary WAV file
    os.remove(wav_path)

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
    tpr_url = get_latest_tpr_url()
    download_mp3(tpr_url, tpr_path)

    # Random playlist
    music_files = list(MUSIC_DIR.glob("*.mp3"))
    if len(music_files) < 10:
        print("❌ Not enough songs in the music folder. Please add more.")
        return


    songs = random.sample(music_files, 30)
    news_clip = random.choice([npr_path, tpr_path])
    playlist = songs + [news_clip] + jingles
    random.shuffle(playlist)

    playlist=[SHRQ_THEME]+playlist

    print("\nFinal Playlist:")
    for i, track in enumerate(playlist):
        print(f"{i+1}. {Path(track).name}")

    client = ollama.Client(host='http://127.0.0.1:11434')
    dj_response_map = {}
    response_paths = {}
    response_counter = 0

    for i, track in enumerate(playlist):
        if track == npr_path:
            prompt = "Say: 'Up next, some national news from NPR'"
        elif track == tpr_path:
            prompt = "Say: 'Up next, some local news from Texas Public Radio'"
        elif track in jingles:
            continue
        elif random.random() < 0.5:
            continue
        else:
            md = extract_metadata(track)
            prompt = (
                f"You will act as a radio DJ for S-H-R-Q with a fun and upbeat tone. Do not simulate sound effects or music. "
                f"Say: 'Up next: here is {md['title']} by {md['artist']} from the album {md['album']}. You're listening to S-H-R-Q Radio!'"
            )

        result = client.chat(model='llama3.2:1b', messages=[{"role": "user", "content": prompt}])
        clean = re.sub(r"<think>.*?</think>", "", result['message']['content'], flags=re.DOTALL).strip()

        response_counter += 1
        response_path = RESPONSES_DIR / f"response_{response_counter}.mp3"
        await synthesize_and_save(clean, response_path)

        key = track.name
        dj_response_map[key] = response_counter
        response_paths[key] = response_path

    # Signoff
    signoff_prompt = (
        "You are signing off for the day as a DJ on S-H-R-Q. Give a fun, friendly farewell, no sound effects."
    )
    signoff_result = client.chat(model='llama3.2:1b', messages=[{"role": "user", "content": signoff_prompt}])
    signoff_text = re.sub(r"<think>.*?</think>", "", signoff_result['message']['content'], flags=re.DOTALL).strip()
    signoff_path = RESPONSES_DIR / "response_signoff.mp3"
    await synthesize_and_save(signoff_text, signoff_path)

    with open(BASE_DIR / "dj_response_map.json", "w") as f:
        json.dump(dj_response_map, f)

    # Stitch final mix
    final_mix = AudioSegment.silent(duration=0)
    for track in playlist:
        key = track.name
        if key in response_paths and response_paths[key].exists():
            final_mix += AudioSegment.from_file(response_paths[key]) + AudioSegment.silent(duration=500)
        final_mix += AudioSegment.from_file(track) + AudioSegment.silent(duration=1000)

    if signoff_path.exists():
        final_mix += AudioSegment.from_file(signoff_path)

    out_path = OUTPUT_DIR / f"shrq_radio_broadcast.mp3"
    final_mix.export(out_path, format="mp3")
    print(f"\n✅ Broadcast saved to: {out_path}")

if __name__ == "__main__":
    asyncio.run(main())
