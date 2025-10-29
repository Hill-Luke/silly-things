from pathlib import Path
from openai import OpenAI
import os
from dotenv import load_dotenv
load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

speech_file_path = Path(__file__).parent / "speech.mp3"

with client.audio.speech.with_streaming_response.create(
    model="gpt-4o-mini-tts",
    voice="coral",
    input="you're listening to S-H-R-Q Radio",
    instructions="You are Jessica, the DJ of the local radio station S-H-R-Q. Speak in a even-keeled, smooth tone.",
) as response:
    response.stream_to_file(speech_file_path)