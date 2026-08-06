#!/usr/bin/env python3
"""
perforated_mask.py — UV-printer perforated mask generator.

Punches a grid of antialiased transparent circular holes through a PNG.
All dimensions accept --mm or --inch unit flags that apply to subsequent
numeric arguments (sticky until the next unit flag).

UV printer DPI: 1440
  • Soft  warning when any feature < 0.30 mm (~17 px)
  • Hard  warning when any feature < 0.15 mm (~ 9 px)

Usage:
    python3 perforated_mask.py photo.png --mm --hole-size 3 --spacing 6

    python3 perforated_mask.py photo.png \\
        --inch --imgSizeX 6 --imgSizeY 4 \\
        --gridSizeX 4 --gridSizeY 4 \\
        --gridX 1 --gridY 1 \\
        --mm --hole-size 3 --spacing 6

    # Grid position defaults to image centre; grid size defaults to image size.
    python3 perforated_mask.py photo.png --mm --hole-size 2 --spacing 5 --out custom.png
"""

import os
import sys
from PIL import Image, ImageDraw

# ── Constants ───────────────────────────────────────────────────────────────
UV_DPI = 1440
MM_PER_INCH = 25.4
PX_PER_MM = UV_DPI / MM_PER_INCH   # ≈ 56.69
PX_PER_INCH = UV_DPI

SOFT_WARN_MM = 0.30
HARD_WARN_MM = 0.15

# ── Helpers ─────────────────────────────────────────────────────────────────

def to_px(value: float, unit: str) -> float:
    """Convert a dimension in the given unit to pixels at 1440 DPI."""
    if unit == "inch":
        return value * PX_PER_INCH
    if unit == "mm":
        return value * PX_PER_MM
    return float(value)


def draw_antialiased_hole(draw: ImageDraw.ImageDraw, cx: float, cy: float,
                          diameter_px: float, feather_px: float) -> None:
    """
    Draw a single antialiased hole directly onto an alpha channel.

    Order matters: feather rings from outside in first (opaque → nearly-opaque),
    then the hole centre (alpha=0) last so it overwrites the feather pixels
    inside the hole radius.
    """
    radius = diameter_px / 2.0
    outer_r = radius + feather_px

    steps = max(6, int(feather_px * 4))
    for step in range(steps - 1):
        # step=0 → outermost ring (most opaque, alpha≈255)
        # step=steps-1 → innermost feather ring (alpha≈38)
        t = (step + 1) / steps
        r_inner = outer_r - t * feather_px
        r_outer = outer_r - (step / steps) * feather_px
        alpha_val = int(255 * (1.0 - t * 0.85))
        bbox = [cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer]
        draw.ellipse(bbox, fill=alpha_val)

    # Solid hole centre — fully transparent (alpha 0), drawn last
    if radius > 0:
        bbox = [cx - radius, cy - radius, cx + radius, cy + radius]
        draw.ellipse(bbox, fill=0)


def check_dpi_warnings(values_px: dict, names: dict) -> None:
    soft_px = SOFT_WARN_MM * PX_PER_MM
    hard_px = HARD_WARN_MM * PX_PER_MM
    for key, px_val in sorted(values_px.items()):
        if px_val <= 0:
            continue
        label = names.get(key, key)
        mm_val = px_val / PX_PER_MM
        if px_val < hard_px:
            print(
                f"  ⚠️  HARD WARNING: {label} = {mm_val:.2f} mm "
                f"({px_val:.1f} px) — below 0.15 mm printer limit; "
                f"holes may not print cleanly."
            )
        elif px_val < soft_px:
            print(
                f"  ⚠️  SOFT WARNING: {label} = {mm_val:.2f} mm "
                f"({px_val:.1f} px) — approaching 0.30 mm resolution limit."
            )


# ── Argument parser (manual — sticky unit flags) ────────────────────────────

def print_help() -> None:
    print("""Usage: perforated_mask.py input.png [OPTIONS]

Punch a grid of antialiased transparent circular holes through a PNG for UV
flatbed printing.  Sticky unit flags (--mm / --inch) apply to every numeric
argument that follows them until the next unit flag.

UV printer DPI: 1440
  • Soft  warning when any feature < 0.30 mm (~17 px)
  • Hard  warning when any feature < 0.15 mm (~ 9 px)

Arguments:
  input.png              Input image path (PNG recommended; any format Pillow
                         accepts will be converted to RGBA).

Options:
  --mm                   Set millimeters as the unit for subsequent numeric
                         arguments.
  --inch                 Set inches as the unit for subsequent numeric
                         arguments.
  --imgSizeX SIZE        Resize image width to SIZE pixels or units (see
                         --mm / --inch).
  --imgSizeY SIZE        Resize image height to SIZE pixels or units.
  --gridSizeX SIZE       Grid area width  in pixels or units.
  --gridSizeY SIZE       Grid area height in pixels or units.
  --gridX OFFSET         Grid area origin offset from left edge in pixels or
                         units.  0 = image centre (default).
  --gridY OFFSET         Grid area origin offset from bottom edge in pixels or
                         units.  0 = image centre (default).
  --hole-size DIAMETER   Hole diameter in pixels or units (default: 8 px).
  --spacing  PITCH       Centre-to-centre spacing between holes in pixels or
                         units (default: 12 px).
  --feather   WIDTH      Antialiasing feather width in pixels or units
                         (default: max(2, hole-size * 0.12)).
  --margin    SIZE       Inset margin around the grid in pixels or units;
                         offsets grid origin and reduces grid size on all sides.
  --out      PATH        Output file path (default: auto-named beside input).
  --preview             Open the result in the default image viewer.
  --stagger             Offset alternate rows by half the spacing (hex-style).
  --help                Show this help message and exit.

Defaults:
  • Grid position: centred on image.
  • Grid size:    entire image.
  • Feather:      auto-scaled from hole size when omitted.

Examples:
    python3 perforated_mask.py photo.png --mm --hole-size 3 --spacing 6

    python3 perforated_mask.py photo.png \\
        --inch --imgSizeX 6 --imgSizeY 4 \\
        --gridSizeX 4 --gridSizeY 4 \\
        --gridX 1 --gridY 1 \\
        --mm --hole-size 3 --spacing 6

    # Grid position defaults to image centre; grid size defaults to image size.
    python3 perforated_mask.py photo.png --mm --hole-size 2 --spacing 5 --out custom.png
""")


def parse_args():
    argv = sys.argv[1:]
    unit = "px"
    result = {}

    i = 0
    while i < len(argv):
        tok = argv[i]

        if tok in ("--help", "-h"):
            print_help()
            sys.exit(0)

        if tok in ("--mm", "--inch"):
            unit = tok.lstrip("-")
            result["unit"] = unit
            i += 1
            continue

        if tok == "--preview":
            result["preview"] = True
            i += 1
            continue

        if tok == "--stagger":
            result["stagger"] = True
            i += 1
            continue

        if tok == "--out":
            i += 1
            if i < len(argv) and not argv[i].startswith("--"):
                result["out"] = argv[i]
            else:
                print("Error: --out requires a path value.", file=sys.stderr)
                sys.exit(1)
            i += 1
            continue

        numeric_flags = {
            "imgSizeX", "imgSizeY",
            "gridSizeX", "gridSizeY",
            "gridX", "gridY",
            "hole-size", "spacing", "feather", "margin",
        }
        key = tok.lstrip("-")
        if key in numeric_flags:
            i += 1
            if i >= len(argv) or argv[i].startswith("--"):
                print(f"Error: {tok} requires a numeric value.", file=sys.stderr)
                sys.exit(1)
            result[key] = (float(argv[i]), unit)
            i += 1
            continue

        # Positional: input file
        if not tok.startswith("-"):
            if "input" not in result:
                result["input"] = tok
            i += 1
            continue

        print(f"Warning: unrecognised flag {tok} — ignored.", file=sys.stderr)
        i += 1

    return result


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    raw = parse_args()

    if "input" not in raw:
        print("Usage: perforated_mask.py input.png [OPTIONS]", file=sys.stderr)
        print("  --mm / --inch   set unit for following dimensions", file=sys.stderr)
        sys.exit(1)

    input_path = raw["input"]
    if not os.path.isfile(input_path):
        print(f"Error: file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    def px(key, default=None):
        if key not in raw:
            return default
        val, unit = raw[key]
        return to_px(val, unit)

    img_size_x_px = px("imgSizeX")
    img_size_y_px = px("imgSizeY")
    grid_size_x_px = px("gridSizeX")
    grid_size_y_px = px("gridSizeY")
    grid_x_px = px("gridX", 0.0)
    grid_y_px = px("gridY", 0.0)
    hole_size_px = px("hole-size", 8.0)
    spacing_px    = px("spacing", 12.0)
    feather_px    = px("feather", max(2.0, hole_size_px * 0.12))
    margin_px     = px("margin", 0.0)

    preview   = raw.get("preview", False)
    stagger   = raw.get("stagger", False)
    out_path  = raw.get("out")

    # ── Load & optionally resize ────────────────────────────────────────────
    img = Image.open(input_path).convert("RGBA")
    orig_w, orig_h = img.size

    if img_size_x_px is not None or img_size_y_px is not None:
        new_w = int(img_size_x_px) if img_size_x_px is not None else orig_w
        new_h = int(img_size_y_px) if img_size_y_px is not None else orig_h
        img = img.resize((new_w, new_h), Image.LANCZOS)
        print(f"Resized to {new_w}×{new_h} px  "
              f"({new_w/PX_PER_INCH:.3f}\" × {new_h/PX_PER_INCH:.3f}\")")
    else:
        new_w, new_h = orig_w, orig_h
        print(f"Original size: {new_w}×{new_h} px  "
              f"({new_w/PX_PER_INCH:.3f}\" × {new_h/PX_PER_INCH:.3f}\")")

    # ── Grid geometry ───────────────────────────────────────────────────────
    gsx = grid_size_x_px if grid_size_x_px is not None else float(new_w)
    gsy = grid_size_y_px if grid_size_y_px is not None else float(new_h)

    # gridX/gridY reference from BOTTOM-LEFT; Pillow uses TOP-LEFT.
    # Zero → centre the grid.
    if grid_x_px == 0.0 and grid_y_px == 0.0:
        gx = (new_w - gsx) / 2.0
        gy = (new_h - gsy) / 2.0
    else:
        gx = grid_x_px
        gy = new_h - grid_y_px - gsy   # flip Y

    # Apply user-specified margin inset on all sides
    if margin_px > 0:
        gx += margin_px
        gy += margin_px
        gsx = max(0.0, gsx - 2.0 * margin_px)
        gsy = max(0.0, gsy - 2.0 * margin_px)

    # Hole centres inset by half a hole-diameter (no holes clip at grid edges)
    hole_margin = hole_size_px / 2.0
    first_cx = gx + hole_margin
    first_cy = gy + hole_margin
    last_cx  = gx + gsx - hole_margin
    last_cy  = gy + gsy - hole_margin

    if spacing_px <= 0:
        print("Error: spacing must be > 0.", file=sys.stderr)
        sys.exit(1)

    cols = max(1, int((last_cx - first_cx) / spacing_px) + 1)
    rows = max(1, int((last_cy - first_cy) / spacing_px) + 1)

    hole_mm = hole_size_px / PX_PER_MM
    hole_inch = hole_size_px / PX_PER_INCH
    spacing_mm = spacing_px / PX_PER_MM
    spacing_inch = spacing_px / PX_PER_INCH
    feather_mm = feather_px / PX_PER_MM
    feather_inch = feather_px / PX_PER_INCH
    margin_mm = margin_px / PX_PER_MM
    margin_inch = margin_px / PX_PER_INCH

    print(f"\nGrid: {cols} cols × {rows} rows")
    print(f"  Origin (top-left):  ({gx:.1f}, {gy:.1f}) px")
    print(f"  Grid size:          ({gsx:.1f}, {gsy:.1f}) px")
    print(f"  Hole Ø:             {hole_size_px:.1f} px  ({hole_mm:.3f} mm / {hole_inch:.4f}\")")
    print(f"  Spacing:            {spacing_px:.1f} px  ({spacing_mm:.3f} mm / {spacing_inch:.4f}\")")
    print(f"  Feather:            {feather_px:.1f} px  ({feather_mm:.3f} mm / {feather_inch:.4f}\")")
    print(f"  Margin:             {margin_px:.1f} px  ({margin_mm:.3f} mm / {margin_inch:.4f}\")")

    # ── DPI warnings ────────────────────────────────────────────────────────
    print("\n── DPI checks (1440 ppi UV printer) ──")
    check_dpi_warnings(
        {"hole": hole_size_px, "spacing": spacing_px, "feather": feather_px,
         "grid_w": gsx, "grid_h": gsy},
        {"hole": "Hole diameter", "spacing": "Hole spacing",
         "feather": "Feather width", "grid_w": "Grid width", "grid_h": "Grid height"},
    )

    # ── Punch holes ─────────────────────────────────────────────────────────
    out_img = img.copy()

    # Get a real independent alpha copy we can draw on
    alpha = out_img.split()[3].convert("L")   # .convert("L") forces a copy
    draw = ImageDraw.Draw(alpha)

    count = 0
    for row in range(rows):
        cy = first_cy + row * spacing_px
        if not (0 <= cy < new_h):
            continue
        row_offset = (spacing_px / 2.0) if (stagger and row % 2 == 1) else 0.0
        for col in range(cols):
            cx = first_cx + col * spacing_px + row_offset
            if not (0 <= cx < new_w):
                continue
            draw_antialiased_hole(draw, cx, cy, hole_size_px, feather_px)
            count += 1

    # Apply the modified alpha back to the image
    out_img.putalpha(alpha)

    print(f"\nPunched {count} antialiased holes "
          f"(Ø={hole_size_px:.1f} px, spacing={spacing_px:.1f} px, "
          f"feather={feather_px:.1f} px, stagger={'on' if stagger else 'off'})")

    # ── Smart output naming ─────────────────────────────────────────────────
    if out_path is None:
        base, ext = os.path.splitext(input_path)
        hs_val = raw.get("hole-size", (8.0, "px"))[0]
        sp_val = raw.get("spacing",    (12.0, "px"))[0]
        stg_val = "-stagger" if stagger else ""
        mrg_unit = raw.get("unit", "px")
        mrg_per_unit = margin_px / (PX_PER_MM if mrg_unit == "mm" else PX_PER_INCH)
        mrg_val = f"-m{mrg_per_unit:.2f}" if margin_px > 0 else ""
        if img_size_x_px is not None or img_size_y_px is not None:
            ix = int(img_size_x_px) if img_size_x_px is not None else orig_w
            iy = int(img_size_y_px) if img_size_y_px is not None else orig_h
            out_path = f"{base}-{ix}X{iy}-{hs_val}-{sp_val}{stg_val}{mrg_val}{ext}"
        else:
            out_path = f"{base}-{hs_val}-{sp_val}{stg_val}{mrg_val}{ext}"

    # Embed printer DPI metadata so external measurement tools can verify
    # physical hole size in mm / inches.
    out_img.save(out_path, dpi=(PX_PER_INCH, PX_PER_INCH))
    print(f"Saved: {out_path}  (embedded {int(PX_PER_INCH)}×{int(PX_PER_INCH)} ppi)")

    if preview:
        out_img.show()

    # Optional sidecar verification report for external measurements / QA
    measure_json = os.path.splitext(out_path)[0] + "-measure.json"
    report = _measure_output(out_img, hole_size_px, spacing_px, feather_px)
    with open(measure_json, "w", encoding="utf-8") as fh:
        import json
        json.dump(report, fh, indent=2)
    print(f"Measure report: {measure_json}")


def _measure_output(img, hole_diameter_px, spacing_px, feather_px):
    alpha = img.split()[-1].convert("L")
    w, h = img.size

    def hole_bounds(cx, cy, radius):
        x_min = max(0, int(cx - radius))
        x_max = min(w - 1, int(cx + radius))
        y_min = max(0, int(cy - radius))
        y_max = min(h - 1, int(cy + radius))
        return x_min, x_max, y_min, y_max

    first_cx = hole_diameter_px / 2.0
    first_cy = hole_diameter_px / 2.0
    holes = []
    for row in range(max(1, int((h - hole_diameter_px) / max(1.0, spacing_px)) + 1)):
        cy = first_cy + row * spacing_px
        if not (0 <= cy < h):
            continue
        for col in range(max(1, int((w - hole_diameter_px) / max(1.0, spacing_px)) + 1)):
            cx = first_cx + col * spacing_px
            if not (0 <= cx < w):
                continue
            x_min, x_max, y_min, y_max = hole_bounds(cx, cy, hole_diameter_px / 2.0)
            if x_max < x_min or y_max < y_min:
                continue
            zero_count = 0
            sample = 0
            xs = []
            ys = []
            for y in range(y_min, y_max + 1):
                for x in range(x_min, x_max + 1):
                    if alpha.getpixel((x, y)) == 0:
                        zero_count += 1
                        xs.append(x)
                        ys.append(y)
            if xs:
                holes.append({
                    "cx": cx,
                    "cy": cy,
                    "x_min": min(xs),
                    "x_max": max(xs),
                    "y_min": min(ys),
                    "y_max": max(ys),
                    "width_px": max(xs) - min(xs) + 1,
                    "height_px": max(ys) - min(ys) + 1,
                    "zero_px": zero_count,
                })

    summary = {
        "image_size_px": {"width": w, "height": h},
        "requested": {
            "hole_diameter_px": hole_diameter_px,
            "spacing_px": spacing_px,
            "feather_px": feather_px,
        },
        "measured_holes": holes[:12],
        "measured_count": len(holes),
    }
    if holes:
        widths = [h["width_px"] for h in holes]
        heights = [h["height_px"] for h in holes]
        summary["measurements_px"] = {
            "holes": len(holes),
            "width_min": min(widths),
            "width_max": max(widths),
            "height_min": min(heights),
            "height_max": max(heights),
        }
    return summary


if __name__ == "__main__":
    main()
