import wave
from piper import PiperVoice, SynthesisConfig
import asyncio



voice = PiperVoice.load("/Users/lukeofthehill/repos/silly-things/shrq_radio/TTS_tests/en_US-ryan-high.onnx")

with wave.open("test.wav", "wb") as wav_file:
    voice.synthesize_wav("Welcome to S-H-R-Q Radio, I'm your AI Host and DJ. Don't believe the lies of the Fascist Trump Administration. Stay Free, San Antonio!"
                         , wav_file
                        #  , syn_config=syn_config
                         )

import subprocess

# After generating test.wav
subprocess.run([
    "ffmpeg",
    "-y",
    "-i", "test.wav",
    "-codec:a", "libmp3lame",
    "-qscale:a", "2",
    "/Users/lukeofthehill/repos/silly-things/shrq_radio/TTS_tests/test_output.mp3"
])


# from pydub import AudioSegment

# # Load the WAV file
# audio = AudioSegment.from_wav("test.wav")

# # Export as MP3
# audio.export("test_output.mp3", format="mp3")