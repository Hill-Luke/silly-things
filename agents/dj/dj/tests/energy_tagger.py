import librosa
import numpy as np
import pyloudnorm as pyln
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3
import soundfile as sf
import sys
import os
 
def classify_tempo(bpm):
    if bpm < 90:
        return "low"
    elif bpm < 120:
        return "medium"
    else:
        return "high"

def classify_waveform(rms, lufs):
    # Normalize both measures to comparable scales
    # LUFS are negative, so we invert and offset
    loudness_score = max(0, 100 + lufs)  # e.g. -12 LUFS → 88
    rms_score = np.mean(rms) * 1000       # RMS roughly 0.05–0.3 typical

    avg_energy = (loudness_score + rms_score) / 2

    if avg_energy < 60:
        return "low"
    elif avg_energy < 80:
        return "medium"
    else:
        return "high"    
    
from mutagen.id3 import ID3, TXXX, ID3NoHeaderError

def add_energy_tag(mp3_path, energy_value):
    try:
        audio = ID3(mp3_path)
    except ID3NoHeaderError:
        audio = ID3()

    # Remove any old energy tags first
    for key in list(audio.keys()):
        if key.startswith("TXXX:energy"):
            del audio[key]

    # Add new tag as a custom text frame
    audio.add(TXXX(encoding=3, desc="energy", text=energy_value))
    audio.save(mp3_path)

    print(f"✅ Energy tag added as TXXX:energy = {energy_value}")
    
    

def analyze_mp3(filepath):
    if not os.path.exists(filepath):
        print("❌ File not found.")
        sys.exit(1)

    print(f"🔍 Analyzing {filepath}...")

    # Load the MP3 file
    y, sr = librosa.load(filepath, sr=None, mono=True)

    # 1️⃣ Tempo detection
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)

    # librosa can sometimes return an array or float — normalize it
    if isinstance(tempo, (list, np.ndarray)):
        tempo_value = float(tempo[0]) if len(tempo) > 0 else 0.0
    else:
        tempo_value = float(tempo)

    tempo_class = classify_tempo(tempo_value)

    # 2️⃣ RMS and LUFS calculation
    rms = librosa.feature.rms(y=y)[0]
    meter = pyln.Meter(sr)
    lufs = meter.integrated_loudness(y)
    waveform_class = classify_waveform(rms, lufs)

    # 3️⃣ Combine into "energy"
    energy_tag = f"{tempo_class}_{waveform_class}"
    print(f"🎚 Tempo: {tempo_value:.2f} BPM ({tempo_class})")
    print(f"🔊 LUFS: {lufs:.2f}, RMS avg: {np.mean(rms):.4f} ({waveform_class})")
    print(f"⚡ Combined energy classification: {energy_tag}")

    # 4️⃣ Add to metadata
    add_energy_tag(filepath, energy_tag)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python classify_energy.py <path_to_mp3>")
        sys.exit(1)
    analyze_mp3(sys.argv[1])