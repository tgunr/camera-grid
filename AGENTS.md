# Project: CameraGrid

UV-printed perforated mask for a camera array — artwork printed with a grid of
transparent holes so cameras can look through an otherwise-opaque printed surface.

## Quick Start

- Read `notes/brief.md` for current specs and design decisions
- Run `python3 ~/.hermes/skills/productivity/projects/scripts/projects.py show CameraGrid` for project state
- The perforated mask generator is at `scripts/perforated_mask.py`

## Workspace Layout

- `notes/` — project decisions, briefs, session notes
- `design/` — Affinity Designer files, exported artwork, PNG sources
- `toolpaths/` — CAM toolpaths (Vectric/Aspire) for CNC-cutting the substrate
- `output/` — finished G-code and production files
- `mask/` — UV-printer-ready perforated mask PNGs, calibration prints

## Linked Skills

- `perforated_mask.py` — hole grid generator (UV-printer DPI-aware, antialiased)

## Recent Sessions

```bash
python3 ~/.hermes/skills/productivity/projects/scripts/projects.py show CameraGrid
```
