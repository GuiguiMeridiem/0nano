"""
fal.ai client — uses official fal-client for queue/subscribe (avoids 405 on custom HTTP).
"""

import fal_client

# Ensure FAL_KEY is loaded from .env before fal_client is used
import config.fal  # noqa: F401


def run_sync(model_id: str, payload: dict, timeout: float = 120.0) -> dict:
    """
    Call a fal.ai model synchronously.
    Best for fast models (< a few seconds).
    """
    return fal_client.run(model_id, arguments=payload)


def run_queue(
    model_id: str,
    payload: dict,
    poll_interval: float = 2.0,
    timeout: float = 600.0,
) -> dict:
    """
    Submit to fal.ai queue and wait for result.
    Uses fal_client.subscribe() which handles polling correctly.
    """
    prompt_preview = (payload.get("prompt") or "")[:60]
    print(f"  → Sending to fal: prompt={prompt_preview}..., aspect_ratio={payload.get('aspect_ratio')}, resolution={payload.get('resolution')}")

    def on_update(update):
        try:
            if hasattr(update, "logs") and update.logs:
                for log in update.logs:
                    msg = log.get("message") if isinstance(log, dict) else str(log)
                    if msg:
                        print(f"  → {msg}")
            if getattr(update, "queue_position", None) is not None:
                print(f"  → Queue position: {update.queue_position}")
        except Exception:
            pass

    result = fal_client.subscribe(
        model_id,
        arguments=payload,
        with_logs=True,
        on_queue_update=on_update,
    )
    return result
