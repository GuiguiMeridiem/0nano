#!/usr/bin/env python3
"""
Launch the 0nano GUI.

Run from project root:
    python -m gui
"""

import argparse
import os
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from uvicorn import Config, Server

from gui.app import app

PORT = 5050
URL = f"http://127.0.0.1:{PORT}"


def _start_server():
    config = Config(app, host="127.0.0.1", port=PORT)
    server = Server(config)
    server.run()


def main():
    parser = argparse.ArgumentParser(description="0nano GUI")
    parser.add_argument(
        "--browser",
        action="store_true",
        help="Open in browser instead of native window",
    )
    parser.add_argument(
        "--no-spawn",
        action="store_true",
        help="Skip subprocess spawn (for debugging)",
    )
    args = parser.parse_args()

    if args.browser:
        thread = threading.Thread(target=_start_server, daemon=True)
        thread.start()
        time.sleep(1)
        webbrowser.open(URL)
        print(f"0nano GUI → {URL}")
        print("Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    else:
        # Spawn webview in a subprocess with clean env to avoid Homebrew libGL
        # conflicting with macOS OpenGL (causes segfault in WebKit/WebCore)
        env = os.environ.copy()
        for key in ("DYLD_LIBRARY_PATH", "DYLD_INSERT_LIBRARIES", "DYLD_FALLBACK_LIBRARY_PATH"):
            env.pop(key, None)

        if args.no_spawn:
            import webview
            thread = threading.Thread(target=_start_server, daemon=True)
            thread.start()
            time.sleep(1)
            webview.create_window("0nano", URL, width=900, height=700, min_size=(600, 500))
            webview.start()
        else:
            result = subprocess.run(
                [sys.executable, "-m", "gui.window"],
                env=env,
                cwd=PROJECT_ROOT,
            )
            sys.exit(result.returncode)


if __name__ == "__main__":
    main()
