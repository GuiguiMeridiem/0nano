"""
0nano GUI — Web interface for building and running workflows.

Run from project root:
    python gui/app.py
    # or
    uvicorn gui.app:app --reload --host 0.0.0.0 --port 5050
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import json
import asyncio
from concurrent.futures import ThreadPoolExecutor
from queue import Queue, Empty

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from workflow.engine import WorkflowEngine, SAVED_WORKFLOWS_DIR
from pricing.registry import REGISTRY, HIGH_COST_THRESHOLD, PricingNotFoundError

app = FastAPI(title="0nano GUI")
executor = ThreadPoolExecutor(max_workers=2)


class WorkflowRequest(BaseModel):
    workflow: dict
    confirmed: bool = False
    procedure_name: str | None = None


class SaveWorkflowRequest(BaseModel):
    name: str
    workflow: dict
    overwrite: bool = False


static_dir = PROJECT_ROOT / "gui" / "static"


@app.get("/", response_class=HTMLResponse)
async def index():
    return (static_dir / "index.html").read_text()


app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/api/models")
async def list_models():
    """Return models from pricing registry with type hints for GUI."""
    models = []
    for mid, info in REGISTRY.items():
        models.append({
            "id": mid,
            "description": info.get("description", ""),
            "type": info.get("type", "image"),
        })
    return {"models": models}


@app.post("/api/estimate")
async def estimate_cost(req: WorkflowRequest):
    """Return cost breakdown for the workflow."""
    try:
        engine = WorkflowEngine.from_dict(req.workflow)
        breakdown, total = engine.get_cost_breakdown()
    except PricingNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "breakdown": [{"name": n, "cost": c} for n, c in breakdown],
        "total": total,
        "threshold": HIGH_COST_THRESHOLD,
    }


def _next_output_index(outputs_dir: Path, base: str) -> int:
    """Return the next available index for {base}_N.* so we never overwrite existing files."""
    if not outputs_dir.exists():
        return 1
    max_n = 0
    prefix = f"{base}_"
    for p in outputs_dir.iterdir():
        if not p.is_file() or not p.name.startswith(prefix):
            continue
        stem = p.stem
        suffix = stem[len(prefix):]
        if suffix.isdigit():
            max_n = max(max_n, int(suffix))
    return max_n + 1


def _save_outputs_from_event(output: dict, procedure_name: str, outputs_dir: Path, counter: list) -> None:
    """Download images/video from step output and save to outputs/{procedure_name}_{n}.ext."""
    import urllib.request
    base = procedure_name or "output"
    base = "".join(c if c.isalnum() or c in "_-" else "_" for c in base).strip("_") or "output"
    for img in output.get("images") or []:
        url = img.get("url") if isinstance(img, dict) else None
        if not url:
            continue
        counter[0] += 1
        ext = ".png"
        if isinstance(img, dict) and img.get("content_type"):
            ct = img["content_type"]
            if "jpeg" in ct or "jpg" in ct:
                ext = ".jpg"
            elif "webp" in ct:
                ext = ".webp"
        dest = outputs_dir / f"{base}_{counter[0]}{ext}"
        urllib.request.urlretrieve(url, dest)
    video = output.get("video")
    if video:
        url = video.get("url") if isinstance(video, dict) else video
        if url:
            counter[0] += 1
            dest = outputs_dir / f"{base}_{counter[0]}.mp4"
            urllib.request.urlretrieve(url, dest)


def _run_workflow(workflow_dict: dict, event_queue: Queue, procedure_name: str | None = None):
    """Run workflow in thread, push events to queue. Saves outputs to outputs/ with procedure_name_N."""
    outputs_dir = PROJECT_ROOT / "outputs"
    outputs_dir.mkdir(exist_ok=True)
    base = procedure_name or "output"
    base = "".join(c if c.isalnum() or c in "_-" else "_" for c in base).strip("_") or "output"
    counter = [_next_output_index(outputs_dir, base) - 1]
    try:
        engine = WorkflowEngine.from_dict(workflow_dict)

        def on_progress(evt: dict):
            event_queue.put(evt)
            if evt.get("type") == "step_end" and procedure_name and evt.get("output"):
                _save_outputs_from_event(evt["output"], procedure_name, outputs_dir, counter)

        engine.run(skip_confirm=True, progress_callback=on_progress)
    except Exception as e:
        event_queue.put({"type": "error", "message": str(e)})


def _queue_get(q: Queue, timeout: float = 0.2):
    try:
        return q.get(timeout=timeout)
    except Empty:
        return None


@app.post("/api/run")
async def run_workflow(req: WorkflowRequest):
    """Stream workflow progress via SSE. Requires confirmed=True."""
    if not req.confirmed:
        raise HTTPException(status_code=400, detail="confirmed must be true")

    event_queue = Queue()
    proc_name = req.procedure_name or (req.workflow.get("steps", [{}])[0].get("name", "output") if req.workflow.get("steps") else "output")

    async def event_stream():
        loop = asyncio.get_event_loop()
        loop.run_in_executor(executor, _run_workflow, req.workflow, event_queue, proc_name)
        while True:
            evt = await loop.run_in_executor(None, _queue_get, event_queue)
            if evt is None:
                await asyncio.sleep(0.05)
                continue
            yield f"event: {evt.get('type', 'message')}\ndata: {json.dumps(evt)}\n\n"
            if evt.get("type") in ("complete", "error"):
                break

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


outputs_dir = PROJECT_ROOT / "outputs"
outputs_dir.mkdir(exist_ok=True)
app.mount("/outputs", StaticFiles(directory=str(outputs_dir)), name="outputs")


@app.get("/api/workflows")
async def list_workflows():
    """List saved workflow names (from .json and .py files)."""
    SAVED_WORKFLOWS_DIR.mkdir(exist_ok=True)
    names = sorted(
        set(p.stem for p in SAVED_WORKFLOWS_DIR.glob("*.json"))
        | set(p.stem for p in SAVED_WORKFLOWS_DIR.glob("*.py"))
    )
    return {"workflows": names}


@app.get("/api/workflows/{name}")
async def get_workflow(name: str):
    """Load a saved workflow. Returns JSON for .json files. .py workflows cannot be loaded in GUI."""
    json_path = SAVED_WORKFLOWS_DIR / f"{name}.json"
    if json_path.exists():
        data = json.loads(json_path.read_text())
        return data
    raise HTTPException(
        status_code=404,
        detail=f"Workflow '{name}' not found or is a .py file (only .json can be loaded in GUI)",
    )


@app.post("/api/workflows/save")
async def save_workflow(req: SaveWorkflowRequest):
    """Save workflow as JSON. If overwrite=True and file exists, update in place. Else create new (append _2, _3 if name exists)."""
    SAVED_WORKFLOWS_DIR.mkdir(exist_ok=True)
    name = req.name.strip() or "workflow"
    name = "".join(c if c.isalnum() or c in "_-" else "_" for c in name).strip("_") or "workflow"
    json_path = SAVED_WORKFLOWS_DIR / f"{name}.json"
    if req.overwrite and json_path.exists():
        json_path.write_text(json.dumps(req.workflow, indent=2))
        return {"saved_as": name, "path": str(json_path), "updated": True}
    candidate = name
    counter = 2
    while (SAVED_WORKFLOWS_DIR / f"{candidate}.json").exists() or (SAVED_WORKFLOWS_DIR / f"{candidate}.py").exists():
        candidate = f"{name}_{counter}"
        counter += 1
    dest = SAVED_WORKFLOWS_DIR / f"{candidate}.json"
    dest.write_text(json.dumps(req.workflow, indent=2))
    return {"saved_as": candidate, "path": str(dest), "updated": False}


@app.delete("/api/workflows/{name}")
async def delete_workflow(name: str):
    """Delete a saved workflow. Only .json files can be deleted from GUI."""
    json_path = SAVED_WORKFLOWS_DIR / f"{name}.json"
    if not json_path.exists():
        raise HTTPException(status_code=404, detail=f"Procedure '{name}' not found")
    json_path.unlink()
    return {"deleted": name}


class RenameWorkflowRequest(BaseModel):
    new_name: str


@app.post("/api/workflows/{name}/rename")
async def rename_workflow(name: str, req: RenameWorkflowRequest):
    """Rename a saved procedure. Only .json files. Returns new name."""
    json_path = SAVED_WORKFLOWS_DIR / f"{name}.json"
    if not json_path.exists():
        raise HTTPException(status_code=404, detail=f"Procedure '{name}' not found")
    new_name = req.new_name.strip() or "workflow"
    new_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in new_name).strip("_") or "workflow"
    new_path = SAVED_WORKFLOWS_DIR / f"{new_name}.json"
    if new_path.exists() and new_path.resolve() != json_path.resolve():
        raise HTTPException(status_code=409, detail=f"Procedure '{new_name}' already exists")
    json_path.rename(new_path)
    return {"renamed_to": new_name}


@app.get("/api/outputs")
async def list_outputs():
    """List files in outputs directory."""
    out_dir = PROJECT_ROOT / "outputs"
    if not out_dir.exists():
        return {"files": []}
    files = []
    for p in sorted(out_dir.iterdir()):
        if p.is_file() and not p.name.startswith("."):
            files.append({
                "name": p.name,
                "url": f"/outputs/{p.name}",
            })
    return {"files": files}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5050)
