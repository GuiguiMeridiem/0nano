import base64
from pathlib import Path
from typing import Callable

from .base import BaseStep
from services.fal_client import run_queue
import pricing.registry as pricing

OUTPUTS_DIR = Path(__file__).resolve().parent.parent.parent / "outputs"


class AIVideoStep(BaseStep):
    """
    Generates video via a fal.ai video model.

    params_fn receives the current workflow context and returns model input params.
    Poll timeout is higher by default since video generation takes longer.

    Example:
        AIVideoStep(
            name="Generate video",
            output_key="final_video",
            model_id="fal-ai/minimax-video/image-to-video",
            params_fn=lambda ctx: {
                "prompt": ctx["optimized_prompt"]["output"],
                "image_url": ctx["portrait"]["images"][0]["url"],
            },
        )
    """

    def __init__(
        self,
        name: str,
        output_key: str,
        model_id: str,
        params_fn: Callable[[dict], dict],
        timeout: float = 600.0,
    ):
        super().__init__(name, output_key)
        self.model_id = model_id
        self.params_fn = params_fn
        self.timeout = timeout

    def estimate_cost(self, context: dict = None) -> float:
        try:
            params = self.params_fn(context or {})
        except Exception:
            params = {}
        return pricing.estimate(self.model_id, params)

    def run(self, context: dict) -> dict:
        params = dict(self.params_fn(context))
        output_image = params.pop("output_image", None)
        if output_image:
            path = OUTPUTS_DIR / output_image
            if path.exists():
                b64 = base64.b64encode(path.read_bytes()).decode()
                ext = path.suffix.lower()
                mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp", "gif": "image/gif"}.get(ext.lstrip("."), "image/png")
                params["image_url"] = f"data:{mime};base64,{b64}"
        print(f"  Model: {self.model_id}")
        return run_queue(self.model_id, params, timeout=self.timeout)
