# 0nano Architecture Guide

This document describes the current architecture after the short-form video refactor.

## 1) Product model

0nano is now **GUI-first** and procedure-oriented.

Each procedure is a single short-form video project with 4 fixed steps:

1. `generate_base_image`
2. `modify_images`
3. `generate_video`
4. `modify_video`

Users run each step independently, can iterate multiple times, and keep multiple variants.

## 2) Runtime architecture

### Layers

1. **GUI layer**
   - `gui/static/index.html`
   - `gui/static/app.js`
   - Fixed step panels, per-step estimate/confirm/run flow

2. **API layer**
   - `gui/app.py` (FastAPI)
   - Procedure CRUD, step config/estimate/run, asset operations

3. **Domain/service layer**
   - `services/procedure_repository.py` (SQLite repository)
   - `services/asset_storage.py` (per-procedure filesystem management)
   - `services/media_processor.py` (image/video local edits)
   - `services/fal_client.py` (fal provider adapter)

4. **Pricing layer**
   - `pricing/registry.py` (model registry + estimate functions + threshold)

## 3) Persistence model

### SQLite

Database: `data/0nano.db`

Core tables:

- `procedures`
- `step_configs`
- `assets`
- `step_runs`

Notes:

- One row in `assets` == one media variant.
- Archive is modeled by `assets.archived = 1`.
- No branching tree: variants are flat and listed.

### Filesystem assets

Asset root: `procedure_assets/`

Structure:

- `procedure_assets/<procedure_id>/images/*`
- `procedure_assets/<procedure_id>/videos/*`

Assets are always local files; API exposes them via `/media/...`.

## 4) Cost confirmation model

Cost is enforced **per step run**:

1. Client requests `/steps/{step}/estimate`.
2. User confirms.
3. Client calls `/steps/{step}/run` with:
   - `confirmed=true`
   - `expected_cost`
4. Server recomputes estimate and rejects if changed.

No model call is made without explicit confirmed pre-run data.

## 5) Step behavior

### Step 1 - Generate base image

- Uses image models from `pricing/registry.py`.
- Saves each output image as a new asset (`source=generated`).

### Step 2 - Modify images

- **Import image**: creates image asset (`source=imported`) and lets user skip step 1.
- **AI modify**: creates duplicate variants (`source=ai_edit`, parent set).
- **Basic transforms**: in-place reversible edits:
  - horizontal flip
  - zoom
  - filter
- Revert restores from an `.orig` backup.

### Step 3 - Generate video

- Uses video models from `pricing/registry.py`.
- Can reference a source image asset.
- Saves generated videos as assets (`source=generated`).

### Step 4 - Modify video

- Local edits:
  - cut
  - first-second phone-like shake (2-4% jitter)
- Subtitles endpoint exists as a stub response (not implemented yet).

## 6) API overview

Implemented in `gui/app.py`:

- `GET /api/models`
- Procedure CRUD:
  - `GET /api/procedures`
  - `POST /api/procedures`
  - `GET /api/procedures/{id}`
  - `POST /api/procedures/{id}/rename`
  - `DELETE /api/procedures/{id}`
- Step APIs:
  - `GET/POST /api/procedures/{id}/steps/{step}/config`
  - `POST /api/procedures/{id}/steps/{step}/estimate`
  - `POST /api/procedures/{id}/steps/{step}/run`
- Asset APIs:
  - `GET /api/procedures/{id}/assets`
  - `POST /api/procedures/{id}/assets/import-image`
  - `DELETE /api/assets/{asset_id}`
  - `POST /api/assets/{asset_id}/archive`
  - `POST /api/assets/{asset_id}/image-transform`
  - `POST /api/assets/{asset_id}/image-ai-edit`
  - `POST /api/assets/{asset_id}/video-cut`
  - `POST /api/assets/{asset_id}/video-shake`
  - `POST /api/assets/{asset_id}/video-subtitles`

## 7) Interface-independence strategy

GUI is the product path, but core logic is reusable:

- Storage and repository code is framework-agnostic Python.
- Media edits are service-level functions.
- fal provider integration is isolated in `services/fal_client.py`.

This allows a future API-only server or another frontend to reuse the same core modules.

## 8) Legacy notes

- Old JSON/Python workflow authoring remains in repo history but is no longer the product architecture.
- `main.py` now acts as a GUI server launcher entrypoint instead of a workflow composition file.
