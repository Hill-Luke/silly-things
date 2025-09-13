import librosa
import numpy as np
from crewai.tools import BaseTool
from typing import Type, List
from pydantic import BaseModel, Field
import os
import traceback
import pyloudnorm as pyln

#{"filepaths": ["/Users/lukeofthehill/Desktop/test/1-02 Boku Wa Chotto.mp3", "/Users/lukeofthehill/Desktop/test/04 (I Got) So Much Trouble In My Mind.mp3"]}
class BPMToolInput(BaseModel):
    """Input schema for BPMTool."""
    filepath: str = Field(..., description="Path to the audio file for BPM extraction.")


class BPMTool(BaseTool):
    name: str = "BPM Extraction Tool"
    description: str = "Extracts the beats per minute (BPM) from an audio file."
    args_schema: Type[BaseModel] = BPMToolInput

    def _run(self, filepath: str) -> str:
        try:
            # Avoid resampling to bypass resampy/numba path
            y, sr = librosa.load(filepath, sr=None, mono=True)
            tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
            # `tempo` can be a numpy array (e.g., shape (1,)) on some versions/platforms.
            tempo_arr = np.asarray(tempo).astype(float).squeeze()
            if tempo_arr.ndim == 0:
                tempo_val = float(tempo_arr)
            else:
                # take the first element if an array is returned
                tempo_val = float(tempo_arr.flat[0])
            return f"BPM (tempo): {tempo_val:.2f} | numpy={np.__version__} librosa={librosa.__version__} sr={sr}"
        except Exception as e:
            tb = traceback.format_exc()
            return (
                f"Error processing BPM for {filepath}: {repr(e)}\nTraceback:\n{tb}\n"
                f"numpy={np.__version__} librosa={librosa.__version__}"
            )


class AudioPreprocessToolInput(BaseModel):
    """Input schema for AudioPreprocessTool."""
    filepath: str = Field(..., description="Path to the audio file for RMS loudness analysis.")


class AudioPreprocessTool(BaseTool):
    name: str = "Audio Preprocessing Tool"
    description: str = "Analyzes the RMS loudness of an audio file and categorizes intensity."
    args_schema: Type[BaseModel] = AudioPreprocessToolInput

    def _run(self, filepath: str) -> str:
        y, sr = librosa.load(filepath, sr=None, mono=True)
        rms = librosa.feature.rms(y=y)
        mean_rms = float(np.mean(rms))
        if mean_rms < 0.02:
            category = "low"
        elif mean_rms < 0.05:
            category = "medium"
        else:
            category = "high"
        return str({"file": filepath, "rms": mean_rms, "category": category})


class LUFSToolInput(BaseModel):
    """Input schema for LUFSTool."""
    filepath: str = Field(..., description="Path to the audio file for LUFS measurement.")


class LUFSTool(BaseTool):
    name: str = "LUFS Measurement Tool"
    description: str = "Measures the integrated loudness (LUFS) of an audio file."
    args_schema: Type[BaseModel] = LUFSToolInput

    def _run(self, filepath: str) -> str:
        try:
            y, sr = librosa.load(filepath, sr=None, mono=True)
            meter = pyln.Meter(sr)
            loudness = meter.integrated_loudness(y)
            return f"File: {filepath} | Integrated Loudness (LUFS): {loudness:.2f} | numpy={np.__version__} librosa={librosa.__version__}"
        except Exception as e:
            tb = traceback.format_exc()
            return (
                f"Error processing LUFS for {filepath}: {repr(e)}\nTraceback:\n{tb}\n"
                f"numpy={np.__version__} librosa={librosa.__version__}"
            )