#!/usr/bin/env python3
"""
lens_optics.py — Dual-regime optics model for perforated masks.

Two regimes:
  Fine grid  (pitch << D_EP): mask is an ND filter + diffraction grating.
    - Light loss = open-area fraction
    - Resolution loss = grating ghost offset f*λ/p, intensity ~ few %
    - Standoff is irrelevant (many holes contribute)
  Coarse grid (pitch ≥ D_EP): each lens looks through one hole.
    - Must satisfy vignetting: d >= D_EP + 2*(S+T)*tan(θ)
    - No ghosting (single aperture)

Optimum in the fine-grid regime maximises open area under:
  wall = p - d >= wall_min   (printability)
  pitch <= D_EP_min / k_fine  (remain fine, k_fine≈3)
  ghost offset >= ghost_min_px (keep ghosts separated)

References:
  - AXIS P5655-E prototype: 0.3mm holes, 0.575mm pitch, 4" standoff,
    100-yard subject → tele ~137.6mm, observed 2.2 stops / 53px ghosts.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

LAMBDA_MM = 0.55e-3  # green light
DEFAULT_WALL_MIN_MM = 0.30
DEFAULT_GHOST_MIN_PX = 20
FINE_GRID_K = 3.0  # pitch <= D_EP / K  → fine regime


@dataclass
class FineGridResult:
    hole_mm: float
    pitch_mm: float
    wall_mm: float
    open_area: float          # 0..1
    light_loss_stops: float
    ghost_offset_px: float    # at tele focal length
    regime: str               # "fine"
    notes: str


@dataclass
class CoarseGridResult:
    min_hole_mm: float
    min_pitch_mm: float
    regime: str               # "coarse"
    notes: str


# ── Presets ─────────────────────────────────────────────────────────────────

PRESETS: dict[str, dict] = {
    "axis-p5655": {
        "name": "AXIS P5655-E",
        "sensor_width_mm": 4.80,
        "sensor_height_mm": 2.75,
        "sensor_diagonal_mm": 5.53,
        "resolution_w": 1920,
        "resolution_h": 1080,
        "focal_lengths_mm": [4.3, 10, 25, 50, 100, 137.6],
        "f_numbers": [1.4, 1.8, 2.0, 2.8, 3.5, 4.0],
    },
}


def pixel_pitch_mm(sensor_width_mm: float, resolution_w: int = 1920) -> float:
    return sensor_width_mm / resolution_w


def entrance_pupil_mm(focal_mm: float, f_number: float) -> float:
    return focal_mm / f_number


def open_area_square(hole_mm: float, pitch_mm: float) -> float:
    if pitch_mm <= 0:
        return 0.0
    return (math.pi / 4.0) * (hole_mm / pitch_mm) ** 2


def open_area_hex(hole_mm: float, pitch_mm: float) -> float:
    """Hex/staggered grid: denser packing."""
    if pitch_mm <= 0:
        return 0.0
    return (math.pi / (2.0 * math.sqrt(3.0))) * (hole_mm / pitch_mm) ** 2


def light_loss_stops(open_area: float) -> float:
    if open_area <= 0:
        return float("inf")
    if open_area >= 1:
        return 0.0
    return -math.log2(open_area)


def ghost_offset_mm(focal_mm: float, pitch_mm: float, lambda_mm: float = LAMBDA_MM) -> float:
    """First-order grating ghost offset at focal plane (mm)."""
    if pitch_mm <= 0:
        return float("inf")
    return focal_mm * lambda_mm / pitch_mm


def ghost_offset_px(
    focal_mm: float,
    pitch_mm: float,
    pixel_pitch: float,
    lambda_mm: float = LAMBDA_MM,
) -> float:
    off_mm = ghost_offset_mm(focal_mm, pitch_mm, lambda_mm)
    if pixel_pitch <= 0:
        return float("inf")
    return off_mm / pixel_pitch


def cone_spread_mm(standoff_mm: float, mask_thickness_mm: float, half_angle_rad: float) -> float:
    return 2.0 * (standoff_mm + mask_thickness_mm) * math.tan(half_angle_rad)


def coarse_min_hole_mm(
    focal_mm: float,
    f_number: float,
    sensor_width_mm: float,
    standoff_mm: float,
    mask_thickness_mm: float = 0.0,
) -> float:
    d_ep = entrance_pupil_mm(focal_mm, f_number)
    theta = math.atan(sensor_width_mm / (2.0 * focal_mm))
    return d_ep + cone_spread_mm(standoff_mm, mask_thickness_mm, theta)


# ── Fine-grid optimum ────────────────────────────────────────────────────────

def compute_fine_grid_optimum(
    focal_lengths_mm: list[float],
    f_numbers: list[float],
    sensor_width_mm: float,
    resolution_w: int = 1920,
    wall_min_mm: float = DEFAULT_WALL_MIN_MM,
    ghost_min_px: float = DEFAULT_GHOST_MIN_PX,
    lambda_mm: float = LAMBDA_MM,
    stagger: bool = False,
) -> FineGridResult:
    """
    Pick the largest pitch (hence largest hole = pitch - wall) that keeps the
    mask in the fine-grid regime and keeps ghosts separated.

    Constraints:
      p <= D_EP_min / K               (fine-grid)
      p <= f_max*λ / (ghost_min * px) (ghost separation, evaluated at tele)
    Optimum is at p_opt = min(those bounds), d_opt = p_opt - wall_min.
    """
    if not focal_lengths_mm or not f_numbers:
        raise ValueError("focal_lengths and f_numbers required")
    if len(f_numbers) == 1 and len(focal_lengths_mm) > 1:
        f_numbers = f_numbers * len(focal_lengths_mm)
    if len(f_numbers) != len(focal_lengths_mm):
        raise ValueError("focal_lengths and f_numbers length mismatch")

    px = pixel_pitch_mm(sensor_width_mm, resolution_w)

    # Fine-grid bound: smallest entrance pupil governs
    d_eps = [entrance_pupil_mm(f, fn) for f, fn in zip(focal_lengths_mm, f_numbers)]
    d_ep_min = min(d_eps)
    p_fine = d_ep_min / FINE_GRID_K

    # Ghost bound: largest focal length governs (worst-case ghost)
    f_max = max(focal_lengths_mm)
    # p <= f*λ / (ghost_min * px)
    if ghost_min_px > 0 and px > 0:
        p_ghost = f_max * lambda_mm / (ghost_min_px * px)
    else:
        p_ghost = float("inf")

    p_opt = min(p_fine, p_ghost)

    # Enforce wall feasibility: need p > wall
    if p_opt <= wall_min_mm:
        # Wall too large for any feasible pitch — fall back to smallest viable
        # Still report; caller can warn.
        p_opt = wall_min_mm + 0.05  # minimal feasible
        notes = (
            f"wall_min {wall_min_mm}mm exceeds feasible pitch; "
            f"fine-grid bound {p_fine:.2f}mm ghost bound {p_ghost:.2f}mm. "
            f"Increase ghost tolerance or reduce wall_min."
        )
    else:
        notes = (
            f"fine-grid bound {p_fine:.2f}mm (D_EP_min {d_ep_min:.2f}mm/{FINE_GRID_K}), "
            f"ghost bound {p_ghost:.2f}mm (f_max {f_max}mm, ghost_min {ghost_min_px}px). "
            f"Optimum at min bound."
        )

    d_opt = p_opt - wall_min_mm
    # Clamp hole to positive
    if d_opt < 0.05:
        d_opt = 0.05

    oa_fn = open_area_hex if stagger else open_area_square
    oa = oa_fn(d_opt, p_opt)
    ll = light_loss_stops(oa)
    ghost_px = ghost_offset_px(f_max, p_opt, px, lambda_mm)

    return FineGridResult(
        hole_mm=round(d_opt, 4),
        pitch_mm=round(p_opt, 4),
        wall_mm=round(wall_min_mm, 4),
        open_area=round(oa, 4),
        light_loss_stops=round(ll, 2),
        ghost_offset_px=round(ghost_px, 1),
        regime="fine",
        notes=notes,
    )


def compute_single_fine_optimum(
    focal_mm: float,
    f_number: float,
    sensor_width_mm: float,
    resolution_w: int = 1920,
    wall_min_mm: float = DEFAULT_WALL_MIN_MM,
    ghost_min_px: float = DEFAULT_GHOST_MIN_PX,
    lambda_mm: float = LAMBDA_MM,
    stagger: bool = False,
) -> FineGridResult:
    return compute_fine_grid_optimum(
        [focal_mm], [f_number], sensor_width_mm, resolution_w,
        wall_min_mm, ghost_min_px, lambda_mm, stagger,
    )


def evaluate_fine_grid(
    hole_mm: float,
    pitch_mm: float,
    focal_mm: float,
    sensor_width_mm: float,
    resolution_w: int = 1920,
    stagger: bool = False,
) -> dict:
    """Evaluate a given hole/pitch against fine-grid metrics."""
    px = pixel_pitch_mm(sensor_width_mm, resolution_w)
    oa_fn = open_area_hex if stagger else open_area_square
    oa = oa_fn(hole_mm, pitch_mm)
    return {
        "open_area": oa,
        "light_loss_stops": light_loss_stops(oa),
        "ghost_offset_px": ghost_offset_px(focal_mm, pitch_mm, px),
        "ghost_offset_mm": ghost_offset_mm(focal_mm, pitch_mm),
        "wall_mm": pitch_mm - hole_mm,
    }
