import time
import requests
from config.fal import FAL_API_KEY, FAL_QUEUE_BASE_URL, FAL_SYNC_BASE_URL


def _headers() -> dict:
    return {
        "Authorization": f"Key {FAL_API_KEY}",
        "Content-Type": "application/json",
    }


def run_sync(model_id: str, payload: dict, timeout: float = 120.0) -> dict:
    """
    Call a fal.ai model synchronously.
    Best for fast models (< a few seconds). Keeps the connection open until done.
    """
    url = f"{FAL_SYNC_BASE_URL}/{model_id}"
    response = requests.post(url, json=payload, headers=_headers(), timeout=timeout)
    response.raise_for_status()
    return response.json()


def run_queue(
    model_id: str,
    payload: dict,
    poll_interval: float = 2.0,
    timeout: float = 300.0,
) -> dict:
    """
    Submit a request to fal.ai's queue and poll until it completes.
    Recommended for all AI models — doesn't require keeping a long connection open.
    """
    submit_url = f"{FAL_QUEUE_BASE_URL}/{model_id}"
    print(f"  → Sending to fal: prompt={payload.get('prompt', '')[:60]}..., aspect_ratio={payload.get('aspect_ratio')}, resolution={payload.get('resolution')}")
    response = requests.post(submit_url, json=payload, headers=_headers(), timeout=30)
    response.raise_for_status()
    request_id = response.json()["request_id"]
    print(f"  → Request queued: {request_id}")

    status_url = f"{FAL_QUEUE_BASE_URL}/{model_id}/requests/{request_id}/status"
    deadline = time.time() + timeout

    while time.time() < deadline:
        status_resp = requests.get(status_url, headers=_headers(), timeout=30)
        status_resp.raise_for_status()
        status_data = status_resp.json()
        status = status_data.get("status")

        if status == "COMPLETED":
            break
        if status in ("FAILED", "CANCELLED"):
            raise RuntimeError(f"Request {request_id} ended with status: {status}")

        position = status_data.get("queue_position")
        if position is not None:
            print(f"  → Queue position: {position}")

        time.sleep(poll_interval)
    else:
        raise TimeoutError(f"Request {request_id} timed out after {timeout}s")

    result_url = f"{FAL_QUEUE_BASE_URL}/{model_id}/requests/{request_id}"
    result_resp = requests.get(result_url, headers=_headers(), timeout=30)
    if not result_resp.ok:
        try:
            err_body = result_resp.json()
            detail = err_body.get("detail") or err_body.get("message") or str(err_body)
        except Exception:
            detail = result_resp.text or result_resp.reason
        raise RuntimeError(
            f"fal.ai request failed ({result_resp.status_code}): {detail}"
        )
    return result_resp.json()
