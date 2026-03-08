from typing import Callable
from .base import BaseStep
from services.fal_client import run_queue
import pricing.registry as pricing


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
        params = self.params_fn(context)
        print(f"  Model: {self.model_id}")
        return run_queue(self.model_id, params, timeout=self.timeout)
