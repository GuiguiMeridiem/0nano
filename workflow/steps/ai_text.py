from typing import Callable
from .base import BaseStep
from services.fal_client import run_queue
import pricing.registry as pricing


class AITextStep(BaseStep):
    """
    Runs a text/LLM generation via a fal.ai language model.

    params_fn receives the current workflow context and returns model input params.

    Example:
        AITextStep(
            name="Write video prompt",
            output_key="optimized_prompt",
            model_id="fal-ai/any-llm",
            params_fn=lambda ctx: {
                "model": "google/gemini-flash-1.5",
                "prompt": f"Write a viral video prompt based on: {ctx['original_prompt']}",
            },
        )
    """

    def __init__(
        self,
        name: str,
        output_key: str,
        model_id: str,
        params_fn: Callable[[dict], dict],
    ):
        super().__init__(name, output_key)
        self.model_id = model_id
        self.params_fn = params_fn

    def estimate_cost(self, context: dict = None) -> float:
        try:
            params = self.params_fn(context or {})
        except Exception:
            params = {}
        return pricing.estimate(self.model_id, params)

    def run(self, context: dict) -> dict:
        params = self.params_fn(context)
        print(f"  Model: {self.model_id}")
        return run_queue(self.model_id, params)
