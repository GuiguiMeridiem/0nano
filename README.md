# 0nano

Open-source workflow engine for hyper-realistic AI media content generation.

0nano chains AI model calls together into configurable pipelines. Each step can call a different model, process the output, or run custom logic — and passes results to the next step through a shared context.

---

## Project Structure

```
0nano/
├── main.py                 ← Start here. Define and run your workflows.
├── config/
│   └── fal.py              ← fal.ai config (reads FAL_KEY from .env)
├── services/
│   └── fal_client.py       ← Raw HTTP client for fal.ai (queue + sync)
├── workflow/
│   ├── engine.py           ← Runs steps, handles cost check, save/load
│   └── steps/
│       ├── base.py         ← BaseStep abstract class
│       ├── ai_image.py     ← Image generation step
│       ├── ai_text.py      ← LLM / text generation step
│       ├── ai_video.py     ← Video generation step
│       └── custom.py       ← User-defined step (any Python function)
├── pricing/
│   └── registry.py         ← All model pricing data + cost threshold config
├── gui/                    ← Web GUI (dark, minimal)
│   ├── app.py              ← FastAPI server
│   ├── run.py              ← Launch script
│   └── static/             ← HTML, CSS, JS
├── saved_workflows/        ← Saved workflow snapshots (loadable by name)
├── outputs/                ← Generated files saved here (gitignored)
├── requirements.txt
└── .env                    ← Your API keys (never commit this)
```

---

## Setup

1. Clone and install dependencies:

```bash
git clone https://github.com/yourname/0nano.git
cd 0nano
python -m venv .venv
# Activate the venv:
#   macOS/Linux:  source .venv/bin/activate
#   Windows:     .venv\Scripts\activate
pip install -r requirements.txt
```

2. Add your fal.ai API key to `.env`:

```
FAL_KEY=your_fal_api_key_here
```

Get your key at [fal.ai/dashboard/keys](https://fal.ai/dashboard/keys).

3. Run the default workflow:

```bash
python main.py
```

Generated images land in `outputs/`.

4. Or launch the GUI:

```bash
python -m gui
```

Opens in a native window. Use `--browser` to open in your system browser instead (works everywhere, no extra setup).

**Platform notes:**

| Platform | Native window | Notes |
|----------|---------------|-------|
| **macOS** | ✓ | Spawns in a clean subprocess to avoid OpenGL/libGL conflicts. If it crashes, try `--browser` or run from Terminal.app instead of Cursor. |
| **Windows** | ✓ | Uses Edge WebView2 (pre-installed on Windows 10/11). If missing, install [WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/). |
| **Linux** | ✓ | Requires WebKitGTK. Install system deps first: |
| | | **Debian/Ubuntu:** `sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-webkit2-4.1` |
| | | **Fedora:** `sudo dnf install python3-gobject gtk3 webkit2gtk3` |
| | | **Arch:** `sudo pacman -S python-gobject gtk3 webkit2gtk` |

---

## How It Works

### Workflow Context

Every step shares a `context` dict. Steps read from it and write their output back under their `output_key`. This is how data flows between steps.

```
Step 1 → context["portrait"] = { images: [...] }
Step 2 → reads context["portrait"], saves files → context["saved_paths"] = [...]
```

### Step Types

| Step | When to use |
|------|-------------|
| `AIImageStep` | Call a fal.ai image model |
| `AITextStep` | Call a fal.ai LLM / text model |
| `AIVideoStep` | Call a fal.ai video model |
| `CustomStep` | Any Python function (save to DB, deploy, transform data, etc.) |

### Saving & Loading Workflows

Pass `save=` to `WorkflowEngine` to snapshot the current file into `saved_workflows/`:

```python
# Derive name from first step name
workflow = WorkflowEngine([...], save=True)

# Explicit name
workflow = WorkflowEngine([...], save="influencer_portrait")
```

If the name already exists, a number is appended automatically:
`influencer_portrait` → `influencer_portrait_2` → `influencer_portrait_3` …

Load and run a saved workflow:

```python
workflow = WorkflowEngine.load("influencer_portrait")
workflow.run()
```

List available saved workflows by looking in `saved_workflows/`.

---

### JSON Workflows

Workflows can be defined as JSON and passed to `main.py` or built programmatically:

```bash
python main.py --workflow '{"steps": [{"type": "ai_image", "name": "Gen", "output_key": "img", "model_id": "fal-ai/nano-banana-2", "params": {"prompt": "A sunset"}}]}'
python main.py --workflow workflow.json
python main.py --workflow workflow.json --confirmed
```

`WorkflowEngine.from_dict(data)` builds an engine from a dict. `WorkflowEngine.load("name")` loads from `saved_workflows/name.json` or `name.py`.

---

### GUI

`python -m gui` opens the GUI in a native window:

- Add and configure workflow steps (image, text, video, save outputs)
- Estimate cost before running
- Confirm cost (or type amount if above $5 threshold)
- Watch progress (current step, elapsed time)
- View generated images and videos inline

The GUI is dark and minimal. It constructs the workflow JSON and runs it via the API.

---

### Defining a Workflow

Edit `main.py`:

```python
from workflow.engine import WorkflowEngine
from workflow.steps.ai_image import AIImageStep
from workflow.steps.ai_text import AITextStep
from workflow.steps.custom import CustomStep

workflow = WorkflowEngine([

    AITextStep(
        name="Generate influencer personality",
        output_key="personality",
        model_id="fal-ai/any-llm",
        params_fn=lambda ctx: {
            "model": "google/gemini-flash-1.5",
            "prompt": "Create a detailed AI influencer persona for a lifestyle creator.",
        },
    ),

    AIImageStep(
        name="Generate portrait",
        output_key="portrait",
        model_id="fal-ai/nano-banana-2",
        params_fn=lambda ctx: {
            "prompt": ctx["personality"]["output"],
            "aspect_ratio": "2:3",
            "resolution": "2K",
        },
    ),

    CustomStep(
        name="Save to database",
        output_key="db_id",
        fn=lambda ctx: my_db.insert(ctx["portrait"]),
    ),

])

if __name__ == "__main__":
    workflow.run()
```

---

## Nano Banana 2 Parameters

Model ID: `fal-ai/nano-banana-2`

| Parameter | Type | Default | Options |
|-----------|------|---------|---------|
| `prompt` | string | *required* | — |
| `num_images` | int | `1` | — |
| `seed` | int | random | any integer |
| `aspect_ratio` | enum | `auto` | `auto` `21:9` `16:9` `3:2` `4:3` `5:4` `1:1` `4:5` `3:4` `2:3` `9:16` |
| `resolution` | enum | `1K` | `0.5K` `1K` `2K` `4K` |
| `output_format` | enum | `png` | `jpeg` `png` `webp` |
| `safety_tolerance` | enum | `4` | `1` (strict) → `6` (permissive) |
| `limit_generations` | bool | `true` | — |
| `enable_web_search` | bool | `false` | — |
| `sync_mode` | bool | `false` | Returns base64, skips history |

---

## Supported Models (Examples)

| Model | ID |
|-------|----|
| Nano Banana 2 | `fal-ai/nano-banana-2` |
| FLUX.1 Dev | `fal-ai/flux/dev` |
| FLUX.1 Schnell (fast) | `fal-ai/flux/schnell` |
| Any LLM (Gemini, Llama…) | `fal-ai/any-llm` |
| Minimax video | `fal-ai/minimax-video/image-to-video` |
| WAN 2.2 text-to-video | `fal-ai/wan/v2.2-a14b/text-to-video` |

Browse all 600+ models at [fal.ai/models](https://fal.ai/models).

---

## License

MIT
