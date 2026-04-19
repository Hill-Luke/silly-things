#!/usr/bin/env python
import sys
import warnings
import os
from pathlib import Path

from datetime import datetime

from shrq_dj.crew import ShrqDj

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

# This main file is intended to be a way for you to run your
# crew locally, so refrain from adding unnecessary logic into this file.
# Replace with inputs you want to test with, it will automatically
# interpolate any tasks and agents information

DB_PATH = "/Users/lukeofthehill/repos/silly-things/shrq_radio/shrq_radio/dj_agent/shrq_dj/mp3_dataset.json"


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
    os.environ["SHRQ_DB_PATH"] = DB_PATH

    user_query = input("What should the playlist consist of? ")

    inputs = _build_inputs(user_query)
    
    try:
        ShrqDj().crew().kickoff(inputs=inputs)
    except Exception as e:
        raise Exception(f"An error occurred while running the crew: {e}")


def train():
    """
    Train the crew for a given number of iterations.
    """
    _load_env_file()
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY is not set. Add it to your project .env file.")
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
    os.environ["SHRQ_DB_PATH"] = DB_PATH

    user_query = input("What should the playlist consist of? ")

    inputs = _build_inputs(user_query)
    
    try:
        ShrqDj().crew().test(n_iterations=int(sys.argv[1]), eval_llm=sys.argv[2], inputs=inputs)

    except Exception as e:
        raise Exception(f"An error occurred while testing the crew: {e}")
