import os
import sys

import numpy as np
import pyloudnorm as pyln
import soundfile as sf
from mutagen.id3 import ID3, ID3NoHeaderError, TXXX


def _linear_score(value: float, floor: float, ceiling: float) -> float:
    """Map a value between two calibration points onto a 0-100 score."""
    if ceiling <= floor:
        return 0.0
    return max(0.0, min(100.0, (value - floor) / (ceiling - floor) * 100.0))


def get_tempo_energy_score(bpm: float) -> float:
    """
    Convert BPM to a numeric energy score (0-100).
    Lower BPM (< 85) = lower energy, faster tracks ramp up gradually.
    """
    if bpm <= 0:
        return 0.0
    return _linear_score(float(bpm), 70.0, 175.0)


def get_waveform_energy_score(rms: np.ndarray, lufs: float) -> float:
    """
    Compute a numeric waveform energy score (0-100) using RMS + LUFS.
    Calibrated so normally mastered songs do not all max out at 100.
    """
    rms_avg = float(np.mean(rms))

    # Typical music tends to land around -24 to -8 LUFS and 0.03 to 0.30 RMS
    # after loading into normalized floating point audio. The old RMS * 1000
    # scaling made most full-range songs saturate at 100.
    loudness_score = _linear_score(float(lufs), -32.0, -7.0)
    rms_score = _linear_score(rms_avg, 0.03, 0.32)

    return (loudness_score * 0.6) + (rms_score * 0.4)


def add_energy_tag(mp3_path: str, energy_value: str) -> None:
    try:
        audio = ID3(mp3_path)
    except ID3NoHeaderError:
        audio = ID3()

    for key in list(audio.keys()):
        if key.startswith("TXXX:energy"):
            del audio[key]

    audio.add(TXXX(encoding=3, desc="energy", text=energy_value))
    audio.save(mp3_path)

    print(f"✅ Energy tag added as TXXX:energy = {energy_value}")


def _to_mono_float32(y: np.ndarray) -> np.ndarray:
    """Convert audio data to mono float32 in range roughly [-1, 1]."""
    y = np.asarray(y)

    if y.ndim > 1:
        y = np.mean(y, axis=1)

    y = y.astype(np.float32, copy=False)

    peak = float(np.max(np.abs(y))) if y.size else 0.0
    if peak > 1.0:
        y = y / peak

    return y


def _frame_rms(
    y: np.ndarray, frame_length: int = 2048, hop_length: int = 512
) -> np.ndarray:
    """Compute RMS over sliding frames without librosa."""
    if y.size == 0:
        return np.array([0.0], dtype=np.float32)

    if y.size < frame_length:
        return np.array(
            [float(np.sqrt(np.mean(np.square(y))))],
            dtype=np.float32,
        )

    rms_values = []
    for start in range(0, y.size - frame_length + 1, hop_length):
        frame = y[start : start + frame_length]
        rms_values.append(float(np.sqrt(np.mean(np.square(frame)))))

    if not rms_values:
        rms_values.append(float(np.sqrt(np.mean(np.square(y)))))

    return np.array(rms_values, dtype=np.float32)


def _estimate_tempo(y: np.ndarray, sr: int) -> float:
    """
    Estimate tempo using a simple onset-envelope autocorrelation approach.
    This avoids librosa/numba while giving a usable coarse BPM bucket.
    """
    if y.size == 0 or sr <= 0:
        return 0.0

    hop_length = 512
    frame_length = 1024

    if y.size < frame_length * 2:
        return 0.0

    energy = []
    for start in range(0, y.size - frame_length + 1, hop_length):
        frame = y[start : start + frame_length]
        energy.append(float(np.sum(frame * frame)))

    envelope = np.array(energy, dtype=np.float32)
    if envelope.size < 4:
        return 0.0

    envelope = np.diff(envelope, prepend=envelope[0])
    envelope = np.maximum(envelope, 0.0)

    env_mean = float(np.mean(envelope))
    if env_mean > 0:
        envelope = envelope - env_mean

    if not np.any(envelope > 0):
        return 0.0

    autocorr = np.correlate(envelope, envelope, mode="full")
    autocorr = autocorr[autocorr.size // 2 :]

    frames_per_second = sr / hop_length
    min_bpm = 60
    max_bpm = 200
    min_lag = max(1, int(frames_per_second * 60 / max_bpm))
    max_lag = min(len(autocorr) - 1, int(frames_per_second * 60 / min_bpm))

    if max_lag <= min_lag:
        return 0.0

    best_lag = int(np.argmax(autocorr[min_lag : max_lag + 1]) + min_lag)
    if best_lag <= 0:
        return 0.0

    bpm = 60.0 * frames_per_second / best_lag

    while bpm < min_bpm:
        bpm *= 2.0
    while bpm > max_bpm:
        bpm /= 2.0

    return float(bpm)


def analyze_mp3(filepath: str) -> None:
    if not os.path.exists(filepath):
        print("❌ File not found.")
        sys.exit(1)

    print(f"🔍 Analyzing {filepath}...")

    y, sr = sf.read(filepath, always_2d=False)
    y = _to_mono_float32(y)

    tempo_value = _estimate_tempo(y, sr)
    tempo_energy = get_tempo_energy_score(tempo_value)

    rms = _frame_rms(y)
    meter = pyln.Meter(sr)

    try:
        lufs = float(meter.integrated_loudness(y))
    except Exception:
        lufs = -70.0

    waveform_energy = get_waveform_energy_score(rms, lufs)

    # Combine tempo and waveform energy into single numeric score
    overall_energy = (tempo_energy + waveform_energy) / 2.0

    print(f"🎚 Tempo: {tempo_value:.2f} BPM (energy score: {tempo_energy:.1f})")
    print(
        f"🔊 LUFS: {lufs:.2f}, RMS avg: {float(np.mean(rms)):.4f} (energy score: {waveform_energy:.1f})"
    )
    print(f"⚡ Overall energy metric: {overall_energy:.1f}/100")

    add_energy_tag(filepath, str(round(overall_energy, 1)))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python energy_tagger.py <path_to_mp3>")
        sys.exit(1)
    analyze_mp3(sys.argv[1])
