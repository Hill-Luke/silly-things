import subprocess
from pathlib import Path
from tqdm import tqdm
from mutagen.id3 import ID3
from mutagen.easyid3 import EasyID3
# Ask for folder path
folder_path = Path(input('Input the filepath with your music: ').strip().strip('"').strip("'"))

# Verify folder exists
if not folder_path.exists():
    print(f"❌ Folder not found: {folder_path}")
    exit(1)

# Gather filepaths in the folder
filepaths = [str(p) for p in folder_path.iterdir() if p.is_file()]

# print("Analyzing BPM")
# for fp in tqdm(filepaths):
#     print(f"\n🎧 Tagging: {fp}")
#     subprocess.run(["python", "energy_tagger.py", fp], check=False)


# checking the tags
# from mutagen.id3 import ID3

# def read_energy_tag(mp3_path):
#     """Reads the custom 'energy' tag from an MP3 file."""
#     audio = ID3(mp3_path)
#     for key, frame in audio.items():
#         if key.startswith("TXXX:energy"):
#             return frame.text[0]
#     return None

# # Example usage:
# for fp in tqdm(filepaths):
#     energy = read_energy_tag(fp)
#     if energy:
#         print(f"Energy tag: {energy}")
#     else:
#         print("No energy tag found.")
def read_energy_tag(mp3_path):
    """Reads the custom 'energy' tag from an MP3 file."""
    try:
        audio = ID3(mp3_path)
        for key, frame in audio.items():
            if key.startswith("TXXX:energy"):
                return frame.text[0]
    except ID3NoHeaderError:
        return None
    return None

def extract_metadata(file_path):
    """Extracts title, artist, album, and energy metadata from an MP3 file."""
    file = {
        "title": "Unknown",
        "artist": "Unknown",
        "album": "Unknown",
        "energy": "Unknown"
    }

    try:
        audio = EasyID3(file_path)
        file["title"] = audio.get("title", ["Unknown"])[0]
        file["artist"] = audio.get("artist", ["Unknown"])[0]
        file["album"] = audio.get("album", ["Unknown"])[0]
    except Exception:
        pass  # Not all files will have EasyID3 tags

    energy = read_energy_tag(file_path)
    if energy:
        file["energy"] = energy

    return file

# Example usage:
for fp in tqdm(filepaths):
    metadata = extract_metadata(fp)
    print(f"{fp}: {metadata}")