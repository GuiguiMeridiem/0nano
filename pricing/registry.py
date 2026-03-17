"""
pricing/registry.py — Model Pricing Registry

Single source of truth for all fal.ai model costs.

When you add a new model to any step, add its pricing entry here.
If a model is missing from the registry, the workflow will abort and tell you.

All prices are in USD.
"""

# ── Configuration ─────────────────────────────────────────────────────────────

# Below this amount: simple Y/n confirmation before running.
# Above this amount: user must type the exact dollar amount to confirm.
HIGH_COST_THRESHOLD = 5.00


# ── Pricing functions (one per model) ─────────────────────────────────────────

def _nano_banana_2(params: dict) -> float:
    """
    Nano Banana 2 — text-to-image
    Base: $0.08/image at 1K resolution
    Resolution multipliers: 0.5K=0.5x, 1K=1x, 2K=1.5x, 4K=2x
    Source: https://fal.ai/models/fal-ai/nano-banana-2
    """
    resolution_multiplier = {
        "0.5K": 0.5,
        "1K":   1.0,
        "2K":   1.5,
        "4K":   2.0,
    }
    base_price = 0.08
    resolution = params.get("resolution", "1K")
    multiplier = resolution_multiplier.get(resolution, 1.0)
    num_images = params.get("num_images", 1)
    return base_price * multiplier * num_images


def _nano_banana(params: dict) -> float:
    """
    Nano Banana (original) — text-to-image
    $0.039/image
    Source: https://fal.ai/models/fal-ai/nano-banana
    """
    return 0.039 * params.get("num_images", 1)


def _nano_banana_pro(params: dict) -> float:
    """
    Nano Banana Pro — text-to-image
    $0.10/image (estimate, check https://fal.ai/models/fal-ai/nano-banana-pro)
    """
    return 0.10 * params.get("num_images", 1)


def _flux_dev(params: dict) -> float:
    """
    FLUX.1 [dev] — text-to-image
    ~$0.025/image
    Source: https://fal.ai/models/fal-ai/flux/dev
    """
    return 0.025 * params.get("num_images", 1)


def _flux_schnell(params: dict) -> float:
    """
    FLUX.1 [schnell] — text-to-image, optimized for speed
    ~$0.003/image
    Source: https://fal.ai/models/fal-ai/flux/schnell
    """
    return 0.003 * params.get("num_images", 1)


def _flux_pro_v1_1_ultra(params: dict) -> float:
    """
    FLUX1.1 [pro] ultra — text-to-image, up to 2K, high realism
    ~$0.06/image
    Source: https://fal.ai/models/fal-ai/flux-pro/v1.1-ultra
    """
    return 0.06 * params.get("num_images", 1)


def _any_llm(params: dict) -> float:
    """
    fal-ai/any-llm — unified LLM gateway (Gemini, Llama, Mistral, etc.)
    Price varies by model. Using a conservative flat estimate of $0.005/call.
    For accurate pricing, see each sub-model's cost on fal.ai.
    Source: https://fal.ai/models/fal-ai/any-llm
    """
    return 0.005


def _minimax_video_image_to_video(params: dict) -> float:
    """
    Minimax Video — image-to-video
    Official fal pricing: $0.5 per video
    Source: https://fal.ai/models/fal-ai/minimax-video/image-to-video
    """
    return 0.50


def _wan_v2_2_text_to_video(params: dict) -> float:
    """
    WAN 2.2 — text-to-video
    Official fal pricing per video second:
      - 720p: $0.08
      - 580p: $0.06
      - 480p: $0.04
    Source: https://fal.ai/models/fal-ai/wan/v2.2-a14b/text-to-video
    """
    resolution = str(params.get("resolution", "720p")).lower()
    rate = {
        "480p": 0.04,
        "580p": 0.06,
        "720p": 0.08,
    }.get(resolution, 0.08)
    seconds = _duration_seconds(params.get("duration"), 0)
    if seconds <= 0:
        fps = int(params.get("frames_per_second", 16) or 16)
        num_frames = int(params.get("num_frames", 81) or 81)
        seconds = max(1.0, (num_frames - 1) / max(1, fps))
    return rate * seconds


def _seedance_pro_text_to_video(params: dict) -> float:
    """
    Seedance 1.0 Pro — text-to-video (ByteDance)
    Official pricing: 1M video tokens = $2.5
    tokens = (height * width * FPS * duration) / 1024
    Using FPS=24 to align with model example pricing.
    Source: https://fal.ai/models/fal-ai/bytedance/seedance/v1/pro/text-to-video
    """
    duration = max(2, min(12, _duration_seconds(params.get("duration"), 5)))
    width, height = _seedance_dimensions(
        str(params.get("resolution", "1080p")),
        str(params.get("aspect_ratio", "16:9")),
    )
    tokens = (width * height * 24 * duration) / 1024
    return (tokens / 1_000_000) * 2.5


def _seedance_pro_image_to_video(params: dict) -> float:
    """
    Seedance 1.0 Pro — image-to-video (ByteDance)
    Official pricing: 1M video tokens = $2.5
    tokens = (height * width * FPS * duration) / 1024
    Using FPS=24 to align with model example pricing.
    Source: https://fal.ai/models/fal-ai/bytedance/seedance/v1/pro/image-to-video
    """
    duration = max(2, min(12, _duration_seconds(params.get("duration"), 5)))
    width, height = _seedance_dimensions(
        str(params.get("resolution", "1080p")),
        str(params.get("aspect_ratio", "auto")),
    )
    tokens = (width * height * 24 * duration) / 1024
    return (tokens / 1_000_000) * 2.5


def _duration_seconds(value, default: int) -> int:
    """Parse duration values like 8, '8', or '8s'."""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        raw = value.strip().lower().replace("s", "")
        if raw.isdigit():
            return int(raw)
    return default


def _is_truthy(value, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _seedance_dimensions(resolution: str, aspect_ratio: str) -> tuple[int, int]:
    # Conservative mapping from listed resolution/aspect ratio options.
    key = resolution.strip().lower()
    if key not in {"480p", "720p", "1080p"}:
        key = "1080p"
    dims = {
        "480p": {
            "21:9": (1120, 480),
            "16:9": (854, 480),
            "4:3": (640, 480),
            "1:1": (480, 480),
            "3:4": (480, 640),
            "9:16": (480, 854),
            "auto": (854, 480),
        },
        "720p": {
            "21:9": (1680, 720),
            "16:9": (1280, 720),
            "4:3": (960, 720),
            "1:1": (720, 720),
            "3:4": (720, 960),
            "9:16": (720, 1280),
            "auto": (1280, 720),
        },
        "1080p": {
            "21:9": (2520, 1080),
            "16:9": (1920, 1080),
            "4:3": (1440, 1080),
            "1:1": (1080, 1080),
            "3:4": (1080, 1440),
            "9:16": (1080, 1920),
            "auto": (1920, 1080),
        },
    }
    ar = aspect_ratio.strip().lower()
    return dims[key].get(ar, dims[key]["16:9"])


def _kling_v3_pro_image_to_video(params: dict) -> float:
    """
    Kling 3.0 Pro — image-to-video
    Official fal pricing per video second:
      - audio off: $0.112
      - audio on: $0.168
      - audio on + voice control: $0.196
    Source: https://fal.ai/models/fal-ai/kling-video/v3/pro/image-to-video
    """
    seconds = max(3, min(15, _duration_seconds(params.get("duration"), 5)))
    audio_on = _is_truthy(params.get("generate_audio"), True)
    has_voice = bool(params.get("voice_ids"))
    if not audio_on:
        rate = 0.112
    else:
        rate = 0.196 if has_voice else 0.168
    return rate * seconds


def _kling_v2_6_pro_image_to_video(params: dict) -> float:
    """
    Kling 2.6 Pro — image-to-video
    Official fal pricing per video second:
      - audio off: $0.07
      - audio on: $0.14
      - audio on + voice control: $0.168
    Source: https://fal.ai/models/fal-ai/kling-video/v2.6/pro/image-to-video
    """
    seconds = max(5, min(10, _duration_seconds(params.get("duration"), 5)))
    audio_on = _is_truthy(params.get("generate_audio"), True)
    has_voice = bool(params.get("voice_ids"))
    if not audio_on:
        rate = 0.07
    else:
        rate = 0.168 if has_voice else 0.14
    return rate * seconds


def _sora_2_image_to_video(params: dict) -> float:
    """
    Sora 2 — image-to-video (OpenAI)
    Official fal pricing: $0.1 per video second
    Source: https://fal.ai/models/fal-ai/sora-2/image-to-video
    """
    seconds = max(4, min(20, _duration_seconds(params.get("duration"), 4)))
    return 0.10 * seconds


def _sora_2_text_to_video(params: dict) -> float:
    """
    Sora 2 — text-to-video (OpenAI)
    Official fal pricing: $0.1 per video second
    Source: https://fal.ai/models/fal-ai/sora-2/text-to-video
    """
    seconds = max(4, min(20, _duration_seconds(params.get("duration"), 4)))
    return 0.10 * seconds


def _veo3_1_reference_to_video(params: dict) -> float:
    """
    Veo 3.1 — reference-to-video (Google)
    Official fal pricing per video second:
      720p/1080p: $0.20 (audio off), $0.40 (audio on)
      4k:         $0.40 (audio off), $0.60 (audio on)
    Source: https://fal.ai/models/fal-ai/veo3.1/reference-to-video
    """
    seconds = max(4, min(8, _duration_seconds(params.get("duration"), 8)))
    resolution = str(params.get("resolution", "720p")).lower()
    audio_on = _is_truthy(params.get("generate_audio"), True)
    if resolution == "4k":
        rate = 0.60 if audio_on else 0.40
    else:
        rate = 0.40 if audio_on else 0.20
    return rate * seconds


def _veo3_1_image_to_video(params: dict) -> float:
    """
    Veo 3.1 — image-to-video (Google)
    Official fal pricing per video second:
      720p/1080p: $0.20 (audio off), $0.40 (audio on)
      4k:         $0.40 (audio off), $0.60 (audio on)
    Source: https://fal.ai/models/fal-ai/veo3.1/image-to-video
    """
    seconds = max(4, min(8, _duration_seconds(params.get("duration"), 8)))
    resolution = str(params.get("resolution", "720p")).lower()
    audio_on = _is_truthy(params.get("generate_audio"), True)
    if resolution == "4k":
        rate = 0.60 if audio_on else 0.40
    else:
        rate = 0.40 if audio_on else 0.20
    return rate * seconds


def _veo3_1_fast_image_to_video(params: dict) -> float:
    """
    Veo 3.1 Fast — image-to-video (Google)
    Official fal pricing per video second:
      720p/1080p: $0.10 (audio off), $0.15 (audio on)
      4k:         $0.30 (audio off), $0.35 (audio on)
    Source: https://fal.ai/models/fal-ai/veo3.1/fast/image-to-video
    """
    seconds = max(4, min(8, _duration_seconds(params.get("duration"), 8)))
    resolution = str(params.get("resolution", "720p")).lower()
    audio_on = _is_truthy(params.get("generate_audio"), True)
    if resolution == "4k":
        rate = 0.35 if audio_on else 0.30
    else:
        rate = 0.15 if audio_on else 0.10
    return rate * seconds


# ── Registry ──────────────────────────────────────────────────────────────────
# Add a new entry here every time you use a new model in a step.

REGISTRY: dict[str, dict] = {
    "fal-ai/nano-banana-2": {
        "type": "image",
        "description": "Nano Banana 2 — text-to-image (Google, fast, high quality)",
        "calculate": _nano_banana_2,
    },
    "fal-ai/nano-banana": {
        "type": "image",
        "description": "Nano Banana — text-to-image (original)",
        "calculate": _nano_banana,
    },
    "fal-ai/nano-banana-pro": {
        "type": "image",
        "description": "Nano Banana Pro — text-to-image",
        "calculate": _nano_banana_pro,
    },
    "fal-ai/flux/dev": {
        "type": "image",
        "description": "FLUX.1 [dev] — text-to-image",
        "calculate": _flux_dev,
    },
    "fal-ai/flux/schnell": {
        "type": "image",
        "description": "FLUX.1 [schnell] — text-to-image (fast)",
        "calculate": _flux_schnell,
    },
    "fal-ai/flux-pro/v1.1-ultra": {
        "type": "image",
        "description": "FLUX1.1 [pro] ultra — text-to-image (2K, high realism)",
        "calculate": _flux_pro_v1_1_ultra,
    },
    "fal-ai/any-llm": {
        "type": "text",
        "description": "Any LLM — unified LLM gateway",
        "calculate": _any_llm,
    },
    "fal-ai/minimax-video/image-to-video": {
        "type": "video",
        "description": "Minimax Video — image-to-video",
        "calculate": _minimax_video_image_to_video,
    },
    "fal-ai/wan/v2.2-a14b/text-to-video": {
        "type": "video",
        "description": "WAN 2.2 — text-to-video",
        "calculate": _wan_v2_2_text_to_video,
    },
    # Seedance (ByteDance)
    "fal-ai/bytedance/seedance/v1/pro/text-to-video": {
        "type": "video",
        "description": "Seedance 1.0 Pro — text-to-video (ByteDance)",
        "calculate": _seedance_pro_text_to_video,
    },
    "fal-ai/bytedance/seedance/v1/pro/image-to-video": {
        "type": "video",
        "description": "Seedance 1.0 Pro — image-to-video (ByteDance)",
        "calculate": _seedance_pro_image_to_video,
    },
    # Kling
    "fal-ai/kling-video/v3/pro/image-to-video": {
        "type": "video",
        "description": "Kling 3.0 Pro — image-to-video (cinematic, native audio)",
        "calculate": _kling_v3_pro_image_to_video,
    },
    "fal-ai/kling-video/v2.6/pro/image-to-video": {
        "type": "video",
        "description": "Kling 2.6 Pro — image-to-video",
        "calculate": _kling_v2_6_pro_image_to_video,
    },
    # Sora 2 (OpenAI)
    "fal-ai/sora-2/image-to-video": {
        "type": "video",
        "description": "Sora 2 — image-to-video (OpenAI)",
        "calculate": _sora_2_image_to_video,
    },
    "fal-ai/sora-2/text-to-video": {
        "type": "video",
        "description": "Sora 2 — text-to-video (OpenAI)",
        "calculate": _sora_2_text_to_video,
    },
    # Veo 3.1 (Google)
    "fal-ai/veo3.1/reference-to-video": {
        "type": "video",
        "description": "Veo 3.1 — reference-to-video (Google, first+last frame)",
        "calculate": _veo3_1_reference_to_video,
    },
    "fal-ai/veo3.1/image-to-video": {
        "type": "video",
        "description": "Veo 3.1 — image-to-video (Google)",
        "calculate": _veo3_1_image_to_video,
    },
    "fal-ai/veo3.1/fast/image-to-video": {
        "type": "video",
        "description": "Veo 3.1 Fast — image-to-video (Google, cost-effective)",
        "calculate": _veo3_1_fast_image_to_video,
    },
}


# ── Public API ────────────────────────────────────────────────────────────────

class PricingNotFoundError(Exception):
    pass


def estimate(model_id: str, params: dict) -> float:
    """
    Returns the estimated cost in USD for one call to model_id with given params.
    Raises PricingNotFoundError if the model is not in the registry.
    """
    if model_id not in REGISTRY:
        raise PricingNotFoundError(
            f"\n  Model '{model_id}' has no pricing entry.\n"
            f"  Add it to pricing/registry.py before running the workflow.\n"
        )
    return REGISTRY[model_id]["calculate"](params)
