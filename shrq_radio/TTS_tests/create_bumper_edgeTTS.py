import asyncio
import edge_tts

TEXT = "You're listening to S-H-R-Q Radio! Don't complain, because it's all your music!"

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