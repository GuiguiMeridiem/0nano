"""
fal.ai client — uses official fal-client for queue/subscribe (avoids 405 on custom HTTP).
"""

import fal_client
import time

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

    handle = fal_client.submit(model_id, arguments=payload)
    request_id = getattr(handle, "request_id", None)
    if request_id:
        print(f"  → Request queued: {request_id}")

    deadline = time.time() + timeout
    last_status = None

    while time.time() < deadline:
        try:
            try:
                status_obj = handle.status(with_logs=True)
            except TypeError:
                status_obj = handle.status()

            status = getattr(status_obj, "status", None)
            if status is None and isinstance(status_obj, dict):
                status = status_obj.get("status")
            status = status or "UNKNOWN"

            if status != last_status:
                print(f"  → Status: {status}")
                last_status = status

            queue_position = getattr(status_obj, "queue_position", None)
            if queue_position is None and isinstance(status_obj, dict):
                queue_position = status_obj.get("queue_position")
            if queue_position is not None:
                print(f"  → Queue position: {queue_position}")

            logs = getattr(status_obj, "logs", None)
            if logs is None and isinstance(status_obj, dict):
                logs = status_obj.get("logs")
            if logs:
                for log in logs:
                    msg = log.get("message") if isinstance(log, dict) else str(log)
                    if msg:
                        print(f"  → {msg}")

            if status == "COMPLETED":
                break
            if status in ("FAILED", "CANCELLED"):
                raise RuntimeError(f"fal.ai request ended with status: {status}")
        except Exception as e:
            print(f"  → Status check warning: {e}")

        time.sleep(max(0.5, poll_interval))
    else:
        raise TimeoutError(f"fal.ai request timed out after {int(timeout)}s")

    # Result can be briefly unavailable right after COMPLETED; retry a few times.
    result_deadline = time.time() + 45.0
    last_err = None
    while time.time() < result_deadline:
        try:
            return handle.get()
        except Exception as e:
            last_err = e
            time.sleep(1.5)
    raise RuntimeError(f"fal.ai result retrieval failed after completion: {last_err}")
