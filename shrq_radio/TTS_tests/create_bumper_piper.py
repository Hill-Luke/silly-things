import wave
from piper import PiperVoice, SynthesisConfig
import asyncio



voice = PiperVoice.load("/Users/lukeofthehill/repos/silly-things/shrq_radio/TTS_tests/en_US-hfc_male-medium.onnx")
syn_config=SynthesisConfig(
    volume=1.2,             # Slight boost for presence in radio context
    length_scale=1.02,      # Closer to natural speed, less robotic
    # noise_scale=0.02,      # Introduces some tonal variation (intonation)
     noise_w_scale=0.5,      # Adds variation in pronunciation and rhythm
    # normalize_audio=True,   # Ensures consistent output loudness
)


# Voices and Messages

# | Voice    | Message
# | Norman   | "S-H-R-Q. The only radio station that CANNOT be defunded!"
# | hfc_male | "S-H-R-Q. If you're listening to us, you've got strange taste."


with wave.open("test.wav", "wb") as wav_file:
    voice.synthesize_wav(
                          "S-H-R-Q. If you're listening to us, you've got strange taste."
                         , wav_file
                         , syn_config=syn_config
                         )

import subprocess

# After generating test.wav
subprocess.run([
    "ffmpeg",
    "-y",
    "-i", "test.wav",
    "-codec:a", "libmp3lame",
    "-qscale:a", "2",
    "/Users/lukeofthehill/repos/silly-things/shrq_radio/TTS_tests/shrq_strange_taste.mp3"
])


# from pydub import AudioSegment

# # Load the WAV file
# audio = AudioSegment.from_wav("test.wav")

# # Export as MP3
# audio.export("test_output.mp3", format="mp3")