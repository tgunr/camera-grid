#!/usr/bin/env python3
"""
Perforated Mask Calculator for Camera Arrays

Given lens specs and mounting geometry, calculates:
  - Minimum hole diameter (no vignetting)
  - Minimum grid pitch (no cross-talk)
  - Valid hole size range for a given pitch
  - Effective f-number if hole clips the entrance pupil

Usage:
  python3 scripts/mask_calculator.py --help
  python3 scripts/mask_calculator.py --focal-length 25 --f-number 2.0 --sensor-diagonal 5.53 --standoff 25.4
  python3 scripts/mask_calculator.py --preset axis-p5655 --standoff 25.4
"""

import argparse
import math
import json
import sys

# ─── Preset cameras ───────────────────────────────────────────────────────────

PRESETS = {
    "axis-p5655": {
        "name": "AXIS P5655-E",
        "sensor_diagonal": 5.53,  # mm (1/2.8" format, back-calculated from FOV)
        "sensor_width": 4.80,     # mm
        "sensor_height": 2.75,    # mm
        "aspect": "16:9",
        "focal_lengths": [4.3, 10, 25, 50, 100, 137.6],  # mm
        "f_numbers": [1.4, 1.8, 2.0, 2.8, 3.5, 4.0],     # corresponding max apertures
        "hfov": [58.3, 25.0, 11.0, 5.5, 2.8, 2.4],        # degrees (approximate for midpoints)
    },
}


def calc_min_hole(focal_length, f_number, sensor_width, sensor_height, standoff, mask_thickness=0):
    """
    Calculate minimum hole diameter to avoid vignetting.

    Args:
        focal_length: mm
        f_number: f/# (e.g. 2.8 for f/2.8)
        sensor_width: mm
        sensor_height: mm
        standoff: mm (distance from entrance pupil to near side of mask)
        mask_thickness: mm (default 0 for thin mask)

    Returns:
        dict with minimum hole diameter and contributing terms
    """
    # Entrance pupil diameter
    d_ep = focal_length / f_number

    # Half field of view (horizontal)
    theta_h = math.atan(sensor_width / (2 * focal_length))

    # Cone spread at mask plane (near side + far side)
    total_distance = standoff + mask_thickness
    cone_spread = 2 * total_distance * math.tan(theta_h)

    # Minimum hole diameter
    d_min = d_ep + cone_spread

    return {
        "focal_length_mm": focal_length,
        "f_number": f_number,
        "entrance_pupil_mm": round(d_ep, 2),
        "hfov_degrees": round(math.degrees(theta_h) * 2, 2),
        "half_angle_degrees": round(math.degrees(theta_h), 2),
        "standoff_mm": standoff,
        "mask_thickness_mm": mask_thickness,
        "cone_spread_mm": round(cone_spread, 2),
        "min_hole_mm": round(d_min, 2),
        "min_hole_inches": round(d_min / 25.4, 3),
    }


def calc_grid_pitch(focal_length, f_number, sensor_width, standoff, mask_thickness=0):
    """
    Calculate minimum grid pitch to avoid cross-talk between adjacent cameras.

    Returns:
        dict with minimum pitch and valid hole range
    """
    d_ep = focal_length / f_number
    theta_h = math.atan(sensor_width / (2 * focal_length))
    total_distance = standoff + mask_thickness
    cone_spread = 2 * total_distance * math.tan(theta_h)

    # Minimum pitch: hole lower bound must ≤ hole upper bound
    # d_min = D_EP + cone_spread
    # d_max = 2*P - D_EP - cone_spread
    # For d_min ≤ d_max: P ≥ D_EP + cone_spread
    min_pitch = d_ep + cone_spread

    # If pitch is given, the valid hole range is [d_min, d_max]
    # d_max = 2*P - D_EP - cone_spread
    # But we return min_pitch here; the caller can compute d_max for a given pitch

    return {
        "min_pitch_mm": round(min_pitch, 2),
        "min_pitch_inches": round(min_pitch / 25.4, 3),
    }


def calc_hole_range(pitch, focal_length, f_number, sensor_width, standoff, mask_thickness=0):
    """
    Given a grid pitch, calculate the valid hole diameter range.

    Returns:
        dict with min and max hole diameters
    """
    d_ep = focal_length / f_number
    theta_h = math.atan(sensor_width / (2 * focal_length))
    total_distance = standoff + mask_thickness
    cone_spread = 2 * total_distance * math.tan(theta_h)

    d_min = d_ep + cone_spread
    d_max = 2 * pitch - d_ep - cone_spread

    return {
        "min_hole_mm": round(d_min, 2),
        "min_hole_inches": round(d_min / 25.4, 3),
        "max_hole_mm": round(d_max, 2),
        "max_hole_inches": round(d_max / 25.4, 3),
        "valid": d_min <= d_max,
        "pitch_mm": pitch,
    }


def calc_effective_fstop(focal_length, hole_diameter):
    """
    If the hole is smaller than the entrance pupil, it becomes the effective stop.
    Calculate the effective f-number.
    """
    if hole_diameter <= 0:
        return None
    d_ep = focal_length
    # Effective f-number = focal_length / hole_diameter
    # (This is the f-number if the hole were the aperture stop)
    effective_f = focal_length / hole_diameter
    return round(effective_f, 2)


def analyze_camera(focal_length, f_number, sensor_width, sensor_height, standoff, mask_thickness=0, pitch=None):
    """
    Full analysis for a single camera/mask configuration.
    """
    result = calc_min_hole(focal_length, f_number, sensor_width, sensor_height, standoff, mask_thickness)

    # Grid pitch analysis
    pitch_result = calc_grid_pitch(focal_length, f_number, sensor_width, standoff, mask_thickness)
    result["min_pitch_mm"] = pitch_result["min_pitch_mm"]
    result["min_pitch_inches"] = pitch_result["min_pitch_inches"]

    # If pitch is specified, calculate valid hole range
    if pitch is not None:
        range_result = calc_hole_range(pitch, focal_length, f_number, sensor_width, standoff, mask_thickness)
        result["pitch_mm"] = pitch
        result["hole_range_mm"] = (range_result["min_hole_mm"], range_result["max_hole_mm"])
        result["hole_range_inches"] = (range_result["min_hole_inches"], range_result["max_hole_inches"])
        result["hole_range_valid"] = range_result["valid"]

    # Effective f-number if hole clips entrance pupil
    d_ep = focal_length / f_number
    if result["min_hole_mm"] < d_ep:
        result["effective_fstop_at_min_hole"] = calc_effective_fstop(focal_length, result["min_hole_mm"])

    return result


def analyze_preset(preset_name, standoff, mask_thickness=0, pitch=None):
    """
    Analyze a preset camera across its full zoom range.
    """
    if preset_name not in PRESETS:
        print(f"Unknown preset: {preset_name}")
        print(f"Available presets: {', '.join(PRESETS.keys())}")
        sys.exit(1)

    preset = PRESETS[preset_name]
    results = []

    for i, f in enumerate(preset["focal_lengths"]):
        f_num = preset["f_numbers"][i] if i < len(preset["f_numbers"]) else preset["f_numbers"][-1]
        result = analyze_camera(
            focal_length=f,
            f_number=f_num,
            sensor_width=preset["sensor_width"],
            sensor_height=preset["sensor_height"],
            standoff=standoff,
            mask_thickness=mask_thickness,
            pitch=pitch,
        )
        result["zoom_label"] = f"{f}mm"
        results.append(result)

    return {
        "preset": preset["name"],
        "sensor_diagonal_mm": preset["sensor_diagonal"],
        "sensor_width_mm": preset["sensor_width"],
        "sensor_height_mm": preset["sensor_height"],
        "standoff_mm": standoff,
        "standoff_inches": round(standoff / 25.4, 3),
        "mask_thickness_mm": mask_thickness,
        "results": results,
    }


def print_analysis(analysis):
    """Pretty-print the analysis results."""
    print(f"\n{'='*70}")
    print(f"  Perforated Mask Calculator — {analysis['preset']}")
    print(f"{'='*70}")
    print(f"  Sensor: {analysis['sensor_width_mm']} × {analysis['sensor_height_mm']} mm "
          f"(diagonal {analysis['sensor_diagonal_mm']} mm)")
    print(f"  Standoff: {analysis['standoff_mm']} mm ({analysis['standoff_inches']}\")")
    if analysis['mask_thickness_mm'] > 0:
        print(f"  Mask thickness: {analysis['mask_thickness_mm']} mm")
    print()

    # Table header
    print(f"  {'Zoom':>8} {'f/#':>5} {'D_EP':>7} {'HFOV':>7} {'Cone':>7} {'Min Hole':>10} {'Min Pitch':>10}")
    print(f"  {'':>8} {'':>5} {'(mm)':>7} {'(deg)':>7} {'(mm)':>7} {'mm':>5} {'in':>5} {'mm':>5} {'in':>5}")
    print(f"  {'-'*8} {'-'*5} {'-'*7} {'-'*7} {'-'*7} {'-'*5} {'-'*5} {'-'*5} {'-'*5}")

    worst_hole = 0
    worst_pitch = 0

    for r in analysis["results"]:
        print(f"  {r['zoom_label']:>8} f/{r['f_number']:<4} "
              f"{r['entrance_pupil_mm']:>6.1f} "
              f"{r['hfov_degrees']:>6.1f}° "
              f"{r['cone_spread_mm']:>6.1f} "
              f"{r['min_hole_mm']:>5.1f} "
              f"{r['min_hole_inches']:>5.2f} "
              f"{r['min_pitch_mm']:>5.1f} "
              f"{r['min_pitch_inches']:>5.2f}")

        worst_hole = max(worst_hole, r["min_hole_mm"])
        worst_pitch = max(worst_pitch, r["min_pitch_mm"])

    print(f"  {'-'*8} {'-'*5} {'-'*7} {'-'*7} {'-'*7} {'-'*5} {'-'*5} {'-'*5} {'-'*5}")
    print()
    print(f"  ► Worst-case minimum hole (any zoom):  {worst_hole:.1f} mm ({worst_hole/25.4:.2f}\")")
    print(f"  ► Worst-case minimum grid pitch:       {worst_pitch:.1f} mm ({worst_pitch/25.4:.2f}\")")

    # Hole range if pitch specified
    if "hole_range_mm" in analysis["results"][0]:
        print()
        print(f"  Valid hole ranges for pitch = {analysis['results'][0]['pitch_mm']} mm:")
        for r in analysis["results"]:
            valid = "✓" if r.get("hole_range_valid", False) else "✗ NO SOLUTION"
            print(f"    {r['zoom_label']:>8}: {r['hole_range_mm'][0]:.1f} – {r['hole_range_mm'][1]:.1f} mm  "
                  f"({r['hole_range_inches'][0]:.2f} – {r['hole_range_inches'][1]:.2f}\")  {valid}")

    print()


def main():
    parser = argparse.ArgumentParser(
        description="Perforated mask calculator for camera arrays",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # AXIS P5655-E at 1" standoff
  python3 scripts/mask_calculator.py --preset axis-p5655 --standoff 25.4

  # Custom lens: 50mm f/2.8, 1/2.3" sensor (6.17mm wide), 10mm standoff
  python3 scripts/mask_calculator.py --focal-length 50 --f-number 2.8 --sensor-width 6.17 --standoff 10

  # With mask thickness and grid pitch
  python3 scripts/mask_calculator.py --preset axis-p5655 --standoff 25.4 --mask-thickness 1 --pitch 40

  # JSON output
  python3 scripts/mask_calculator.py --preset axis-p5655 --standoff 25.4 --json
        """
    )

    parser.add_argument("--preset", type=str, help="Camera preset name (e.g. axis-p5655)")
    parser.add_argument("--focal-length", type=float, help="Focal length in mm")
    parser.add_argument("--f-number", type=float, help="F-number (e.g. 2.8 for f/2.8)")
    parser.add_argument("--sensor-diagonal", type=float, help="Sensor diagonal in mm")
    parser.add_argument("--sensor-width", type=float, help="Sensor width in mm")
    parser.add_argument("--sensor-height", type=float, help="Sensor height in mm")
    parser.add_argument("--standoff", type=float, required=True, help="Standoff distance in mm (entrance pupil to mask)")
    parser.add_argument("--mask-thickness", type=float, default=0, help="Mask substrate thickness in mm (default: 0)")
    parser.add_argument("--pitch", type=float, help="Grid pitch in mm (calculates valid hole range)")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of table")
    parser.add_argument("--list-presets", action="store_true", help="List available camera presets")

    args = parser.parse_args()

    if args.list_presets:
        print("Available camera presets:")
        for name, preset in PRESETS.items():
            print(f"  {name}: {preset['name']} — {preset['sensor_width']}×{preset['sensor_height']}mm sensor, "
                  f"focal lengths {preset['focal_lengths']}")
        sys.exit(0)

    if args.preset:
        analysis = analyze_preset(args.preset, args.standoff, args.mask_thickness, args.pitch)
        if args.json:
            print(json.dumps(analysis, indent=2))
        else:
            print_analysis(analysis)
    elif args.focal_length and args.f_number and args.sensor_width:
        result = analyze_camera(
            focal_length=args.focal_length,
            f_number=args.f_number,
            sensor_width=args.sensor_width,
            sensor_height=args.sensor_height or args.sensor_width * 9/16,
            standoff=args.standoff,
            mask_thickness=args.mask_thickness,
            pitch=args.pitch,
        )
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"\n  Focal length: {result['focal_length_mm']}mm, f/{result['f_number']}")
            print(f"  Entrance pupil: {result['entrance_pupil_mm']}mm")
            print(f"  HFOV: {result['hfov_degrees']}°")
            print(f"  Cone spread at mask: {result['cone_spread_mm']}mm")
            print(f"  Minimum hole: {result['min_hole_mm']}mm ({result['min_hole_inches']}\")")
            print(f"  Minimum pitch: {result['min_pitch_mm']}mm ({result['min_pitch_inches']}\")")
            if args.pitch and "hole_range_mm" in result:
                valid = "✓" if result["hole_range_valid"] else "✗ NO SOLUTION"
                print(f"  Valid hole range at pitch {args.pitch}mm: "
                      f"{result['hole_range_mm'][0]}–{result['hole_range_mm'][1]}mm  {valid}")
            print()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
