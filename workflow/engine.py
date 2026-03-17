import json
import re
import sys
import time
import inspect
import importlib.util
from pathlib import Path
from typing import List, Callable, Optional

from .steps.base import BaseStep
from .steps.ai_image import AIImageStep
from .steps.ai_text import AITextStep
from .steps.ai_video import AIVideoStep
from .steps.custom import CustomStep
from . import functions as builtin_functions
from pricing.registry import PricingNotFoundError, HIGH_COST_THRESHOLD

SAVED_WORKFLOWS_DIR = Path("saved_workflows")


class WorkflowEngine:
    """
    Runs a sequence of steps, threading a shared context dict between them.

    Before executing, estimates the total cost and asks the user to confirm:
    - Cost <= HIGH_COST_THRESHOLD : simple Y/n prompt
    - Cost >  HIGH_COST_THRESHOLD : user must type the exact dollar amount
    - Unknown model in registry   : aborts with instructions to add pricing

    Save a workflow snapshot:
        WorkflowEngine([...], save=True)          # name derived from first step
        WorkflowEngine([...], save="my_workflow") # explicit name

    Load and run a saved workflow:
        workflow = WorkflowEngine.load("my_workflow")
        workflow.run()
    """

    def __init__(self, steps: List[BaseStep], save=None):
        self.steps = steps
        if save is True:
            self._save(self._name_from_steps())
        elif isinstance(save, str):
            self._save(save)

    # ── Save / Load ───────────────────────────────────────────────────────────

    def _name_from_steps(self) -> str:
        raw = self.steps[0].name if self.steps else "workflow"
        return re.sub(r"[^a-z0-9]+", "_", raw.lower()).strip("_") or "workflow"

    def _unique_name(self, name: str) -> str:
        """Return name, name_2, name_3 … until one doesn't exist."""
        SAVED_WORKFLOWS_DIR.mkdir(exist_ok=True)
        candidate = name
        counter = 2
        while (SAVED_WORKFLOWS_DIR / f"{candidate}.py").exists():
            candidate = f"{name}_{counter}"
            counter += 1
        return candidate

    def _save(self, name: str):
        """Copy the calling source file to saved_workflows/<name>.py, neutralising save=."""
        SAVED_WORKFLOWS_DIR.mkdir(exist_ok=True)

        # Find the first stack frame that isn't this file (engine.py)
        source_file = None
        for frame_info in inspect.stack():
            path = Path(frame_info.filename)
            if path.resolve() != Path(__file__).resolve():
                source_file = path
                break

        if source_file is None or not source_file.exists():
            print("  Warning: could not locate source file to save.")
            return

        dest_name = self._unique_name(name)
        dest = SAVED_WORKFLOWS_DIR / f"{dest_name}.py"

        source = source_file.read_text()
        # Replace save=True / save="name" / save='name' with save=None
        # so re-loading this file won't trigger another save
        patched = re.sub(
            r'\bsave\s*=\s*(?:True|"[^"]*"|\'[^\']*\')',
            "save=None",
            source,
        )

        dest.write_text(patched)
        print(f"\n  Workflow saved → saved_workflows/{dest_name}.py")

    @classmethod
    def from_dict(cls, data: dict) -> "WorkflowEngine":
        """
        Build a WorkflowEngine from a dict (e.g. parsed JSON).

        Format:
            {
                "name": "optional",
                "steps": [
                    {"type": "ai_image", "name": "...", "output_key": "...", "model_id": "...", "params": {...}},
                    {"type": "ai_text", ...},
                    {"type": "ai_video", ...},
                    {"type": "custom", "name": "...", "output_key": "...", "fn": "save_outputs", "params": {"from_key": "..."}}
                ]
            }
        """
        steps_data = data.get("steps", [])
        steps = []
        for s in steps_data:
            stype = s.get("type", "")
            name = s.get("name", "step")
            output_key = s.get("output_key", "output")
            step = None

            if stype == "ai_image":
                params = dict(s.get("params", {}))
                if not params.get("prompt"):
                    params["prompt"] = "A beautiful image"
                params.setdefault("num_images", 1)
                params.setdefault("aspect_ratio", "auto")
                params.setdefault("resolution", "1K")
                params.setdefault("output_format", "png")
                params.setdefault("safety_tolerance", "4")
                step = AIImageStep(
                    name=name,
                    output_key=output_key,
                    model_id=s.get("model_id", ""),
                    # Important: ignore runtime context and return captured params.
                    # Using lambda p=params would get overridden by the passed context arg.
                    params_fn=lambda _ctx, p=params: p,
                )
            elif stype == "ai_text":
                params = dict(s.get("params", {}))
                step = AITextStep(
                    name=name,
                    output_key=output_key,
                    model_id=s.get("model_id", ""),
                    params_fn=lambda _ctx, p=params: p,
                )
            elif stype == "ai_video":
                params = dict(s.get("params", {}))
                step = AIVideoStep(
                    name=name,
                    output_key=output_key,
                    model_id=s.get("model_id", ""),
                    params_fn=lambda _ctx, p=params: p,
                )
            elif stype == "custom":
                fn_name = s.get("fn", "")
                fn_params = s.get("params", {})
                if fn_name == "save_outputs":
                    from_key = fn_params.get("from_key", "")
                    fn = lambda ctx, k=from_key: builtin_functions.save_outputs(ctx, k)
                else:
                    raise ValueError(f"Unknown custom function: {fn_name}")
                step = CustomStep(name=name, output_key=output_key, fn=fn)
            else:
                raise ValueError(f"Unknown step type: {stype}")

            if step:
                steps.append(step)

        return cls(steps)

    def to_dict(self) -> dict:
        """Serialize to a dict (JSON-compatible). Only works for steps built from dict."""
        steps_data = []
        for step in self.steps:
            if isinstance(step, AIImageStep):
                params = step.params_fn({}) if hasattr(step.params_fn, "__call__") else {}
                steps_data.append({
                    "type": "ai_image",
                    "name": step.name,
                    "output_key": step.output_key,
                    "model_id": step.model_id,
                    "params": params,
                })
            elif isinstance(step, AITextStep):
                params = step.params_fn({}) if hasattr(step.params_fn, "__call__") else {}
                steps_data.append({
                    "type": "ai_text",
                    "name": step.name,
                    "output_key": step.output_key,
                    "model_id": step.model_id,
                    "params": params,
                })
            elif isinstance(step, AIVideoStep):
                params = step.params_fn({}) if hasattr(step.params_fn, "__call__") else {}
                steps_data.append({
                    "type": "ai_video",
                    "name": step.name,
                    "output_key": step.output_key,
                    "model_id": step.model_id,
                    "params": params,
                })
            elif isinstance(step, CustomStep):
                steps_data.append({
                    "type": "custom",
                    "name": step.name,
                    "output_key": step.output_key,
                    "fn": "save_outputs",
                    "params": {},
                })
        return {"steps": steps_data}

    @classmethod
    def load(cls, name: str) -> "WorkflowEngine":
        """
        Load a previously saved workflow by name.
        Checks for .json first, then .py.

        Usage:
            workflow = WorkflowEngine.load("my_workflow")
            workflow.run()
        """
        json_path = SAVED_WORKFLOWS_DIR / f"{name}.json"
        py_path = SAVED_WORKFLOWS_DIR / f"{name}.py"
        if json_path.exists():
            data = json.loads(json_path.read_text())
            return cls.from_dict(data)
        if py_path.exists():
            project_root = str(Path(__file__).resolve().parent.parent)
            if project_root not in sys.path:
                sys.path.insert(0, project_root)
            spec = importlib.util.spec_from_file_location(name, py_path.resolve())
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if not hasattr(module, "workflow"):
                raise AttributeError(
                    f"Saved workflow '{name}.py' has no 'workflow' variable at module level."
                )
            return module.workflow

        available = sorted(
            set(p.stem for p in SAVED_WORKFLOWS_DIR.glob("*.py"))
            | set(p.stem for p in SAVED_WORKFLOWS_DIR.glob("*.json"))
        )
        hint = f"Available: {available}" if available else "No saved workflows found."
        raise FileNotFoundError(
            f"No saved workflow named '{name}' in {SAVED_WORKFLOWS_DIR}/\n  {hint}"
        )

    # ── Cost estimation ───────────────────────────────────────────────────────

    def get_cost_breakdown(self) -> tuple[list[tuple[str, float]], float]:
        """Return [(step_name, cost), ...] and total. Raises PricingNotFoundError if model unknown."""
        breakdown = []
        total = 0.0
        for step in self.steps:
            cost = step.estimate_cost()
            if cost > 0:
                breakdown.append((step.name, cost))
            total += cost
        return breakdown, total

    def _print_cost_breakdown(self) -> float:
        """Print per-step cost breakdown and return total."""
        breakdown, total = self.get_cost_breakdown()
        print("\n  Cost estimate:")
        for name, cost in breakdown:
            print(f"    {name:<40} ${cost:.4f}")
        print(f"    {'─' * 47}")
        print(f"    {'Total':<40} ${total:.4f}")
        return total

    def _confirm(self, total: float) -> bool:
        """Prompt the user to confirm the estimated cost. Returns True if confirmed."""
        formatted = f"${total:.2f}"
        if total > HIGH_COST_THRESHOLD:
            print(f"\n  ⚠  Cost exceeds the ${HIGH_COST_THRESHOLD:.2f} safety limit.")
            answer = input(f"\n  Type {formatted} to confirm and proceed: ").strip()
            return answer == formatted
        else:
            answer = input(f"\n  Proceed? [Y/n]: ").strip().lower()
            return answer in ("", "y", "yes")

    # ── Run ───────────────────────────────────────────────────────────────────

    def run(
        self,
        initial_context: dict = None,
        skip_confirm: bool = False,
        progress_callback: Optional[Callable[[dict], None]] = None,
    ) -> dict:
        """
        Run the workflow.

        skip_confirm: If True, skip cost check and confirmation (for GUI/API).
        progress_callback: Callback receiving events:
            {"type": "step_start", "step": i, "name": "...", "total": n}
            {"type": "step_end", "step": i, "name": "...", "elapsed": float, "output": {...}}
            {"type": "complete"}
        """
        context = initial_context or {}
        total_steps = len(self.steps)

        if not skip_confirm:
            print(f"\n{'='*50}")
            print(f"  0nano workflow  ({total_steps} step{'s' if total_steps != 1 else ''})")
            print(f"{'='*50}")
            try:
                estimated_total = self._print_cost_breakdown()
            except PricingNotFoundError as e:
                print(f"\n  ERROR: {e}")
                print("  Workflow aborted.")
                sys.exit(1)
            if not self._confirm(estimated_total):
                print("\n  Workflow aborted.")
                sys.exit(0)
            print()

        for i, step in enumerate(self.steps, 1):
            if progress_callback:
                progress_callback({
                    "type": "step_start",
                    "step": i,
                    "name": step.name,
                    "total": total_steps,
                })
            t0 = time.time()
            step.execute(context)
            elapsed = time.time() - t0
            output = context.get(step.output_key)
            if progress_callback:
                out_summary = None
                if isinstance(output, dict) and "images" in output:
                    out_summary = {"images": [{"url": img.get("url"), "content_type": img.get("content_type")} for img in output["images"]]}
                elif isinstance(output, dict) and "video" in output:
                    v = output.get("video")
                    out_summary = {"video": v if isinstance(v, dict) else {"url": v}} if v else None
                progress_callback({
                    "type": "step_end",
                    "step": i,
                    "name": step.name,
                    "elapsed": round(elapsed, 2),
                    "output": out_summary,
                })
            if not progress_callback:
                print(f"[{i}/{total_steps}] {step.name} ({elapsed:.1f}s)")
                print()

        if progress_callback:
            progress_callback({"type": "complete"})
        if not progress_callback:
            print(f"{'='*50}")
            print(f"  Workflow complete")
            print(f"{'='*50}\n")
        return context
