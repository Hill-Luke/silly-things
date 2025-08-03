import asyncio
import edge_tts

TEXT = "Warning! This set may contain tracks from when you were in High School! You're tuned in to S-H-R-Q."

voices = [
    'en-US-MichelleNeural', 'en-US-AriaNeural', 'en-US-AnaNeural',
    'en-US-ChristopherNeural', 'en-US-EricNeural', 'en-US-GuyNeural',
    'en-US-JennyNeural', 'en-US-RogerNeural', 'en-US-SteffanNeural'
]

async def amain() -> None:
    """Main function"""
    for idx, voice in enumerate(voices):
        OUTPUT_FILE = f"/Users/lukeofthehill/repos/silly-things/shrq_radio/TTS_tests/tagline_{idx}_{voice}.mp3"
        communicate = edge_tts.Communicate(TEXT, voice)
        await communicate.save(OUTPUT_FILE)

if __name__ == "__main__":
    asyncio.run(amain())