"""Android entry point: python-for-android starts main.py, which runs the game."""
import os
import runpy

runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "baby_smash.pyw"), run_name="__main__")
