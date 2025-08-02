import asyncio

import edge_tts

TEXT = "This is S-H-R-Q Radio. Radio, made just for you."
VOICE = "en-US-MichelleNeural"
OUTPUT_FILE = "/Users/lukeofthehill/repos/silly-things/shrq_radio/TTS_tests/tagline.mp3"


async def amain() -> None:
    """Main function"""
    communicate = edge_tts.Communicate(TEXT, VOICE)
    await communicate.save(OUTPUT_FILE)


if __name__ == "__main__":
    asyncio.run(amain())