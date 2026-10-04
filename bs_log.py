"""Error log: pythonw has no console, so problems are written to crash_log.txt next to the game."""
import datetime
import faulthandler
import os
import sys
import traceback

LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "crash_log.txt")
_fault_file = None


def log_error(where):
    """Write the current exception (with where it happened) to the log. Call from an except block."""
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"\n=== {datetime.datetime.now():%Y-%m-%d %H:%M:%S}  {where}\n")
            traceback.print_exc(file=f)
    except OSError:
        pass


def start_logging():
    """Log uncaught errors and hard crashes (e.g. inside the audio driver) to crash_log.txt."""
    global _fault_file
    try:
        _fault_file = open(LOG_PATH, "a", encoding="utf-8")
        faulthandler.enable(file=_fault_file)
    except OSError:
        pass

    def hook(kind, value, tb):
        try:
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                f.write(f"\n=== {datetime.datetime.now():%Y-%m-%d %H:%M:%S}  uncaught error\n")
                traceback.print_exception(kind, value, tb, file=f)
        except OSError:
            pass
    sys.excepthook = hook
