from typing import Callable, Any
from .base import BaseStep


class CustomStep(BaseStep):
    """
    A user-defined step for any custom logic: saving to a database,
    transforming data, posting to social media, sending notifications, etc.

    fn receives the current workflow context and must return the step result,
    which will be stored under output_key.

    Example:
        CustomStep(
            name="Save to database",
            output_key="db_record",
            fn=lambda ctx: db.insert({
                "image_url": ctx["portrait"]["images"][0]["url"],
                "prompt": ctx["portrait_params"]["prompt"],
            }),
        )
    """

    def __init__(
        self,
        name: str,
        output_key: str,
        fn: Callable[[dict], Any],
    ):
        super().__init__(name, output_key)
        self.fn = fn

    def run(self, context: dict) -> Any:
        return self.fn(context)
