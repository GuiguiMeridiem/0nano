"""GUI/backend API for the fixed 4-step short-video procedure flow."""

import base64
import mimetypes
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from pricing.registry import HIGH_COST_THRESHOLD, REGISTRY, estimate as estimate_price
from services.asset_storage import AssetStorage
from services.fal_client import run_queue
from services.media_processor import MediaProcessor
from services.procedure_repository import ProcedureRepository, STEP_KEYS

app = FastAPI(title="0nano GUI")

static_dir = PROJECT_ROOT / "gui" / "static"
data_dir = PROJECT_ROOT / "data"
db_path = data_dir / "0nano.db"
assets_root = PROJECT_ROOT / "procedure_assets"

repo = ProcedureRepository(db_path)
storage = AssetStorage(assets_root)
media = MediaProcessor()


STEP_TYPE_MAP = {
    "generate_base_image": "image",
    "modify_images": "image",
    "generate_video": "video",
    "modify_video": "video",
}


def _default_params_for_model_type(model_type: str) -> dict[str, Any]:
    if model_type == "image":
        return {
            "prompt": "preview",
            "num_images": 1,
            "resolution": "1K",
            "aspect_ratio": "9:16",
        }
    if model_type == "video":
        return {
            "prompt": "preview",
            "duration": 5,
            "resolution": "720p",
            "aspect_ratio": "16:9",
            "generate_audio": True,
        }
    return {"prompt": "preview"}


class ProcedureCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class ProcedureRenameRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class StepConfigRequest(BaseModel):
    model_id: str | None = None
    params: dict[str, Any] = {}


class StepEstimateRequest(BaseModel):
    model_id: str
    params: dict[str, Any] = {}


class ModelPreviewRequest(BaseModel):
    step_type: str
    params: dict[str, Any] = {}


class StepRunRequest(BaseModel):
    model_id: str
    params: dict[str, Any] = {}
    confirmed: bool = False
    expected_cost: float | None = None


class ArchiveAssetRequest(BaseModel):
    archived: bool = True


class ImageTransformRequest(BaseModel):
    operation: str
    params: dict[str, Any] = {}


class ImageAiEditRequest(BaseModel):
    model_id: str
    prompt: str
    params: dict[str, Any] = {}
    confirmed: bool = False
    expected_cost: float | None = None


class VideoCutRequest(BaseModel):
    start_sec: float = 0.0
    end_sec: float


class VideoShakeRequest(BaseModel):
    intensity: float = 0.03
    first_seconds: float = 1.0


def _sanitize_name(raw: str) -> str:
    clean = "".join(c if c.isalnum() or c in "_- " else "_" for c in raw.strip())
    clean = clean.strip() or "procedure"
    return clean[:120]


def _validate_step_key(step_key: str) -> str:
    if step_key not in STEP_KEYS:
        raise HTTPException(status_code=400, detail=f"Unknown step '{step_key}'")
    return step_key


def _require_procedure(procedure_id: int) -> dict[str, Any]:
    p = repo.get_procedure(procedure_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"Procedure {procedure_id} not found")
    return p


def _asset_public_url(asset_path: str) -> str:
    rel = Path(asset_path).resolve().relative_to(assets_root.resolve())
    return f"/media/{str(rel).replace(os.sep, '/')}"


def _asset_with_url(asset: dict[str, Any] | None) -> dict[str, Any] | None:
    if not asset:
        return None
    out = dict(asset)
    out["url"] = _asset_public_url(out["path"])
    return out


def _estimate_or_400(model_id: str, params: dict[str, Any]) -> float:
    try:
        return float(estimate_price(model_id, params))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


def _require_confirmed(expected_cost: float | None, actual_cost: float, confirmed: bool) -> None:
    if not confirmed:
        raise HTTPException(status_code=400, detail="Run rejected: confirmed must be true before API call")
    if expected_cost is None:
        raise HTTPException(status_code=400, detail="Run rejected: expected_cost is required")
    if abs(float(expected_cost) - float(actual_cost)) > 0.0001:
        raise HTTPException(
            status_code=409,
            detail=f"Estimate changed. Expected {expected_cost:.4f}, current {actual_cost:.4f}",
        )


def _content_type_to_ext(content_type: str | None) -> str:
    if not content_type:
        return ".png"
    if "jpeg" in content_type or "jpg" in content_type:
        return ".jpg"
    if "webp" in content_type:
        return ".webp"
    if "gif" in content_type:
        return ".gif"
    return ".png"


def _image_data_url(path: Path) -> str:
    mime, _ = mimetypes.guess_type(str(path))
    mime = mime or "image/png"
    b64 = base64.b64encode(path.read_bytes()).decode()
    return f"data:{mime};base64,{b64}"


def _run_generate_base_image(
    procedure_id: int,
    model_id: str,
    params: dict[str, Any],
) -> list[dict[str, Any]]:
    result = run_queue(model_id, params)
    output_assets: list[dict[str, Any]] = []
    for img in result.get("images", []):
        url = img.get("url") if isinstance(img, dict) else None
        if not url:
            continue
        ext = _content_type_to_ext(img.get("content_type") if isinstance(img, dict) else None)
        local_path = storage.download_to_asset(
            procedure_id=procedure_id,
            kind="image",
            remote_url=url,
            ext_hint=ext,
            prefix="generated",
        )
        asset = repo.create_asset(
            procedure_id=procedure_id,
            step_key="generate_base_image",
            kind="image",
            path=str(local_path.resolve()),
            source="generated",
            meta={"model_id": model_id, "params": params},
        )
        output_assets.append(_asset_with_url(asset))
    return output_assets


def _run_generate_video(
    procedure_id: int,
    model_id: str,
    params: dict[str, Any],
) -> list[dict[str, Any]]:
    final_params = dict(params or {})
    src_asset_id = final_params.pop("source_asset_id", None)
    if src_asset_id:
        src = repo.get_asset(int(src_asset_id))
        if not src or src["kind"] != "image":
            raise HTTPException(status_code=400, detail="source_asset_id must reference an image asset")
        final_params["image_url"] = _image_data_url(Path(src["path"]))
    result = run_queue(model_id, final_params, timeout=900.0)
    v = result.get("video")
    video_url = None
    if isinstance(v, dict):
        video_url = v.get("url")
    elif isinstance(v, str):
        video_url = v
    if not video_url:
        return []
    local_path = storage.download_to_asset(
        procedure_id=procedure_id,
        kind="video",
        remote_url=video_url,
        ext_hint=".mp4",
        prefix="generated",
    )
    asset = repo.create_asset(
        procedure_id=procedure_id,
        step_key="generate_video",
        kind="video",
        path=str(local_path.resolve()),
        source="generated",
        meta={"model_id": model_id, "params": final_params},
    )
    return [_asset_with_url(asset)]


@app.get("/", response_class=HTMLResponse)
async def index():
    return (static_dir / "index.html").read_text()


app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
app.mount("/media", StaticFiles(directory=str(assets_root)), name="media")


@app.get("/api/models")
async def list_models():
    models = []
    for mid, info in REGISTRY.items():
        model_type = info.get("type", "image")
        default_estimated_cost = None
        try:
            default_estimated_cost = float(
                estimate_price(mid, _default_params_for_model_type(model_type))
            )
        except Exception:
            default_estimated_cost = None
        models.append(
            {
                "id": mid,
                "description": info.get("description", ""),
                "type": model_type,
                "quality_stars": info.get("quality_stars", 2),
                "pricing_note": info.get("pricing_note", ""),
                "default_estimated_cost": default_estimated_cost,
            }
        )
    return {"models": models}


@app.post("/api/model-previews")
async def model_previews(req: ModelPreviewRequest):
    type_map = {
        "generate_base_image": "image",
        "generate_video": "video",
        "image": "image",
        "video": "video",
    }
    target_type = type_map.get(req.step_type)
    if not target_type:
        return {"previews": []}

    previews = []
    for model_id, info in REGISTRY.items():
        if info.get("type") != target_type:
            continue
        try:
            estimated = float(estimate_price(model_id, req.params or {}))
        except Exception:
            estimated = None
        previews.append({"id": model_id, "estimated_cost": estimated})
    return {"previews": previews}


@app.get("/api/procedures")
async def list_procedures():
    return {"procedures": repo.list_procedures()}


@app.post("/api/procedures")
async def create_procedure(req: ProcedureCreateRequest):
    name = _sanitize_name(req.name)
    if repo.get_procedure_by_name(name):
        raise HTTPException(status_code=409, detail=f"Procedure '{name}' already exists")
    p = repo.create_procedure(name)
    storage.procedure_dir(int(p["id"]))
    return {"procedure": p}


@app.get("/api/procedures/{procedure_id}")
async def get_procedure(procedure_id: int):
    p = _require_procedure(procedure_id)
    return {
        "procedure": p,
        "step_configs": repo.list_step_configs(procedure_id),
        "assets": [_asset_with_url(a) for a in repo.list_assets(procedure_id)],
    }


@app.post("/api/procedures/{procedure_id}/rename")
async def rename_procedure(procedure_id: int, req: ProcedureRenameRequest):
    _require_procedure(procedure_id)
    name = _sanitize_name(req.name)
    existing = repo.get_procedure_by_name(name)
    if existing and int(existing["id"]) != procedure_id:
        raise HTTPException(status_code=409, detail=f"Procedure '{name}' already exists")
    out = repo.rename_procedure(procedure_id, name)
    return {"procedure": out}


@app.delete("/api/procedures/{procedure_id}")
async def delete_procedure(procedure_id: int):
    _require_procedure(procedure_id)
    ok = repo.delete_procedure(procedure_id)
    storage.delete_procedure_dir(procedure_id)
    return {"deleted": ok}


@app.get("/api/procedures/{procedure_id}/steps/{step_key}/config")
async def get_step_config(procedure_id: int, step_key: str):
    _require_procedure(procedure_id)
    key = _validate_step_key(step_key)
    return {"config": repo.get_step_config(procedure_id, key)}


@app.post("/api/procedures/{procedure_id}/steps/{step_key}/config")
async def save_step_config(procedure_id: int, step_key: str, req: StepConfigRequest):
    _require_procedure(procedure_id)
    key = _validate_step_key(step_key)
    config = repo.save_step_config(procedure_id, key, req.model_id, req.params or {})
    return {"config": config}


@app.post("/api/procedures/{procedure_id}/steps/{step_key}/estimate")
async def estimate_step(procedure_id: int, step_key: str, req: StepEstimateRequest):
    _require_procedure(procedure_id)
    key = _validate_step_key(step_key)
    model_type = STEP_TYPE_MAP[key]
    reg = REGISTRY.get(req.model_id)
    if not reg:
        raise HTTPException(status_code=400, detail=f"No pricing for model '{req.model_id}'")
    if reg.get("type") != model_type:
        raise HTTPException(status_code=400, detail=f"Model type must be '{model_type}' for step '{key}'")
    cost = _estimate_or_400(req.model_id, req.params or {})
    return {"estimated_cost": cost, "threshold": HIGH_COST_THRESHOLD}


@app.post("/api/procedures/{procedure_id}/steps/{step_key}/run")
async def run_step(procedure_id: int, step_key: str, req: StepRunRequest):
    _require_procedure(procedure_id)
    key = _validate_step_key(step_key)
    model_type = STEP_TYPE_MAP[key]
    reg = REGISTRY.get(req.model_id)
    if not reg:
        raise HTTPException(status_code=400, detail=f"No pricing for model '{req.model_id}'")
    if reg.get("type") != model_type:
        raise HTTPException(status_code=400, detail=f"Model type must be '{model_type}' for step '{key}'")

    params = dict(req.params or {})
    cost = _estimate_or_400(req.model_id, params)
    _require_confirmed(req.expected_cost, cost, req.confirmed)
    repo.save_step_config(procedure_id, key, req.model_id, params)
    run = repo.create_step_run(
        procedure_id=procedure_id,
        step_key=key,
        model_id=req.model_id,
        params=params,
        estimated_cost=cost,
        status="running",
        confirmed=True,
    )
    try:
        if key == "generate_base_image":
            created = _run_generate_base_image(procedure_id, req.model_id, params)
        elif key == "generate_video":
            created = _run_generate_video(procedure_id, req.model_id, params)
        else:
            # Modify steps are local operations and are exposed through dedicated asset endpoints.
            created = []
        repo.update_step_run_status(int(run["id"]), "completed")
        return {"run": repo.update_step_run_status(int(run["id"]), "completed"), "assets": created}
    except Exception as exc:
        repo.update_step_run_status(int(run["id"]), "failed", str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/procedures/{procedure_id}/assets")
async def list_assets(
    procedure_id: int,
    step_key: str | None = None,
    kind: str | None = None,
    archived: bool | None = None,
):
    _require_procedure(procedure_id)
    if step_key:
        _validate_step_key(step_key)
    items = repo.list_assets(procedure_id, step_key=step_key, kind=kind, archived=archived)
    return {"assets": [_asset_with_url(a) for a in items]}


@app.post("/api/procedures/{procedure_id}/assets/import-image")
async def import_image(procedure_id: int, file: UploadFile = File(...)):
    _require_procedure(procedure_id)
    suffix = Path(file.filename or "imported.png").suffix or ".png"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)
    try:
        local = storage.copy_imported_file(procedure_id, tmp_path, kind="image", ext=suffix)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
    asset = repo.create_asset(
        procedure_id=procedure_id,
        step_key="modify_images",
        kind="image",
        path=str(local.resolve()),
        source="imported",
    )
    return {"asset": _asset_with_url(asset)}


@app.post("/api/procedures/{procedure_id}/assets/import-video")
async def import_video(procedure_id: int, file: UploadFile = File(...)):
    _require_procedure(procedure_id)
    suffix = Path(file.filename or "imported.mp4").suffix or ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)
    try:
        local = storage.copy_imported_file(procedure_id, tmp_path, kind="video", ext=suffix)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
    asset = repo.create_asset(
        procedure_id=procedure_id,
        step_key="modify_video",
        kind="video",
        path=str(local.resolve()),
        source="imported",
    )
    return {"asset": _asset_with_url(asset)}


@app.delete("/api/assets/{asset_id}")
async def delete_asset(asset_id: int):
    asset = repo.delete_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail=f"Asset {asset_id} not found")
    storage.delete_file_if_exists(Path(asset["path"]))
    return {"deleted": asset_id}


@app.post("/api/assets/{asset_id}/archive")
async def archive_asset(asset_id: int, req: ArchiveAssetRequest):
    out = repo.set_asset_archived(asset_id, req.archived)
    if not out:
        raise HTTPException(status_code=404, detail=f"Asset {asset_id} not found")
    return {"asset": _asset_with_url(out)}


@app.post("/api/assets/{asset_id}/image-transform")
async def image_transform(asset_id: int, req: ImageTransformRequest):
    asset = repo.get_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail=f"Asset {asset_id} not found")
    if asset["kind"] != "image":
        raise HTTPException(status_code=400, detail="Asset is not an image")
    op = req.operation
    if op == "revert":
        done = media.image_revert(Path(asset["path"]))
        return {"asset": _asset_with_url(asset), "reverted": done}
    media.image_transform_in_place(Path(asset["path"]), op, req.params or {})
    meta = dict(asset.get("meta") or {})
    history = list(meta.get("transform_history") or [])
    history.append({"operation": op, "params": req.params or {}})
    meta["transform_history"] = history
    updated = repo.update_asset_meta(asset_id, meta)
    return {"asset": _asset_with_url(updated)}


@app.post("/api/assets/{asset_id}/image-ai-edit")
async def image_ai_edit(asset_id: int, req: ImageAiEditRequest):
    asset = repo.get_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail=f"Asset {asset_id} not found")
    if asset["kind"] != "image":
        raise HTTPException(status_code=400, detail="Asset is not an image")
    params = dict(req.params or {})
    params["prompt"] = req.prompt
    params["image_url"] = _image_data_url(Path(asset["path"]))
    cost = _estimate_or_400(req.model_id, params)
    _require_confirmed(req.expected_cost, cost, req.confirmed)
    run = repo.create_step_run(
        procedure_id=int(asset["procedure_id"]),
        step_key="modify_images",
        model_id=req.model_id,
        params=params,
        estimated_cost=cost,
        status="running",
        confirmed=True,
    )
    try:
        result = run_queue(req.model_id, params)
        created: list[dict[str, Any]] = []
        for img in result.get("images", []):
            url = img.get("url") if isinstance(img, dict) else None
            if not url:
                continue
            ext = _content_type_to_ext(img.get("content_type") if isinstance(img, dict) else None)
            local = storage.download_to_asset(
                procedure_id=int(asset["procedure_id"]),
                kind="image",
                remote_url=url,
                ext_hint=ext,
                prefix="ai_edit",
            )
            created_asset = repo.create_asset(
                procedure_id=int(asset["procedure_id"]),
                step_key="modify_images",
                kind="image",
                path=str(local.resolve()),
                source="ai_edit",
                parent_asset_id=asset_id,
                meta={"prompt": req.prompt, "model_id": req.model_id},
            )
            created.append(_asset_with_url(created_asset))
        repo.update_step_run_status(int(run["id"]), "completed")
        return {"assets": created}
    except Exception as exc:
        repo.update_step_run_status(int(run["id"]), "failed", str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/assets/{asset_id}/video-cut")
async def video_cut(asset_id: int, req: VideoCutRequest):
    asset = repo.get_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail=f"Asset {asset_id} not found")
    if asset["kind"] != "video":
        raise HTTPException(status_code=400, detail="Asset is not a video")
    media.video_cut_in_place(Path(asset["path"]), req.start_sec, req.end_sec)
    updated = repo.update_asset_meta(
        asset_id,
        {
            **(asset.get("meta") or {}),
            "last_edit": {"operation": "cut", "start_sec": req.start_sec, "end_sec": req.end_sec},
        },
    )
    return {"asset": _asset_with_url(updated)}


@app.post("/api/assets/{asset_id}/video-shake")
async def video_shake(asset_id: int, req: VideoShakeRequest):
    asset = repo.get_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail=f"Asset {asset_id} not found")
    if asset["kind"] != "video":
        raise HTTPException(status_code=400, detail="Asset is not a video")
    media.video_shake_in_place(Path(asset["path"]), intensity=req.intensity, first_seconds=req.first_seconds)
    updated = repo.update_asset_meta(
        asset_id,
        {
            **(asset.get("meta") or {}),
            "last_edit": {"operation": "shake", "intensity": req.intensity, "first_seconds": req.first_seconds},
        },
    )
    return {"asset": _asset_with_url(updated)}


@app.post("/api/assets/{asset_id}/video-subtitles")
async def video_subtitles_stub(asset_id: int):
    asset = repo.get_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail=f"Asset {asset_id} not found")
    if asset["kind"] != "video":
        raise HTTPException(status_code=400, detail="Asset is not a video")
    return media.subtitles_stub(Path(asset["path"]))


@app.get("/api/procedures/{procedure_id}/runs")
async def list_runs(procedure_id: int, step_key: str | None = None):
    _require_procedure(procedure_id)
    if step_key:
        _validate_step_key(step_key)
    return {"runs": repo.list_step_runs(procedure_id, step_key=step_key)}


@app.post("/api/procedures/{procedure_id}/assets/link-video")
async def create_video_from_existing(
    procedure_id: int,
    file_path: str = Form(...),
):
    """Internal helper: register an existing local video path as a procedure asset."""
    _require_procedure(procedure_id)
    src = Path(file_path)
    if not src.exists() or not src.is_file():
        raise HTTPException(status_code=400, detail="file_path does not exist")
    local = storage.copy_imported_file(procedure_id, src, kind="video", ext=src.suffix or ".mp4")
    asset = repo.create_asset(
        procedure_id=procedure_id,
        step_key="modify_video",
        kind="video",
        path=str(local.resolve()),
        source="imported",
    )
    return {"asset": _asset_with_url(asset)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5050)
