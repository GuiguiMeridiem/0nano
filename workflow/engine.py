import re
import sys
import inspect
import importlib.util
from pathlib import Path
from typing import List

from .steps.base import BaseStep
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
    def load(cls, name: str) -> "WorkflowEngine":
        """
        Load a previously saved workflow by name.

        Usage:
            workflow = WorkflowEngine.load("my_workflow")
            workflow.run()
        """
        path = SAVED_WORKFLOWS_DIR / f"{name}.py"
        if not path.exists():
            available = sorted(p.stem for p in SAVED_WORKFLOWS_DIR.glob("*.py"))
            hint = f"Available: {available}" if available else "No saved workflows found."
            raise FileNotFoundError(
                f"No saved workflow named '{name}' in {SAVED_WORKFLOWS_DIR}/\n  {hint}"
            )

        # Ensure project root is in sys.path so relative imports work
        project_root = str(Path(__file__).resolve().parent.parent)
        if project_root not in sys.path:
            sys.path.insert(0, project_root)

        spec = importlib.util.spec_from_file_location(name, path.resolve())
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        if not hasattr(module, "workflow"):
            raise AttributeError(
                f"Saved workflow '{name}.py' has no 'workflow' variable at module level."
            )
        return module.workflow

    # ── Cost estimation ───────────────────────────────────────────────────────

    def _print_cost_breakdown(self) -> float:
        """Print per-step cost breakdown and return total."""
        print("\n  Cost estimate:")
        total = 0.0
        for step in self.steps:
            cost = step.estimate_cost()
            if cost > 0:
                print(f"    {step.name:<40} ${cost:.4f}")
            total += cost
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

    def run(self, initial_context: dict = None) -> dict:
        context = initial_context or {}
        total = len(self.steps)

        print(f"\n{'='*50}")
        print(f"  0nano workflow  ({total} step{'s' if total != 1 else ''})")
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
            print(f"[{i}/{total}] {step.name}")
            step.execute(context)
            print()

        print(f"{'='*50}")
        print(f"  Workflow complete")
        print(f"{'='*50}\n")
        return context
