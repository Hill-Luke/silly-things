#!/usr/bin/env python
import sys
import warnings

from datetime import datetime

from music_tagger.crew import MusicTagger

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

# This main file is intended to be a way for you to run your
# crew locally, so refrain from adding unnecessary logic into this file.
# Replace with inputs you want to test with, it will automatically
# interpolate any tasks and agents information

def run():
    """
    Run the crew.
    """
    # Prompt user to input a Python-style dictionary containing filepaths
    user_input = input("Please paste a Python-style dictionary containing filepaths: ")
    # WARNING: Using eval() can be dangerous if used with untrusted input.
    # This is intended for controlled/test environments only.
    inputs = eval(user_input)
    
    try:
        MusicTagger().crew().kickoff(inputs=inputs)
    except Exception as e:
        raise Exception(f"An error occurred while running the crew: {e}")


def train():
    """
    Train the crew for a given number of iterations.
    """
    user_input = input("Please paste a Python-style dictionary containing filepaths: ")
    inputs = eval(user_input)
    try:
        MusicTagger().crew().train(n_iterations=int(sys.argv[1]), filename=sys.argv[2], inputs=inputs)

    except Exception as e:
        raise Exception(f"An error occurred while training the crew: {e}")

def replay():
    """
    Replay the crew execution from a specific task.
    """
    user_input = input("Please paste a Python-style dictionary containing filepaths: ")
    inputs = eval(user_input)
    try:
        MusicTagger().crew().replay(task_id=sys.argv[1], inputs=inputs)

    except Exception as e:
        raise Exception(f"An error occurred while replaying the crew: {e}")

def test():
    """
    Test the crew execution and returns the results.
    """
    inputs = {
        "topic": "AI LLMs",
        "current_year": str(datetime.now().year)
    }
    
    try:
        MusicTagger().crew().test(n_iterations=int(sys.argv[1]), eval_llm=sys.argv[2], inputs=inputs)

    except Exception as e:
        raise Exception(f"An error occurred while testing the crew: {e}")
