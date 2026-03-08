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
    ~$0.55/video (5s clip at 720p, estimate)
    Source: https://fal.ai/models/fal-ai/minimax-video/image-to-video
    """
    return 0.55


def _wan_v2_2_text_to_video(params: dict) -> float:
    """
    WAN 2.2 — text-to-video
    ~$0.50/video (estimate)
    Source: https://fal.ai/models/fal-ai/wan/v2.2-a14b/text-to-video
    """
    return 0.50


# ── Registry ──────────────────────────────────────────────────────────────────
# Add a new entry here every time you use a new model in a step.

REGISTRY: dict[str, dict] = {
    "fal-ai/nano-banana-2": {
        "description": "Nano Banana 2 — text-to-image (Google, fast, high quality)",
        "calculate": _nano_banana_2,
    },
    "fal-ai/nano-banana": {
        "description": "Nano Banana — text-to-image (original)",
        "calculate": _nano_banana,
    },
    "fal-ai/nano-banana-pro": {
        "description": "Nano Banana Pro — text-to-image",
        "calculate": _nano_banana_pro,
    },
    "fal-ai/flux/dev": {
        "description": "FLUX.1 [dev] — text-to-image",
        "calculate": _flux_dev,
    },
    "fal-ai/flux/schnell": {
        "description": "FLUX.1 [schnell] — text-to-image (fast)",
        "calculate": _flux_schnell,
    },
    "fal-ai/flux-pro/v1.1-ultra": {
        "description": "FLUX1.1 [pro] ultra — text-to-image (2K, high realism)",
        "calculate": _flux_pro_v1_1_ultra,
    },
    "fal-ai/any-llm": {
        "description": "Any LLM — unified LLM gateway",
        "calculate": _any_llm,
    },
    "fal-ai/minimax-video/image-to-video": {
        "description": "Minimax Video — image-to-video",
        "calculate": _minimax_video_image_to_video,
    },
    "fal-ai/wan/v2.2-a14b/text-to-video": {
        "description": "WAN 2.2 — text-to-video",
        "calculate": _wan_v2_2_text_to_video,
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
