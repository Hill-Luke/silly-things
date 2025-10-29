# SHRQ Radio

SHRQ Radio is a retro-style radio mix generator that combines DJ voiceovers with randomized music tracks, along with NPR and TPR news clips. It's designed for local use and outputs a single mixed MP3 file you can play as your own radio station. See a [demo here](https://youtube.com/shorts/-VCyQLLbfhU?feature=share).

SHRQ is compatible with Mac, Linux, and Windows. However, most of the development has been on the Mac/Linux side so Windows is missing some features.

## Features

- Pulls NPR and TPR news audio from public URLs
- Randomly generates a playlist from local MP3s
- Injects AI-generated DJ commentary between tracks
- Outputs a single MP3 mix playable anywhere
- Plays silly, radio-themed jingles as interludes
- CLI-based, no inputs required

**NOTE:** SHRQ Radio requires Python 3.12. Newer versions of python are not compatible.

SHRQ also reads from the encoding on your mp3 files to get the `song name`, `artist`, and `album` for the host's commentary. It's worthwhile to use a program like [Picard](https://picard.musicbrainz.org/) to clean up your library prior to running SHRQ.

## Setup

1. **Install Python 3.11+**
2. **Install dependencies:**
```bash
pip install -r requirements.txt
```
3. **FOR WINDOWS USERS** Download and install FFmpeg (if not already installed):
  - Download from: https://www.gyan.dev/ffmpeg/builds/
  - Unzip and place the path to `ffmpeg.exe` and `ffprobe.exe` in `C:/ffmpeg-7.1.1-essentials_build/bin/`
4. **Install Ollama**
    - Download and install `ollama` from the [website](https://ollama.com/)
    - Once installed, pull `llama3.2:1b` for generating the DJ's script. You can pull whatever model you'd like to use, dependent on your hardware. I run this on a raspberry pi, so this smaller model works well and doesn't fry my cpu!
    - 
5. **Choose your TTS!**

Option A. **OpenAI's Cora**: I set this as the default because OpenAI's cora is a much more natural sounding TTS algorithm.
  - Create a `.env` file within the `shrq_radio` folder.
  - Add your OpenAI API key to the `.env`

Option B. **Piper TTS**: a free to use Text-to-Speech Algorithm. Piper is free to download and use.
  - First, comment out all of the OpenAI API code and un-comment the Piper TTS code. 
  - Download and save `en_US-hfc_female-medium` voice to the `TTS_tests` folder using `python3 -m piper.download_voices en_US-hfc_female-medium`

6. **Store your MP3 music files in:** `shrq_radio/data/music/`

## Run
```bash
python shrq_radio.py
```

It will:
1. Create a folder structure for you. You might need to run the program once to create the appropriate folder structure before loading in your `.mp3` files

2. Download news clips from NPR or TPR (I live in Texas :) )

3. Generate DJ audio

4. Combine everything into a final mix

5. Save the result to `shrq_radio/output/final_mix.mp3`

### Notes
The DJ audio uses local text-to-speech synthesis. Processing time can take a while depending on the amount of songs you have in the queue and the hardware you're working with. For best performance, I've capped the playlist at 30 songs--but you can adjust it to your liking.
There are several SHRQ-Jingles included in the download. I've capped the number of Jingles to three in a playlist, otherwise the likelihood of playing more than one jingle consecutively on a playlist was too high.
Only .mp3 files are supported for the music playlist.
If ffmpeg or ffprobe are not found, the script will raise an error.

## Song Downloader:
As I listened to my music, I realized that a lot of my music was still from when I was in High School, which was a good and a bad thing. I added a small program that downloads the KUTX Song of the Day from the website and adds it to your music folder. Helps keeps my music library fresh!

