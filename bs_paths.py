"""Where things live: the game's own files (sounds, pictures) and your family's files
(settings, recordings, drawings, crash log).

Run from the source folder, both are that folder. The Windows .exe keeps your files in
%LOCALAPPDATA%\\Baby Smash, and the Android app in its private storage, so updating the
game never touches them.
"""
import os
import sys

WINDOWS = sys.platform == "win32"
ANDROID = hasattr(sys, "getandroidapilevel") or "ANDROID_ARGUMENT" in os.environ

APP_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))  # the .exe unpacks itself here
if getattr(sys, "frozen", False):
    DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "Baby Smash")
elif ANDROID:  # the app folder is replaced on every update; its parent (files/) is not
    DATA_DIR = os.path.join(os.environ.get("ANDROID_PRIVATE") or os.path.dirname(APP_DIR), "babysmash")
else:
    DATA_DIR = APP_DIR
os.makedirs(DATA_DIR, exist_ok=True)
