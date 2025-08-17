#!/usr/bin/env python
import sys
import warnings

from datetime import datetime

from music_finder.crew import MusicFinder

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

# This main file is intended to be a way for you to run your
# crew locally, so refrain from adding unnecessary logic into this file.
# Replace with inputs you want to test with, it will automatically
# interpolate any tasks and agents information

def run():
    """
    Run the crew.
    """
    inputs = {
        'genre': input("What genre would you like artist from?: "),
        'timeperiod': input('What timeframe? E.g. Contemporary, 1970s, etc.:')
    }
    
    try:
        MusicFinder().crew().kickoff(inputs=inputs)
    except Exception as e:
        raise Exception(f"An error occurred while running the crew: {e}")


def train():
    """
    Train the crew for a given number of iterations.
    """
    inputs = {
        'genre': input("What genre would you like artist from?: "),
        'timeperiod': input('What timeframe? E.g. Contemporary, 1970s, etc.:')
    }
    try:
        MusicFinder().crew().train(n_iterations=int(sys.argv[1]), filename=sys.argv[2], inputs=inputs)

    except Exception as e:
        raise Exception(f"An error occurred while training the crew: {e}")

def replay():
    """
    Replay the crew execution from a specific task.
    """
    try:
        MusicFinder().crew().replay(task_id=sys.argv[1])

    except Exception as e:
        raise Exception(f"An error occurred while replaying the crew: {e}")

def test():
    """
    Test the crew execution and returns the results.
    """
    inputs = {
        'genre': input("What genre would you like artist from?: "),
        'timeperiod': input('What timeframe? E.g. Contemporary, 1970s, etc.:')
    }
    
    try:
        MusicFinder().crew().test(n_iterations=int(sys.argv[1]), eval_llm=sys.argv[2], inputs=inputs)

    except Exception as e:
        raise Exception(f"An error occurred while testing the crew: {e}")
