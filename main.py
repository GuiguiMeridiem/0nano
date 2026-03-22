"""
main.py — GUI-first entrypoint.

The product workflow now runs through the GUI + API only.
Python modules remain reusable under services/ for future interfaces.
"""

import argparse


def run_server(host: str, port: int, *, reload: bool) -> None:
    import uvicorn

    uvicorn.run("gui.app:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="0nano GUI-first launcher")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5050)
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Auto-restart when Python files change (handy while editing backend/pricing).",
    )
    args = parser.parse_args()
    run_server(args.host, args.port, reload=args.reload)
