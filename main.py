"""
main.py — 0nano Workflow Manager

This is the main file you edit and run.
Define your workflow steps below, then run:

    python main.py
"""

import urllib.request
from pathlib import Path

from workflow.engine import WorkflowEngine
from workflow.steps.ai_image import AIImageStep
from workflow.steps.custom import CustomStep

# ── Output directory ──────────────────────────────────────────────────────────
OUTPUTS_DIR = Path("outputs")
OUTPUTS_DIR.mkdir(exist_ok=True)


# ── Helper functions (add your own below) ─────────────────────────────────────

def download_images(context: dict) -> list[str]:
    """Download all images from the previous step's result and save them to outputs/."""
    images = context.get("generated_image", {}).get("images", [])
    saved = []
    for img in images:
        url = img["url"]
        filename = img.get("file_name", "output.png")
        dest = OUTPUTS_DIR / filename
        print(f"  Downloading → {dest}")
        urllib.request.urlretrieve(url, dest)
        saved.append(str(dest))
    return saved


# ── Workflow Definition ────────────────────────────────────────────────────────
#
# Add, remove, or reorder steps here.
# Each step receives the full context so it can use outputs from previous steps.
# context["output_key"] gives you the result of any prior step.
#
# save=True          → saves to saved_workflows/, name derived from first step
# save="my_name"     → saves to saved_workflows/my_name.py
# (omit or None)     → don't save
#
workflow = WorkflowEngine(steps=[

    AIImageStep(
        name="Generate image — Nano Banana 2",
        output_key="generated_image",
        model_id="fal-ai/nano-banana-2",
        params_fn=lambda ctx: {
            # ── Required ──────────────────────────────────────────────────────
            "prompt": (
                "Hyper-realistic random picture of a 25-year-old woman with natural makeup in here car , "
                "soft golden hour lighting, shallow depth of field, shot on Iphone from inside the car, "
                "looking directly into the camera, wearing a casual cream linen shirt"
            ),

            # ── Optional ──────────────────────────────────────────────────────

            # Number of images to generate
            "num_images": 1,

            # Aspect ratio: auto | 21:9 | 16:9 | 3:2 | 4:3 (iphone picture) | 5:4 | 1:1 | 4:5 | 3:4 | 2:3 | 9:16
            "aspect_ratio": "4:3",

            # Resolution: 0.5K | 1K | 2K | 4K  (2K/4K charged at 1.5x/2x)
            "resolution": "1K",

            # Output format: jpeg | png | webp
            "output_format": "png",

            # Safety tolerance: "1" (most strict) → "6" (least strict)
            "safety_tolerance": "4",

            # Uncomment to fix the seed for reproducible outputs
            # "seed": 42,

            # Force exactly 1 image regardless of prompt phrasing
            "limit_generations": True,

            # Let the model pull from the web for context (e.g. real people/places)
            # "enable_web_search": False,

            # Return as base64 data URI instead of hosted URL (won't appear in history)
            # "sync_mode": False,
        },
    ),

    CustomStep(
        name="Save images to disk",
        output_key="saved_paths",
        fn=download_images,
    ),

], save=None)  # change to save=True or save="my_name" to persist this workflow


# ── Run ────────────────────────────────────────────────────────────────────────
# To run a saved workflow instead:
#   workflow = WorkflowEngine.load("my_name")
if __name__ == "__main__":
    result = workflow.run()

    paths = result.get("saved_paths", [])
    if paths:
        print("Images saved:")
        for p in paths:
            print(f"  {p}")
    else:
        print("No images were saved.")
