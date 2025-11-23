from crewai.tools import BaseTool
from typing import Type
from pydantic import BaseModel, Field
import librosa
import numpy as np
import pyloudnorm as pyln
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3
import soundfile as sf
import sys
import os
import traceback
import pyloudnorm as pyln
 

class energy_tool_input(BaseModel):
    """Input schema for AudioPreprocessTool."""
    filepath: str = Field(..., description="Path to the audio file to read the energy.")


class energy_tool(BaseTool):
    name: str = "File Energy Reader Tool"
    description: str = "Reads the energy of the given filepath."
    args_schema: Type[BaseModel] = energy_tool_input

    def _run(self, filepath: str) -> str:
        """Reads the custom 'energy' tag from an MP3 file."""
        try:
            from mutagen.id3 import ID3
            from mutagen.easyid3 import EasyID3
        except Exception as e:
            return f"mutagen import failed in interpreter {sys.executable}: {e}"

        audio = ID3(filepath)
        energy=""
        for key, frame in audio.items():
            if key.startswith("TXXX:energy"):
                energy = frame.text[0]
            else:
                energy = None
        return str({"file": filepath, "energy": energy})


#-------- BPM Tool --------#

class bpm_tool_input(BaseModel):
    """Input schema for AudioPreprocessTool."""
    filepath: str = Field(..., description="Path to the audio file to read the energy.")
class bpm_tool(BaseTool):
    name: str='BPM Tool'
    description: str='Reads the BPM of a given file'
    args_schema: Type[BaseModel]=bpm_tool_input

    def _run(self, filepath: str) -> str:
        """Reads the custom 'energy' tag from an MP3 file."""
        try:
            import librosa
            import numpy as np
        except Exception as e:
            return f"librosa import failed in interpreter {sys.executable}: {e}"

        # Load the MP3 file
        y, sr = librosa.load(filepath, sr=None, mono=True)

        # 1️⃣ Tempo detection
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)

        # librosa can sometimes return an array or float — normalize it
        if isinstance(tempo, (list, np.ndarray)):
            tempo_value = float(tempo[0]) if len(tempo) > 0 else 0.0
        else:
            tempo_value = float(tempo)

        from pathlib import Path
        import json

        result = {
            "filepath": str(Path(filepath).resolve()),
            "tempo": tempo_value
        }

        return json.dumps(result, ensure_ascii=False)

    

class folder_file_extractor_input(BaseModel):
    """Input schema for FolderFileExtractor."""
    folder_path: str = Field(..., description="Path to the folder to read files from.")


class folder_file_extractor(BaseTool):
    name: str = "Folder File Extractor Tool"
    description: str = "Extracts all files in a given input folder and returns their names and paths as a dictionary."
    args_schema: Type[BaseModel] = folder_file_extractor_input

    def _run(self, folder_path: str) -> str:
        import os
        from pathlib import Path
        import json

        if not os.path.exists(folder_path):
            return f"Folder path does not exist: {folder_path}"
        if not os.path.isdir(folder_path):
            return f"Provided path is not a directory: {folder_path}"

        files_dict = {}
        for file_path in Path(folder_path).glob("*"):
            if file_path.is_file():
                files_dict[file_path.name] = str(file_path.resolve())

        return json.dumps(files_dict, ensure_ascii=False)
    

#-------- File Tagger --------#
class FileTaggerToolInput(BaseModel):
    """Input schema for FileTaggerTool."""
    filepath: str = Field(..., description="Path to the mp3 file to update.")
    energy_classification: str = Field(..., description="Energy classification string to embed in the mp3 metadata.")

class FileTaggerTool(BaseTool):
    name: str = "File Tagger Tool"
    description: str = "Writes the computed energy classification into the metadata of an MP3 file."
    args_schema: Type[BaseModel] = FileTaggerToolInput

    def _run(self, filepath: str, energy_classification: str) -> str:
        try:
            # Load or initialize ID3 tags
            try:
                tags = ID3(filepath)
            except ID3NoHeaderError:
                tags = ID3()

            # Add/update a custom TXXX frame for energy classification
            tags.add(
                TXXX(
                    encoding=3,  # UTF-8
                    desc="EnergyClassification",
                    text=energy_classification
                )
            )

            # Save back to file
            tags.save(filepath)

            return f"Updated {filepath} with EnergyClassification={energy_classification}"
        except Exception as e:
            tb = traceback.format_exc()
            return f"Error tagging {filepath}: {repr(e)}\nTraceback:\n{tb}"    

class DuckDuckGoInput(BaseModel):
    """Input schema for DuckDuckGoTool."""
    query: str = Field(..., description="Search query string.")

class DuckDuckGoTool(BaseTool):
    name: str = "DuckDuckGo Web Search"
    description: str = (
        "Free web search using DuckDuckGo. Input a query; returns JSON list of results with title, href, and snippet."
    )
    args_schema: Type[BaseModel] = DuckDuckGoInput

    def _run(self, query: str) -> str:
        try:
            from duckduckgo_search import DDGS
        except Exception as e:
            return f"duckduckgo-search import failed in interpreter {sys.executable}: {e}"

        results: List[dict] = []
        try:
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=8):
                    results.append({
                        "title": r.get("title"),
                        "href": r.get("href"),
                        "snippet": r.get("body") or r.get("snippet"),
                    })
        except Exception as e:
            return f"DDG search error: {e}"

        return json.dumps(results, ensure_ascii=False)