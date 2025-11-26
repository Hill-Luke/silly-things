#!/usr/bin/env python
import sys
import warnings
import json

from datetime import datetime

from shrq_dj.crew import ShrqDj

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

# This main file is intended to be a way for you to run your
# crew locally, so refrain from adding unnecessary logic into this file.
# Replace with inputs you want to test with, it will automatically
# interpolate any tasks and agents information

def run():
    """
    Run the crew.
    """
    # Expect the first CLI argument to be the path to the JSON db file
    # if len(sys.argv) < 2:
    #     raise ValueError("Please provide the path to the JSON db file as the first argument, e.g. `python main.py mp3_rag_db.json`.")

    db_path = "/Users/lukeofthehill/repos/silly-things/shrq_radio/shrq_radio/file_preprocessing/mp3_rag_db.json"

    # Load JSON and convert to a pandas DataFrame
    with open(db_path, "r") as f:
        raw_db = json.load(f)

    # Ensure we have a records-oriented structure; assume the JSON is already a list of dicts
    if isinstance(raw_db, list):
        db_records = raw_db
    else:
        db_records = [raw_db]

    user_query = input("What should the playlist consist of? ")

    # Pass a records-oriented representation to the agents so they can analyze the dataset
    inputs = {
        "db": db_records,
        "query": user_query,
        "prompt": user_query,
    }
    
    try:
        ShrqDj().crew().kickoff(inputs=inputs)
    except Exception as e:
        raise Exception(f"An error occurred while running the crew: {e}")


def train():
    """
    Train the crew for a given number of iterations.
    """
    db_path = "/Users/lukeofthehill/repos/silly-things/shrq_radio/shrq_radio/file_preprocessing/mp3_rag_db.json"

    with open(db_path, "r") as f:
        raw_db = json.load(f)

    if isinstance(raw_db, list):
        db_records = raw_db
    else:
        db_records = [raw_db]

    user_query = input("What should the playlist consist of? ")

    inputs = {
        "db": db_records,
        "query": user_query,
        "prompt": user_query,
    }
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
    db_path = "/Users/lukeofthehill/repos/silly-things/shrq_radio/shrq_radio/file_preprocessing/mp3_rag_db.json"

    with open(db_path, "r") as f:
        raw_db = json.load(f)

    if isinstance(raw_db, list):
        db_records = raw_db
    else:
        db_records = [raw_db]

    user_query = input("What should the playlist consist of? ")

    inputs = {
        "db": db_records,
        "query": user_query,
        "prompt": user_query,
    }
    
    try:
        ShrqDj().crew().test(n_iterations=int(sys.argv[1]), eval_llm=sys.argv[2], inputs=inputs)

    except Exception as e:
        raise Exception(f"An error occurred while testing the crew: {e}")
