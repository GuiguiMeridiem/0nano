"""
Runs the pywebview window. Invoked by run.py in a subprocess with a clean
environment to avoid Homebrew libGL / macOS OpenGL conflicts.
"""

import sys
import threading
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import webview
from uvicorn import Config, Server

from gui.app import app

PORT = 5050
URL = f"http://127.0.0.1:{PORT}"


def _start_server():
    config = Config(app, host="127.0.0.1", port=PORT)
    server = Server(config)
    server.run()


if __name__ == "__main__":
    thread = threading.Thread(target=_start_server, daemon=True)
    thread.start()
    time.sleep(1)
    webview.create_window("0nano", URL, width=900, height=700, min_size=(600, 500))
    webview.start()
