# 0nano

GUI-first tool for short-form AI video generation with step-by-step control.

Each procedure is one video project with independent steps you can rerun and iterate:

1. Generate base image
2. Modify images
3. Generate video
4. Modify video

Variants are stored locally and linked to their procedure.

## Key changes

- Fixed 4-step architecture (no arbitrary workflow builder).
- Local SQLite persistence (`data/0nano.db`) instead of saved JSON procedures.
- Per-step cost estimate + confirmation before any model API call.
- Procedure-scoped local assets (`procedure_assets/<procedure_id>/...`).
- Image/video editing tools integrated in the GUI.

## Project structure

```text
0nano/
├── main.py                      # GUI/API launcher entrypoint
├── gui/
│   ├── app.py                   # FastAPI backend (procedures, steps, assets)
│   └── static/
│       ├── index.html           # Fixed 4-step GUI
│       ├── app.js               # Frontend state + API calls
│       └── style.css
├── services/
│   ├── fal_client.py            # fal.ai adapter
│   ├── procedure_repository.py  # SQLite schema + repository
│   ├── asset_storage.py         # Procedure-scoped filesystem assets
│   └── media_processor.py       # Local image/video edits
├── pricing/
│   └── registry.py              # Pricing estimates by model
├── data/                        # SQLite database (created at runtime)
├── procedure_assets/            # Local media storage (created at runtime)
└── ARCHITECTURE.md
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create `.env`:

```bash
FAL_KEY=your_fal_key
```

## Run

```bash
python main.py
```

After you change **Python** code (`gui/`, `services/`, `pricing/`, etc.), stop the server (**Ctrl+C**) and start it again — or use auto-reload while developing:

```bash
python main.py --reload
```

**Frontend** (`gui/static/*.js`, `*.css`, `index.html`): save the file, then **hard-refresh** the browser (**Cmd+Shift+R** / **Ctrl+Shift+R**) so the tab doesn’t use an old cached script.

Then open:

- [http://127.0.0.1:5050](http://127.0.0.1:5050)

## How the new flow works

### Procedure lifecycle

- Create a procedure.
- Configure and run each step independently.
- Inspect outputs after each run.
- Rerun a step to create more variants.
- Archive or delete variants.
- Reopen any saved procedure later.

### Step 1 - Generate base image

- Choose image model + params.
- Estimate cost.
- Confirm.
- Run and store generated images locally.

### Step 2 - Modify images

- Import local images (skip steps 1/2 generation if needed).
- Basic transforms (in place, reversible):
  - horizontal flip
  - zoom
  - filter
- AI modify (prompt-based) creates duplicate variants.

### Step 3 - Generate video

- Choose video model + params.
- Optionally select a generated/imported image as source.
- Estimate -> confirm -> run.
- Generated videos are stored as local variants.

### Step 4 - Modify video

- Cut a video segment.
- Add first-second handheld shake (2%-4% jitter).
- Subtitles button exists as placeholder (not implemented yet).

## Cost safety

All model runs are blocked unless:

1. The user requested an estimate first.
2. The user confirmed that exact estimated amount.

This applies to step runs and AI image modification.

## API summary

Main endpoints (see `gui/app.py` for full contracts):

- `GET /api/models`
- `GET/POST/DELETE /api/procedures...`
- `POST /api/procedures/{id}/steps/{step}/estimate`
- `POST /api/procedures/{id}/steps/{step}/run`
- `GET /api/procedures/{id}/assets`
- `POST /api/procedures/{id}/assets/import-image`
- `POST /api/assets/{id}/image-transform`
- `POST /api/assets/{id}/image-ai-edit`
- `POST /api/assets/{id}/video-cut`
- `POST /api/assets/{id}/video-shake`

## Notes

- The architecture is GUI-first for users.
- Core Python services remain reusable for future interfaces or API deployments.
