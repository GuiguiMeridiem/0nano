"""
Built-in functions for JSON-defined workflows.

These can be referenced by name in workflow JSON (e.g. "save_outputs").
"""

import urllib.request
from pathlib import Path

OUTPUTS_DIR = Path("outputs")
OUTPUTS_DIR.mkdir(exist_ok=True)


def save_outputs(context: dict, from_key: str) -> list[str]:
    """
    Download images from a previous step's result and save to outputs/.
    Used when workflow is defined in JSON.
    """
    data = context.get(from_key)
    if not data:
        return []
    images = data.get("images", []) if isinstance(data, dict) else []
    saved = []
    for img in images:
        url = img.get("url")
        if not url:
            continue
        filename = img.get("file_name", "output.png")
        dest = OUTPUTS_DIR / filename
        urllib.request.urlretrieve(url, dest)
        saved.append(str(dest))
    return saved
