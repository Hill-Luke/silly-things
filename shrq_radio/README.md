# SHRQ Radio

SHRQ Radio is a retro-style radio mix generator that combines DJ voiceovers with randomized music tracks, along with NPR and TPR news clips. It's designed for local use and outputs a single mixed MP3 file you can play as your own radio station.

## Features

- Pulls NPR and TPR news audio from public URLs
- Randomly generates a playlist from local MP3s
- Injects AI-generated DJ commentary between tracks
- Outputs a single MP3 mix playable anywhere
- CLI-based, no inputs required

**NOTE:** SHRQ Radio requires Python 3.12. Newer versions of python are not compatible

## Setup

1. **Install Python 3.11+**
3. **Install dependencies:**
4. Download and install FFmpeg (if not already installed):
  - Download from: https://www.gyan.dev/ffmpeg/builds/
  - Unzip and place the path to `ffmpeg.exe` and `ffprobe.exe` in `C:/ffmpeg-7.1.1-essentials_build/bin/`
4. **Ensure you have MP3 music files in:** `shrq_radio/data/music/`

## Run
```bash
python shrq_radio.py
```

It will:
1. Download news clips from NPR or TPR (I live in Texas :) )

2. Generate DJ audio

3. Combine everything into a final mix

4. Save the result to shrq_radio/output/final_mix.mp3

### Notes
The DJ audio uses local text-to-speech synthesis.
Only .mp3 files are supported for the music playlist.
If ffmpeg or ffprobe are not found, the script will raise an error.

```bash
pip install -r requirements.txt
