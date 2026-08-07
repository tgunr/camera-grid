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

## Running the GUI App (macOS)

The interactive editor `scripts/perforated_mask_app.py` must be run with a
Python that has **both tkinter and Pillow**. On this Mac the Homebrew Python
3.13 in `.venv/` has neither (`_tkinter` missing, Pillow not installed), and
installing `python-tk@3.13` requires the Xcode Command Line Tools which are
not installed.

Anaconda's Python 3.12.4 has everything (tkinter 8.6 + Pillow 10.3.0):

```bash
/opt/anaconda3/bin/python scripts/perforated_mask_app.py
```

To produce a physical-size output (e.g. 6 × 4 inch) in the app, set
**Image Width = 6** and **Image Height = 4** (in inch mode) before saving —
leaving them at 0 keeps the source pixels and yields a sub-inch file.

Verified 2026-08-06: `output/Caution 6X4-6X4-0.258-0.455-stagger-m0.80.png`
is 8640 × 5760 px = 6.0000 × 4.0000 inches at 1440 DPI.

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
