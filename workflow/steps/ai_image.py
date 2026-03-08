from typing import Callable
from .base import BaseStep
from services.fal_client import run_queue, run_sync
import pricing.registry as pricing


class AIImageStep(BaseStep):
    """
    Generates images via a fal.ai text-to-image model.

    params_fn is a callable that receives the current workflow context and returns
    a dict of model input parameters. This lets you build prompts dynamically
    based on previous steps.

    Example:
        AIImageStep(
            name="Generate portrait",
            output_key="portrait",
            model_id="fal-ai/nano-banana-2",
            params_fn=lambda ctx: {
                "prompt": ctx["personality"]["visual_description"],
                "aspect_ratio": "2:3",
                "resolution": "2K",
            },
        )
    """

    def __init__(
        self,
        name: str,
        output_key: str,
        model_id: str,
        params_fn: Callable[[dict], dict],
        use_queue: bool = True,
    ):
        super().__init__(name, output_key)
        self.model_id = model_id
        self.params_fn = params_fn
        self.use_queue = use_queue

    def estimate_cost(self, context: dict = None) -> float:
        try:
            params = self.params_fn(context or {})
        except Exception:
            params = {}
        return pricing.estimate(self.model_id, params)

    def run(self, context: dict) -> dict:
        params = self.params_fn(context)
        print(f"  Model  : {self.model_id}")
        print(f"  Prompt : {str(params.get('prompt', ''))[:80]}...")
        if self.use_queue:
            return run_queue(self.model_id, params)
        return run_sync(self.model_id, params)
