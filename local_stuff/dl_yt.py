import yt_dlp
import os

# Expand ~ to full path (Mac-friendly)
download_path = os.path.expanduser("~/Downloads/%(title)s.%(ext)s")

url = input("Paste your Video Link Here: ")

yydl_opts = {
    "outtmpl": "/Users/lukeofthehill/Downloads/%(title)s.%(ext)s",
    "format": "bestvideo+bestaudio/best",
    "merge_output_format": "mp4",
    "retries": 10,
    "fragment_retries": 10,
    "continuedl": True,
    "noprogress": False
    }

with yt_dlp.YoutubeDL(yydl_opts) as ydl:
    ydl.download([url])