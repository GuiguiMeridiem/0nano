from abc import ABC, abstractmethod
from typing import Any


class BaseStep(ABC):
    def __init__(self, name: str, output_key: str):
        self.name = name
        self.output_key = output_key

    @abstractmethod
    def run(self, context: dict) -> Any:
        """Execute the step logic. Receives the shared context, returns the step result."""

    def execute(self, context: dict) -> dict:
        """Called by the engine. Runs the step and stores its result in the context."""
        result = self.run(context)
        context[self.output_key] = result
        return context

    def estimate_cost(self, context: dict = None) -> float:
        """
        Returns the estimated cost in USD for this step.
        Override in AI steps. Custom steps return 0 by default.
        """
        return 0.0
