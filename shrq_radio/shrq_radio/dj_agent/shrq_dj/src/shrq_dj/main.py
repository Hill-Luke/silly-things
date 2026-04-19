#!/usr/bin/env python
import sys
import warnings
import os
import json
import ast
from pathlib import Path

from datetime import datetime

from shrq_dj.crew import ShrqDj

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

# This main file is intended to be a way for you to run your
# crew locally, so refrain from adding unnecessary logic into this file.
# Replace with inputs you want to test with, it will automatically
# interpolate any tasks and agents information

def _discover_db_path() -> str:
    # Priority: explicit env var, CWD, module-relative candidate paths
    env_path = os.getenv("SHRQ_DB_PATH")
    if env_path:
        return env_path

    cwd_candidate = Path.cwd() / "mp3_dataset.json"
    if cwd_candidate.exists():
        return str(cwd_candidate)

    p = Path(__file__).resolve()
    # Try a few reasonable locations relative to this file
    candidates = [
        p.parents[2] / "mp3_dataset.json",
        p.parents[3] / "mp3_dataset.json",
        p.parents[4] / "mp3_dataset.json",
    ]
    for c in candidates:
        try:
            if c.exists():
                return str(c)
        except IndexError:
            continue

    # Fallback to CWD candidate string even if missing (will be validated later)
    return str(cwd_candidate)

DB_PATH = _discover_db_path()


def _load_env_file() -> None:
    env_path = None
    for parent in Path(__file__).resolve().parents:
        candidate = parent / ".env"
        if candidate.exists():
            env_path = candidate
            break
    if env_path is None:
        return

    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and value and key not in os.environ:
            os.environ[key] = value


def _build_inputs(user_query: str) -> dict:
    return {
        "db_path": DB_PATH,
        "db_summary": f"Dataset path: {DB_PATH}",
        "query": user_query,
        "prompt": user_query,
    }


def _extract_playlist_filepaths(crew_output: object) -> list[str]:
    payload = crew_output
    for attr in ("json_dict", "raw", "result"):
        val = getattr(crew_output, attr, None)
        if val:
            payload = val
            break

    data = payload
    if isinstance(data, str):
        text = data.strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            try:
                data = ast.literal_eval(text)
            except (ValueError, SyntaxError):
                return []

    if not isinstance(data, dict):
        return []

    tracks = data.get("tracks", [])
    if not isinstance(tracks, list):
        return []

    filepaths: list[str] = []
    for track in tracks:
        if not isinstance(track, dict):
            continue
        fp = track.get("Filepath")
        if isinstance(fp, str) and fp.strip():
            filepaths.append(fp.strip())
    return filepaths

def run():
    """
    Run the crew.
    """
    # Expect the first CLI argument to be the path to the JSON db file
    # if len(sys.argv) < 2:
    #     raise ValueError("Please provide the path to the JSON db file as the first argument, e.g. `python main.py mp3_rag_db.json`.")

    _load_env_file()
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY is not set. Add it to your project .env file.")

    # Validate dataset path early and provide actionable message
    if not DB_PATH or not Path(DB_PATH).exists():
        raise FileNotFoundError(
            f"Dataset not found at {DB_PATH}. Set SHRQ_DB_PATH env var or place mp3_dataset.json in the project root or current working directory."
        )
    os.environ["SHRQ_DB_PATH"] = DB_PATH

    user_query = input("What should the playlist consist of? ")

    inputs = _build_inputs(user_query)
    
    try:
        result = ShrqDj().crew().kickoff(inputs=inputs)
        filepaths = _extract_playlist_filepaths(result)
        Path("playlist").write_text(repr(filepaths) + "\n")
        print(f"Saved {len(filepaths)} filepaths to playlist")
    except Exception as e:
        raise Exception(f"An error occurred while running the crew: {e}")


def train():
    """
    Train the crew for a given number of iterations.
    """
    _load_env_file()
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY is not set. Add it to your project .env file.")

    if not DB_PATH or not Path(DB_PATH).exists():
        raise FileNotFoundError(
            f"Dataset not found at {DB_PATH}. Set SHRQ_DB_PATH env var or place mp3_dataset.json in the project root or current working directory."
        )
    os.environ["SHRQ_DB_PATH"] = DB_PATH

    user_query = input("What should the playlist consist of? ")

    inputs = _build_inputs(user_query)
    try:
        ShrqDj().crew().train(n_iterations=int(sys.argv[1]), filename=sys.argv[2], inputs=inputs)

    except Exception as e:
        raise Exception(f"An error occurred while training the crew: {e}")

def replay():
    """
    Replay the crew execution from a specific task.
    """
    try:
        ShrqDj().crew().replay(task_id=sys.argv[1])

    except Exception as e:
        raise Exception(f"An error occurred while replaying the crew: {e}")

def test():
    """
    Test the crew execution and returns the results.
    """
    _load_env_file()
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY is not set. Add it to your project .env file.")

    if not DB_PATH or not Path(DB_PATH).exists():
        raise FileNotFoundError(
            f"Dataset not found at {DB_PATH}. Set SHRQ_DB_PATH env var or place mp3_dataset.json in the project root or current working directory."
        )
    os.environ["SHRQ_DB_PATH"] = DB_PATH

    user_query = input("What should the playlist consist of? ")

    inputs = _build_inputs(user_query)
    
    try:
        ShrqDj().crew().test(n_iterations=int(sys.argv[1]), eval_llm=sys.argv[2], inputs=inputs)

    except Exception as e:
        raise Exception(f"An error occurred while testing the crew: {e}")
