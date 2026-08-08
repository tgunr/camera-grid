# Project: CameraGrid

UV-printed perforated mask for a camera array — artwork printed with a grid of
transparent holes so cameras can look through an otherwise-opaque printed surface.

**Repo location: `~/Camera Grid`** (moved from `/Volumes/projects/uv/Camera Grid` 2026-08-08).

## Quick Start

- Read `notes/brief.md` for current specs and design decisions
- Run `python3 ~/.hermes/skills/productivity/projects/scripts/projects.py show CameraGrid` for project state
- The perforated mask generator is at `scripts/perforated_mask.py`
- The lens-optics calculator (dual-regime: fine grid ND+grating, coarse vignetting) is at `scripts/lens_optics.py`
- The standalone GUI app is `output/CameraGrid.app` (double-click to launch; rebuild from `scripts/CameraGrid.spec` or `scripts/build_app.sh`)

## Workspace Layout

- `notes/` — project decisions, briefs, session notes
- `design/` — Affinity Designer files, exported artwork, PNG sources
- `toolpaths/` — CAM toolpaths (Vectric/Aspire) for CNC-cutting the substrate
- `output/` — finished G-code and production files
- `mask/` — UV-printer-ready perforated mask PNGs, calibration prints

## Linked Skills

- `perforated_mask.py` — hole grid generator (UV-printer DPI-aware, antialiased)
- `lens_optics.py` — dual-regime mask optics: fine-grid ND+grating (light loss, ghost offset) and coarse single-hole vignetting; `compute_fine_grid_optimum()` picks hole/pitch from lens criteria
- `mask_calculator.py` — CLI calculator (`--preset axis-p5655 --standoff 25.4`)

## Recent Sessions

```bash
python3 ~/.hermes/skills/productivity/projects/scripts/projects.py show CameraGrid
```
