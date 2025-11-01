import librosa
import numpy as np
import pyloudnorm as pyln
import pandas as pd
import matplotlib.pyplot as plt
import soundfile as sf
import os
import sys
from tqdm import tqdm
 
def analyze_audio(filepath):
    """Analyze a single MP3 and return BPM, RMS, and LUFS."""
    try:
        y, sr = librosa.load(filepath, sr=None, mono=True)

        # Tempo (BPM)
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        bpm = float(tempo) if not isinstance(tempo, (list, np.ndarray)) else float(tempo[0])

        # RMS energy (mean across the track)
        rms = np.mean(librosa.feature.rms(y=y)[0])

        # LUFS (integrated loudness)
        meter = pyln.Meter(sr)
        lufs = meter.integrated_loudness(y)

        return bpm, rms, lufs

    except Exception as e:
        print(f"⚠️ Error analyzing {filepath}: {e}")
        return np.nan, np.nan, np.nan


def plot_histograms(df):
    """Display histograms for BPM, RMS, and LUFS."""
    if df.empty:
        print("⚠️ No valid data to plot.")
        return

    plt.figure(figsize=(15, 5))

    plt.subplot(1, 3, 1)
    plt.hist(df["bpm"].dropna(), bins=20, edgecolor="black")
    plt.title("BPM Distribution")
    plt.xlabel("Beats Per Minute")
    plt.ylabel("Count")

    plt.subplot(1, 3, 2)
    plt.hist(df["rms"].dropna(), bins=20, edgecolor="black")
    plt.title("RMS Energy Distribution")
    plt.xlabel("RMS (average amplitude)")
    plt.ylabel("Count")

    plt.subplot(1, 3, 3)
    plt.hist(df["lufs"].dropna(), bins=20, edgecolor="black")
    plt.title("LUFS Distribution")
    plt.xlabel("Loudness (LUFS)")
    plt.ylabel("Count")

    plt.tight_layout()
    plt.show()


def main(filepaths):
    """Analyze all filepaths and show histograms after loop."""
    data = []

    print("🎧 Starting batch analysis...\n")

    for path in tqdm(filepaths):
        if not os.path.exists(path):
            print(f"❌ File not found: {path}")
            continue

        print(f"🔍 Analyzing {path} ...")
        bpm, rms, lufs = analyze_audio(path)
        data.append({
            "filepath": path,
            "filename": os.path.basename(path),
            "bpm": round(bpm, 2) if not np.isnan(bpm) else None,
            "rms": round(rms, 4) if not np.isnan(rms) else None,
            "lufs": round(lufs, 2) if not np.isnan(lufs) else None
        })

    df = pd.DataFrame(data)
    print("\n✅ Analysis complete:")
    print(df)

    # Save results
    output_path = "audio_analysis_results.csv"
    df.to_csv(output_path, index=False)
    print(f"\n📊 Results saved to {output_path}")

    # Plot histograms once at the end
    print("\n📈 Displaying histograms...")
    plot_histograms(df)


if __name__ == "__main__":
    # Allow reading filepaths from either command line or text file
    if len(sys.argv) == 2 and sys.argv[1].endswith(".txt"):
        txt_file = sys.argv[1]

        if not os.path.exists(txt_file):
            print(f"❌ Path to file list not found: {txt_file}")
            sys.exit(1)

        print(f"📂 Reading filepaths from text file: {txt_file}")
        with open(txt_file, "r") as f:
            file_list = [line.strip().strip('"').strip("'") for line in f if line.strip()]

    elif len(sys.argv) >= 2:
        file_list = sys.argv[1:]
    else:
        print("Usage:\n  python energy_distr.py <file1.mp3> <file2.mp3> ...\n  OR\n  python energy_distr.py filepaths.txt")
        sys.exit(1)

    main(file_list)
