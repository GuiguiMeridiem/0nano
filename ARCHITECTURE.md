# 0nano Architecture Guide

This document explains how 0nano is built and how data flows through the system, so a developer (or AI coding agent) can work effectively without reading the whole codebase first.

## 1) What 0nano is

0nano is a Python workflow engine for AI media generation on fal.ai.

It has two usage modes:

- **CLI mode**: run workflows directly from `main.py` or from JSON.
- **GUI mode**: build/edit/run workflows in a local desktop/web UI backed by FastAPI.

Core concept: a workflow is an ordered list of steps that all share a single mutable `context` dictionary.

---

## 2) High-level architecture

## Runtime layers

1. **Workflow authoring layer**
   - `main.py` (Python-defined workflows)
   - GUI (`gui/static/*`) for JSON-defined workflows

2. **Execution layer**
   - `workflow/engine.py` (`WorkflowEngine`)
   - Step classes in `workflow/steps/*`

3. **Provider layer**
   - `services/fal_client.py` (HTTP calls to fal queue/sync APIs)
   - `config/fal.py` (loads `FAL_KEY`, base URLs)

4. **Cost/safety layer**
   - `pricing/registry.py` (model registry + cost estimation)
   - Confirmation gate in `WorkflowEngine.run()`

5. **Persistence/output layer**
   - `saved_workflows/` (`.json` and `.py` definitions)
   - `outputs/` downloaded/generated media

---

## 3) Core execution model

All step types inherit from `BaseStep` (`workflow/steps/base.py`):

- `run(context) -> Any`: step-specific logic
- `execute(context)`: calls `run`, then stores result in `context[self.output_key]`
- `estimate_cost()`: default `0.0`, overridden by AI steps

### `WorkflowEngine.run()` lifecycle

From `workflow/engine.py`:

1. Initialize `context = initial_context or {}`
2. Optionally estimate and confirm total cost (`skip_confirm=False`)
3. For each step:
   - emit `step_start` event (if callback exists)
   - `step.execute(context)`
   - emit `step_end` with elapsed time and output summary
4. Emit `complete` event
5. Return final `context`

### Important design point

`context` is the canonical data bus between steps.  
If step A writes to `output_key="portrait"`, step B reads from `ctx["portrait"]`.

---

## 4) Workflow formats

0nano supports two workflow definition styles.

## A) Python workflow objects

Defined directly in `main.py` using classes:

- `AIImageStep`
- `AITextStep`
- `AIVideoStep`
- `CustomStep`

Each AI step receives a `params_fn(context)` callable.

## B) JSON workflow schema

Used by GUI and CLI `--workflow`:

```json
{
  "steps": [
    {
      "type": "ai_image",
      "name": "Image generation",
      "output_key": "output",
      "model_id": "fal-ai/nano-banana-2",
      "params": {
        "prompt": "A subject...",
        "aspect_ratio": "9:16",
        "resolution": "1K"
      }
    },
    {
      "type": "custom",
      "name": "Save outputs",
      "output_key": "saved",
      "fn": "save_outputs",
      "params": { "from_key": "output" }
    }
  ]
}
```

`WorkflowEngine.from_dict()` converts these JSON steps into runtime step objects.

---

## 5) Step types and responsibilities

## `AIImageStep` (`workflow/steps/ai_image.py`)

- Uses fal image endpoints
- Ensures `prompt` exists
- Special-case normalization for `fal-ai/nano-banana`:
  - maps `aspect_ratio="auto"` -> `"1:1"`
  - drops `resolution` (unsupported by original nano-banana)
- Calls `run_queue()` by default

## `AITextStep` (`workflow/steps/ai_text.py`)

- Uses fal text/LLM endpoint (`fal-ai/any-llm` typically)
- Calls `run_queue()`

## `AIVideoStep` (`workflow/steps/ai_video.py`)

- Uses fal video endpoints
- Calls `run_queue()` with longer timeout default (600s)

## `CustomStep` (`workflow/steps/custom.py`)

- Runs arbitrary Python function `fn(context)`
- Used for non-model side effects (save files, DB, webhooks, transforms, etc.)

---

## 6) fal.ai integration details

`services/fal_client.py` provides:

- `run_sync(model_id, payload)`
- `run_queue(model_id, payload, poll_interval, timeout)`

### Queue flow

1. `POST https://queue.fal.run/{model_id}` with JSON payload
2. Poll `.../requests/{request_id}/status` until `COMPLETED`
3. Fetch final result at `.../requests/{request_id}`

Errors are surfaced with status code + provider detail when available.

---

## 7) Cost model and confirmation safety

`pricing/registry.py` is the source of truth for:

- Supported model IDs
- Per-model cost estimation functions
- `HIGH_COST_THRESHOLD` (default `$5.00`)

`WorkflowEngine` behavior:

- If model missing in registry -> raises `PricingNotFoundError` and aborts
- If total cost <= threshold -> simple Y/n confirm
- If total cost > threshold -> user must type exact amount
- GUI/API path usually runs with `skip_confirm=True` because UI has its own confirmation flow

When adding a new model to workflows, update registry first.

---

## 8) Save/load architecture

## Python workflow snapshots

- `WorkflowEngine(..., save=True | "name")` writes a `.py` copy into `saved_workflows/`
- Engine patches `save=` to `save=None` in the saved file to avoid recursive resaves

## JSON workflow persistence (GUI path)

FastAPI endpoints in `gui/app.py`:

- `GET /api/workflows` -> list names from `saved_workflows/*.json` + `*.py`
- `GET /api/workflows/{name}` -> load JSON workflow
- `POST /api/workflows/save` -> save as JSON, auto-suffix `_2`, `_3`, ...

---

## 9) GUI architecture

## Backend (FastAPI): `gui/app.py`

Main API surface:

- `GET /api/models` -> model list from pricing registry (id, description, type)
- `POST /api/estimate` -> workflow cost breakdown
- `POST /api/run` -> Server-Sent Events stream (`step_start`, `step_end`, `complete`, `error`)
- `GET /api/outputs` -> list files in `outputs/`
- workflow save/load endpoints above

## Frontend: `gui/static/*`

- `index.html`: UI skeleton + modals
- `style.css`: dark theme + layout + lightbox
- `app.js`: application state, workflow builder, run loop, SSE handling

Frontend state is centered around:

- `state.steps`: current workflow (JSON step objects)
- `buildWorkflow()`: serializes to `{ steps: [...] }` for API calls

### GUI run pipeline

1. User builds/edits steps
2. `POST /api/estimate` for cost
3. User confirms
4. `POST /api/run` streams progress events
5. UI updates progress + renders output media

### Output persistence on GUI run

During `/api/run`, backend downloads returned media to `outputs/` using:

- basename derived from `procedure_name` (or first step name fallback)
- incremental suffix `_1`, `_2`, ...
- extension inferred from content type for images; `.mp4` for video

---

## 10) GUI launcher/runtime modes

`python -m gui` executes `gui/run.py`.

Modes:

- `--browser`: run API server and open system browser
- default native window: spawn `python -m gui.window` (pywebview) in subprocess
- `--no-spawn`: debug mode without subprocess

macOS-specific env cleanup removes problematic `DYLD_*` vars to avoid libGL/WebKit conflicts.

---

## 11) Data contracts and event contracts

## Step output contract (common)

- Each step writes its raw result under its `output_key` in `context`.

## SSE event contract (`/api/run`)

- `step_start`: `{type, step, name, total}`
- `step_end`: `{type, step, name, elapsed, output}`
- `complete`: `{type: "complete"}`
- `error`: `{type: "error", message}`

`step_end.output` is summarized for UI:

- images: `{"images": [{"url", "content_type"}, ...]}`
- video: `{"video": {"url": ...}}`

---

## 12) Extension guide (where to change what)

## Add a new fal model

1. Add pricing function + registry entry in `pricing/registry.py`
2. Ensure GUI supports relevant parameters in `gui/static/app.js` + `index.html`
3. If model has special param constraints, normalize in step class (`ai_image.py`, etc.)

## Add a new step type

1. Create class in `workflow/steps/` inheriting `BaseStep`
2. Wire parsing in `WorkflowEngine.from_dict()`
3. Wire serialization in `WorkflowEngine.to_dict()`
4. Add GUI creation/editing support (`app.js`, `index.html`)

## Add a new built-in custom function for JSON workflows

1. Implement in `workflow/functions.py`
2. Register dispatch in `WorkflowEngine.from_dict()` `custom` branch

---

## 13) Common failure modes and debugging

## “Prompt not respected” / missing params

- Verify `from_dict()` is preserving params (it now captures params independently of runtime context)
- Check terminal debug line from `fal_client.py`:
  - `→ Sending to fal: prompt=..., aspect_ratio=..., resolution=...`

## 422 from fal

- Usually payload/schema mismatch or moderation/constraints
- Check raised detail in backend log (error text now bubbles up)

## GUI shows media but files not in `outputs/`

- Ensure `/api/run` path is used (GUI mode)
- Check backend output-saving helper in `gui/app.py` and file permissions

---

## 14) Operational notes

- Secrets: `FAL_KEY` is loaded from `.env` by `config/fal.py`
- Generated media and saved workflows are local filesystem state:
  - `outputs/`
  - `saved_workflows/`
- The project is intentionally lightweight: no DB, no auth, no message broker.

---

## 15) Quick mental model

If you only remember one thing:

> **0nano = ordered steps + shared context + provider adapter + optional GUI API wrapper.**

Everything else (cost checks, save/load, GUI progress, output downloads) is scaffolding around that core.

