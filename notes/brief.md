# CameraGrid Brief

UV-printed perforated mask for a camera array: artwork printed with a grid of
transparent holes so cameras can see through an otherwise-opaque printed
surface.

## Current Status

- Repo exists at `/Volumes/projects/UV/Camera Grid`
- Active generator is `scripts/perforated_mask.py`
- This brief was added after `AGENTS.md` still referenced it while the file was missing

## Specs / Known Parameters

- UV printer target DPI: **1440**
- Soft resolution warning threshold: **0.30 mm** (~17 px)
- Hard resolution warning threshold: **0.15 mm** (~9 px)
- Hole punch shape: **antialiased circular**
- Feathering: **alpha-feathered hole edge**
- Default CLI-style behavior: centred grid, full-image grid unless otherwise specified

## Repo Structure

- `design/` — Affinity Designer files and exports
- `mask/` — UV-printer-ready perforated mask PNGs
- `output/` — finished G-code / production exports
- `scripts/perforated_mask.py` — main generator
- `scripts/perforated_mask_app.py` — interactive preview app

## Sample Assets Present

- `camera grid.png`
- `black grid.png`
- `test.png`
- `danger*.png`
- `Caution*.png`
- `Danger Grid.png`
- `image-2mm.png`
- `test-measure.json`

## Known Gaps / TODOs

- [ ] Recover or rewrite the original brief/spec decisions that used to live here
- [ ] Confirm final physical substrate size, material, and mounting method
- [ ] Confirm exact camera array geometry: hole count, spacing, and alignment targets
- [ ] Define print workflow: colour separation, white underbase, mask registration
- [ ] Validate CNC/UV print integration steps if substrate is machined then printed
