#!/usr/bin/env python3
"""
perforated_mask_app.py — Interactive hole-grid editor.

Tkinter-based preview app that wraps the same punch logic as the CLI.
Defaults are intentionally aligned with the CLI generator and the
CameraGrid UV-print specs.
"""

import os
import sys
from tkinter import (
    Tk,
    Frame,
    Label,
    Button,
    Scale,
    Entry,
    Checkbutton,
    OptionMenu,
    StringVar,
    DoubleVar,
    BooleanVar,
    filedialog,
    messagebox,
    TclError,
)
from PIL import Image, ImageDraw, ImageTk

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)


def resource_path(rel: str) -> str:
    """Resolve a bundled resource (PyInstaller _MEIPASS) or a repo-relative file."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        candidate = os.path.join(sys._MEIPASS, rel)
        if os.path.isfile(candidate):
            return candidate
    candidate = os.path.join(SCRIPT_DIR, rel)
    if os.path.isfile(candidate):
        return candidate
    return os.path.join(os.path.dirname(SCRIPT_DIR), rel)


try:
    from perforated_mask import (
        to_px,
        draw_antialiased_hole,
        UV_DPI,
        PX_PER_MM,
        PX_PER_INCH,
    )
except ImportError:
    print("Run this from the repo so 'perforated_mask.py' can be imported.",
          file=sys.stderr)
    sys.exit(1)


# ── Helpers ──────────────────────────────────────────────────────────────────

DEFAULT_HOLE_SIZE_MM = 0.25
DEFAULT_SPACING_MM = 0.4
DEFAULT_FEATHER_MM = 0.005
DEFAULT_MARGIN_MM = 0.5


def current_px_per_unit(unit: str) -> float:
    return PX_PER_MM if unit == "mm" else PX_PER_INCH


def convert_value(value: float, from_unit: str, to_unit: str) -> float:
    """Convert a value between units via pixels as intermediate."""
    if from_unit == to_unit:
        return value
    px_val = to_px(value, from_unit)
    if to_unit == "mm":
        return px_val / PX_PER_MM
    elif to_unit == "inch":
        return px_val / PX_PER_INCH
    elif to_unit == "px":
        return px_val
    return value


# ── Punch logic ──────────────────────────────────────────────────────────────


def punch_holes(
    img: "Image.Image",
    unit: str,
    img_w: "float | None" = None,
    img_h: "float | None" = None,
    grid_w: "float | None" = None,
    grid_h: "float | None" = None,
    grid_x: float = 0.0,
    grid_y: float = 0.0,
    hole_diam: float = DEFAULT_HOLE_SIZE_MM,
    spacing: float = DEFAULT_SPACING_MM,
    feather: float = DEFAULT_FEATHER_MM,
    stagger: bool = False,
    margin: float = DEFAULT_MARGIN_MM,
) -> "Image.Image":
    out = img.copy()
    work = out.convert("RGBA")
    w, h = work.size

    img_w_px = None if img_w is None else to_px(img_w, unit)
    img_h_px = None if img_h is None else to_px(img_h, unit)
    if img_w_px is not None or img_h_px is not None:
        nw = int(img_w_px) if img_w_px is not None else w
        nh = int(img_h_px) if img_h_px is not None else h
        work = work.resize((nw, nh), Image.LANCZOS)
        w, h = work.size

    gsx = to_px(grid_w, unit) if grid_w is not None else float(w)
    gsy = to_px(grid_h, unit) if grid_h is not None else float(h)

    gx = to_px(grid_x, unit)
    gy = to_px(grid_y, unit)

    if gx == 0.0 and gy == 0.0:
        gx = (w - gsx) / 2.0
        gy = (h - gsy) / 2.0
    else:
        gy = h - gy - gsy

    # Apply margin inset on all sides after positioning
    margin_px = to_px(margin, unit)
    if margin_px > 0:
        gx += margin_px
        gy += margin_px
        gsx = max(0.0, gsx - 2.0 * margin_px)
        gsy = max(0.0, gsy - 2.0 * margin_px)

    diameter = to_px(hole_diam, unit)
    pitch = to_px(spacing, unit)
    feather_px = to_px(feather, unit)

    if pitch <= 0:
        raise ValueError("Spacing must be greater than 0.")

    margin = diameter / 2.0
    first_cx = gx + margin
    first_cy = gy + margin
    last_cx = gx + gsx - margin
    last_cy = gy + gsy - margin

    cols = max(1, int((last_cx - first_cx) / pitch) + 1)
    rows = max(1, int((last_cy - first_cy) / pitch) + 1)

    alpha = work.split()[3].convert("L")
    draw = ImageDraw.Draw(alpha)

    for row in range(rows):
        cy = first_cy + row * pitch
        if not (0 <= cy < h):
            continue
        row_offset = (pitch / 2.0) if (stagger and row % 2 == 1) else 0.0
        for col in range(cols):
            cx = first_cx + col * pitch + row_offset
            if not (0 <= cx < w):
                continue
            draw_antialiased_hole(draw, cx, cy, diameter, feather_px)

    work.putalpha(alpha)
    return work


# ── Tkinter app ──────────────────────────────────────────────────────────────


class MaskApp:
    def __init__(self, root: Tk) -> None:
        self.root = root
        root.title("CameraGrid Mask Editor")
        root.minsize(860, 620)

        self.unit = StringVar(value="mm")
        self.out_format = StringVar(value="auto")

        self.src_img: "Image.Image | None" = None
        self.display_img: "Image.Image | None" = None
        self.tk_img: "ImageTk.PhotoImage | None" = None

        # Image size controls follow the current unit so users can type
        # "6" / "4" in inches (or 152.4 / 101.6 in mm) and get the right
        # physical print size at 1440 DPI. 0 = use the source image size.
        self.img_w_var = DoubleVar(value=0.0)
        self.img_h_var = DoubleVar(value=0.0)
        self.grid_w_var = DoubleVar(value=0.0)
        self.grid_h_var = DoubleVar(value=0.0)
        self.grid_x_var = DoubleVar(value=0.0)
        self.grid_y_var = DoubleVar(value=0.0)
        self.hole_var = DoubleVar(value=DEFAULT_HOLE_SIZE_MM)
        self.spacing_var = DoubleVar(value=DEFAULT_SPACING_MM)
        self.feather_var = DoubleVar(value=DEFAULT_FEATHER_MM)
        self.stagger_var = BooleanVar(value=False)
        self.margin_var = DoubleVar(value=DEFAULT_MARGIN_MM)
        self.step_var = DoubleVar(value=0.01)

        self.prev_unit = self.unit.get()
        self._converting = False
        self._suppress_refresh = 0
        self._last_changed: "str | None" = None
        self.scales: list[Scale] = []
        self._img_size_widgets: list[Scale] = []
        self._img_size_hint: "Label | None" = None

        self.canvas_size = 640
        self._build_ui()
        self._bind_vars()
        self._pick_default_input()

    @staticmethod
    def _unit_suffix(unit: str) -> str:
        return {"inch": "in", "mm": "mm", "px": "px"}.get(unit, unit)

    @staticmethod
    def _format_param(value: float) -> str:
        text = f"{value:.3f}".rstrip("0").rstrip(".")
        return text or "0"

    @staticmethod
    def _format_param_float(value: float) -> float:
        text = f"{value:.3f}".rstrip("0").rstrip(".")
        return 0.0 if text == "" else float(text)

    def _add_scale(self, parent: Frame, label: str, var, frm: float, to: float, res: float, row: int) -> None:
        Label(parent, text=label, anchor="w").grid(row=row, column=0, sticky="w", padx=6, pady=3)
        sc = Scale(parent, variable=var, from_=frm, to=to, resolution=res,
                   orient="horizontal", length=220)
        sc.grid(row=row, column=1, sticky="ew", padx=6, pady=3)
        self.scales.append(sc)

        entry = Entry(parent, width=8, justify="right")
        entry.grid(row=row, column=2, padx=6, pady=3)
        entry.insert(0, str(var.get()))

        def sync_entry_to_var():
            if entry.focus_get() != entry:
                entry.delete(0, "end")
                entry.insert(0, str(var.get()))

        def on_edit_finish(_=None):
            val_str = entry.get().strip()
            if not val_str:
                var.set(frm)
                return
            try:
                val = float(val_str)
                val = max(frm, min(to, val))
                var.set(val)
            except (ValueError, TclError):
                sync_entry_to_var()

        entry.bind("<Return>", on_edit_finish)
        entry.bind("<FocusOut>", on_edit_finish)
        var.trace_add("write", lambda *_: sync_entry_to_var())
        parent.grid_columnconfigure(1, weight=1)

    def _build_ui(self) -> None:
        left = Frame(self.root, padx=10, pady=10)
        left.pack(side="left", fill="y")

        right = Frame(self.root, padx=10, pady=10)
        right.pack(side="right", expand=True, fill="both")

        ctrl = Frame(left)
        ctrl.pack(fill="x", pady=(0, 8))

        Button(ctrl, text="Open Image", command=self.open_image).pack(side="left", padx=4, pady=4)
        Button(ctrl, text="Save Result", command=self.save_result).pack(side="left", padx=4, pady=4)
        Button(ctrl, text="Save for EufyMaker", command=self.save_eufymaker).pack(side="left", padx=4, pady=4)
        Button(ctrl, text="Reset", command=self.reset_values).pack(side="left", padx=4, pady=4)

        OptionMenu(ctrl, self.unit, "mm", "inch", "px").pack(side="left", padx=8, pady=4)
        Label(ctrl, text="Unit:").pack(side="left", padx=4, pady=4)

        Label(ctrl, text="Step:").pack(side="left", padx=(12, 4), pady=4)
        OptionMenu(ctrl, self.step_var, "0.001", "0.010", "0.100").pack(side="left", padx=4, pady=4)

        OptionMenu(ctrl, self.out_format, "auto", "PNG", "same").pack(side="right", padx=8, pady=4)
        Label(ctrl, text="Save As:").pack(side="right", padx=4, pady=4)

        sliders = Frame(left)
        sliders.pack(fill="y")

        self._add_scale(sliders, "Hole Size", self.hole_var, 0.1, 1.0, 0.1, 0)
        self._add_scale(sliders, "Spacing", self.spacing_var, 0.1, 3.0, 0.1, 1)
        self._add_scale(sliders, "Feather", self.feather_var, 0.0, 4.0, 0.05, 2)

        # Image size: ranges are unit-aware and rebind on unit change
        self._img_size_widgets = []
        self._add_scale(sliders, "Image Width", self.img_w_var, 0.0, 9600.0, 1.0, 3)
        self._add_scale(sliders, "Image Height", self.img_h_var, 0.0, 9600.0, 1.0, 4)
        self._img_size_widgets = list(self.scales[-2:])

        self._add_scale(sliders, "Grid Width", self.grid_w_var, 0.0, 420.0, 0.1, 5)
        self._add_scale(sliders, "Grid Height", self.grid_h_var, 0.0, 320.0, 0.1, 6)
        self._add_scale(sliders, "Grid X Offset", self.grid_x_var, 0.0, 420.0, 0.1, 7)
        self._add_scale(sliders, "Grid Y Offset", self.grid_y_var, 0.0, 320.0, 0.1, 8)
        self._add_scale(sliders, "Margin", self.margin_var, 0.0, 50.0, 0.1, 9)

        Checkbutton(sliders, text="Stagger rows (hex)", variable=self.stagger_var,
                    anchor="w").grid(row=10, column=0, columnspan=3, sticky="w",
                                     padx=6, pady=3)

        Label(sliders, text="Defaults: hole 0.5 mm, spacing 1.5 mm.",
              foreground="#555").grid(row=11, column=0, columnspan=3, sticky="w", padx=8, pady=(10, 0))
        Label(sliders, text="0 image/grid size = full source / full image.",
              foreground="#555").grid(row=12, column=0, columnspan=3, sticky="w", padx=8)
        self._img_size_hint = Label(
            sliders,
            text="Image size is in the current unit (e.g. 6 in × 4 in or 152.4 mm × 101.6 mm).",
            foreground="#555",
        )
        self._img_size_hint.grid(row=13, column=0, columnspan=3, sticky="w", padx=8, pady=(0, 4))
        self._rebind_img_size_scales()

        sliders.grid_columnconfigure(1, weight=1)

        self._update_slider_resolutions()

        self.canvas = Label(right, text="Open an image to preview.", anchor="center")
        self.canvas.pack(expand=True, fill="both")

    def _bind_vars(self):
        self.unit.trace_add("write", lambda *_: self._on_unit_change())
        self.step_var.trace_add("write", lambda *_: self._on_step_change())

        self.img_w_var.trace_add("write", lambda *_: self._on_var_changed("img_w"))
        self.img_h_var.trace_add("write", lambda *_: self._on_var_changed("img_h"))
        self.grid_w_var.trace_add("write", lambda *_: self._on_var_changed("grid_w"))
        self.grid_h_var.trace_add("write", lambda *_: self._on_var_changed("grid_h"))
        self.grid_x_var.trace_add("write", lambda *_: self._on_var_changed("grid_x"))
        self.grid_y_var.trace_add("write", lambda *_: self._on_var_changed("grid_y"))
        self.hole_var.trace_add("write", lambda *_: self._on_var_changed("hole"))
        self.spacing_var.trace_add("write", lambda *_: self._on_var_changed("spacing"))
        self.feather_var.trace_add("write", lambda *_: self._on_var_changed("feather"))
        self.margin_var.trace_add("write", lambda *_: self._on_var_changed("margin"))
        self.stagger_var.trace_add("write", lambda *_: self._on_var_changed("stagger"))

    def _on_var_changed(self, name: str) -> None:
        self._last_changed = name
        self.refresh()

    def _on_unit_change(self):
        if self._converting:
            return
        new_unit = self.unit.get()
        old_unit = self.prev_unit
        if old_unit == new_unit:
            return

        self._converting = True
        self._suppress_refresh = True

        # Capture old values BEFORE touching scale ranges, because
        # Tkinter clamps the bound variable during configure().
        old_values = [var.get() for var in [
            self.hole_var, self.spacing_var, self.feather_var,
            self.grid_w_var, self.grid_h_var,
            self.grid_x_var, self.grid_y_var,
            self.margin_var,
            self.img_w_var, self.img_h_var,
        ]]

        # Update scale ranges FIRST so the converted values don't get
        # clamped by the old unit's limits.
        self._update_all_scale_ranges()
        self._update_slider_resolutions()

        vars_to_convert = [
            self.hole_var, self.spacing_var, self.feather_var,
            self.grid_w_var, self.grid_h_var,
            self.grid_x_var, self.grid_y_var,
            self.margin_var,
            self.img_w_var, self.img_h_var,
        ]
        for var, old_val in zip(vars_to_convert, old_values):
            converted = convert_value(old_val, old_unit, new_unit)
            var.set(converted)

        self.prev_unit = new_unit
        self._converting = False
        self._suppress_refresh = False
        self.refresh()

    def _on_step_change(self):
        self._update_slider_resolutions()

    def _update_slider_resolutions(self):
        unit = self.unit.get()
        try:
            base_step = float(self.step_var.get())
        except (ValueError, TclError):
            base_step = 0.01
        if unit == "px":
            res = max(1, round(base_step * 1000.0))
        else:
            res = max(0.001, base_step)
        for sc in self.scales:
            sc.configure(resolution=res)

    def _update_all_scale_ranges(self) -> None:
        """Update every scale's min/max for the current unit."""
        unit = self.unit.get()
        mm_ranges = [
            (0.1, 1.0),    # hole
            (0.1, 3.0),    # spacing
            (0.0, 4.0),    # feather
            (0.0, 420.0),  # grid_w
            (0.0, 320.0),  # grid_h
            (0.0, 420.0),  # grid_x
            (0.0, 320.0),  # grid_y
        ]
        for idx, (frm_mm, to_mm) in enumerate(mm_ranges):
            sc = self.scales[idx]
            sc.configure(
                from_=convert_value(frm_mm, "mm", unit),
                to=convert_value(to_mm, "mm", unit),
            )

        self._update_margin_scale_range()
        self._rebind_img_size_scales()

    def _update_margin_scale_range(self) -> None:
        unit = self.unit.get()
        if self.src_img:
            src_w_px, src_h_px = self.src_img.size
            img_w_px = int(to_px(self.img_w_var.get(), unit)) if self.img_w_var.get() else src_w_px
            img_h_px = int(to_px(self.img_h_var.get(), unit)) if self.img_h_var.get() else src_h_px
            margin_max_px = min(img_w_px, img_h_px) / 3.0
        else:
            margin_max_px = 0.0

        margin_max = max(0.0, margin_max_px / current_px_per_unit(unit))
        self.margin_var.set(min(self.margin_var.get(), margin_max))
        self.scales[-1].configure(
            from_=0.0,
            to=margin_max,
        )

    def _rebind_img_size_scales(self) -> None:
        """Reconfigure the Image W/H slider ranges for the current unit.

        A 6×4 in printout at 1440 DPI needs 8640×5760 pixels. Use the unit
        in the dropdown to express the physical size, then convert to pixels
        at 1440 DPI when saving.
        """
        if not hasattr(self, "_img_size_widgets"):
            return
        unit = self.unit.get()
        if unit == "mm":
            to = 600.0  # 600 mm = ~23.6 in
            res = 0.1
        elif unit == "inch":
            to = 24.0   # 24 in = 600 mm
            res = 0.01
        else:  # px
            to = 1440.0 * 24.0  # 24 inches worth of pixels
            res = 1.0
        for sc in self._img_size_widgets:
            sc.configure(from_=0.0, to=to, resolution=res)
        if hasattr(self, "_img_size_hint"):
            self._img_size_hint.config(
                text=(
                    f"Image size is in the current unit. The output PNG is saved at "
                    f"1440 DPI, so 6 in × 4 in becomes 8640 × 5760 px; "
                    f"152.4 mm × 101.6 mm becomes 8640 × 5760 px."
                )
            )

    # ── state helpers ────────────────────────────────────────────────────────

    def _pick_default_input(self) -> None:
        project_root = os.path.dirname(SCRIPT_DIR)
        candidates = [
            resource_path(os.path.join("design", "danger.png")),
            os.path.join(project_root, "danger.png"),
            os.path.join(project_root, "camera grid.png"),
            os.path.join(project_root, "black grid.png"),
        ]
        for path in candidates:
            if os.path.isfile(path):
                self.open_image(path)
                break

    def _current_params(self):
        unit = self.unit.get()
        return {
            "unit": unit,
            "img_w": self.img_w_var.get() or None,
            "img_h": self.img_h_var.get() or None,
            "grid_w": self.grid_w_var.get() or None,
            "grid_h": self.grid_h_var.get() or None,
            "grid_x": self.grid_x_var.get(),
            "grid_y": self.grid_y_var.get(),
            "hole_diam": self.hole_var.get(),
            "spacing": self.spacing_var.get(),
            "feather": self.feather_var.get(),
            "stagger": self.stagger_var.get(),
            "margin": self.margin_var.get(),
        }

    # ── actions ──────────────────────────────────────────────────────────────

    def _apply_src_image_size(self) -> None:
        unit = self.unit.get()
        if not self.src_img:
            return

        src_w_px, src_h_px = self.src_img.size
        if src_w_px <= 0 or src_h_px <= 0:
            return

        w_in = src_w_px / UV_DPI
        h_in = src_h_px / UV_DPI
        w_mm = round(w_in * 25.4, 1)
        h_mm = round(h_in * 25.4, 1)
        if unit == "inch":
            img_w = max(0.0, w_in)
            img_h = max(0.0, h_in)
        elif unit == "mm":
            img_w = max(0.0, w_mm)
            img_h = max(0.0, h_mm)
        else:
            img_w = max(0.0, src_w_px)
            img_h = max(0.0, src_h_px)

        if self.img_w_var.get() in (0.0, None):
            self.img_w_var.set(img_w)
        if self.img_h_var.get() in (0.0, None):
            self.img_h_var.set(img_h)

        if self.grid_w_var.get() in (0.0, None):
            self.grid_w_var.set(img_w)
        if self.grid_h_var.get() in (0.0, None):
            self.grid_h_var.set(img_h)

        self._clamp_grid_to_image()
        self._adjust_margin_consistency()

    def _img_unit_values(self):
        unit = self.unit.get()
        if not self.src_img:
            return 0.0, 0.0, 0.0, unit

        src_w_px, src_h_px = self.src_img.size
        if unit == "inch":
            img_w = max(0.0, src_w_px / UV_DPI)
            img_h = max(0.0, src_h_px / UV_DPI)
        elif unit == "mm":
            img_w = max(0.0, round((src_w_px / UV_DPI) * 25.4, 1))
            img_h = max(0.0, round((src_h_px / UV_DPI) * 25.4, 1))
        else:
            img_w = max(0.0, float(src_w_px))
            img_h = max(0.0, float(src_h_px))
        return img_w, img_h, float(src_w_px), unit

    def _clamp_grid_to_image(self) -> None:
        img_w, img_h, _, unit = self._img_unit_values()
        if img_w == 0.0 and img_h == 0.0:
            return
        img_limit_w = self.img_w_var.get() or img_w
        img_limit_h = self.img_h_var.get() or img_h
        self.grid_w_var.set(min(float(self.grid_w_var.get()), float(img_limit_w)))
        self.grid_h_var.set(min(float(self.grid_h_var.get()), float(img_limit_h)))

    def _adjust_margin_consistency(self) -> None:
        if self._last_changed not in ("margin", "img_w", "img_h", "grid_w", "grid_h"):
            return

        img_w, img_h, _, unit = self._img_unit_values()
        if img_w == 0.0 and img_h == 0.0:
            return

        if self._last_changed == "margin":
            img_limit_w = self.img_w_var.get() or img_w
            img_limit_h = self.img_h_var.get() or img_h
            if float(self.margin_var.get()) * 2 > float(img_limit_w):
                self.margin_var.set(max(0.0, float(img_limit_w) / 2))
            if float(self.grid_w_var.get()) > float(img_limit_w) - float(self.margin_var.get()) * 2:
                self.grid_w_var.set(max(0.0, float(img_limit_w) - float(self.margin_var.get()) * 2))
            if float(self.grid_h_var.get()) > float(img_limit_h) - float(self.margin_var.get()) * 2:
                self.grid_h_var.set(max(0.0, float(img_limit_h) - float(self.margin_var.get()) * 2))
            return

        if self._last_changed in ("img_w", "grid_w"):
            img_limit_w = float(self.img_w_var.get() or img_w)
            if img_limit_w == 0.0:
                return
            if float(self.grid_w_var.get()) > img_limit_w:
                self.grid_w_var.set(img_limit_w)
            if float(self.margin_var.get()) > 0 and float(self.grid_w_var.get()) > 0 and abs(float(self.grid_w_var.get()) - (img_limit_w - float(self.margin_var.get()) * 2)) > 1e-6:
                self.margin_var.set(0.0)
            return

        if self._last_changed in ("img_h", "grid_h"):
            img_limit_h = float(self.img_h_var.get() or img_h)
            if img_limit_h == 0.0:
                return
            if float(self.grid_h_var.get()) > img_limit_h:
                self.grid_h_var.set(img_limit_h)
            if float(self.margin_var.get()) > 0 and float(self.grid_h_var.get()) > 0 and abs(float(self.grid_h_var.get()) - (img_limit_h - float(self.margin_var.get()) * 2)) > 1e-6:
                self.margin_var.set(0.0)
            return

    def _enforce_hole_spacing_fit(self) -> None:
        if self.src_img is None:
            return

        img_w, img_h, _, unit = self._img_unit_values()
        grid_w = float(self.grid_w_var.get() or img_w or 0.0)
        grid_h = float(self.grid_h_var.get() or img_h or 0.0)
        diameter = float(to_px(self.hole_var.get(), unit))
        pitch = float(to_px(self.spacing_var.get(), unit))

        if pitch <= 0:
            self.spacing_var.set(self._format_param(current_px_per_unit(unit) * float(self.step_var.get())))
            pitch = float(to_px(self.spacing_var.get(), unit))

        if diameter <= pitch and diameter <= grid_w and diameter <= grid_h:
            return

        max_diameter = min(grid_w, grid_h, pitch)
        if max_diameter <= 0 or diameter <= max_diameter:
            raise ValueError("Hole size is larger than the grid area or spacing.")

        self.hole_var.set(self._format_param_float(convert_value(max_diameter, "px", unit)))
        self.spacing_var.set(self._format_param_float(convert_value(max(max_diameter, pitch), "px", unit)))

    def open_image(self, path=None):
        if path is None:
            path = filedialog.askopenfilename(
                title="Choose input image",
                filetypes=[
                    ("Images", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp"),
                    ("All files", "*.*"),
                ],
            )
        if not path:
            return
        img = Image.open(path).convert("RGBA")
        self.src_img = img
        self._apply_src_image_size()
        self.refresh()

    def reset_values(self) -> None:
        self.hole_var.set(DEFAULT_HOLE_SIZE_MM)
        self.spacing_var.set(DEFAULT_SPACING_MM)
        self.feather_var.set(DEFAULT_FEATHER_MM)
        self.grid_w_var.set(0.0)
        self.grid_h_var.set(0.0)
        self.grid_x_var.set(0.0)
        self.grid_y_var.set(0.0)
        self.stagger_var.set(False)
        self.margin_var.set(DEFAULT_MARGIN_MM)
        self.refresh()

    def save_result(self) -> None:
        if self.src_img is None:
            messagebox.showinfo("No image", "Open an image first.")
            return

        try:
            out = punch_holes(self.src_img, **self._current_params())
        except ValueError as exc:
            messagebox.showerror("Cannot save", str(exc))
            return

        # Suggested filename derived from the source image + current params.
        default_name = "camera-grid-output.png"
        src_name = getattr(self.src_img, "filename", None)
        unit = self.unit.get()
        if src_name:
            base = os.path.splitext(os.path.basename(src_name))[0]
            hs = self._format_param(self.hole_var.get())
            sp = self._format_param(self.spacing_var.get())
            stg = "-stagger" if self.stagger_var.get() else ""
            mrg = f"-m{self._format_param(self.margin_var.get())}" if self.margin_var.get() > 0 else ""
            iw = self.img_w_var.get()
            ih = self.img_h_var.get()
            if iw or ih:
                size_tag = f"{iw:g}X{ih:g}{self._unit_suffix(unit)}"
                default_name = f"{base}-{size_tag}-{hs}-{sp}{stg}{mrg}.png"
            else:
                default_name = f"{base}-{hs}-{sp}{stg}{mrg}.png"

        # Never default into the app bundle's own directory when frozen.
        initial_dir = None
        if not getattr(sys, "frozen", False) and src_name:
            initial_dir = os.path.dirname(src_name)

        path = filedialog.asksaveasfilename(
            title="Save perforated mask",
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("All files", "*.*")],
            initialfile=default_name,
            initialdir=initial_dir,
        )
        if not path:
            return

        try:
            out.save(path, dpi=(UV_DPI, UV_DPI))
        except (OSError, ValueError) as exc:
            messagebox.showerror("Save failed", f"{path}\n\n{exc}")
            return
        # Show the resulting pixel + physical size so the user can confirm
        # the file will print at the right size in eufymake studio.
        w, h = out.size
        w_in = w / UV_DPI
        h_in = h / UV_DPI
        w_mm = w_in * 25.4
        h_mm = h_in * 25.4
        messagebox.showinfo(
            "Saved",
            f"{path}\n\n"
            f"Pixel size:    {w} × {h} px\n"
            f"Print size:    {w_in:.2f} × {h_in:.2f} in\n"
            f"              {w_mm:.1f} × {h_mm:.1f} mm  @ {UV_DPI} DPI",
        )

    def save_eufymaker(self) -> None:
        if self.src_img is None:
            messagebox.showinfo("No image", "Open an image first.")
            return

        # Force a millimeter-sized export so EufyMaker Studio treats the
        # resulting file as the intended physical size instead of assuming
        # 1 pixel = 1 mm.
        mm_params = {
            "unit": "mm",
            "img_w": convert_value(self.img_w_var.get() or 0.0, self.unit.get(), "mm") or None,
            "img_h": convert_value(self.img_h_var.get() or 0.0, self.unit.get(), "mm") or None,
            "grid_w": convert_value(self.grid_w_var.get() or 0.0, self.unit.get(), "mm") or None,
            "grid_h": convert_value(self.grid_h_var.get() or 0.0, self.unit.get(), "mm") or None,
            "grid_x": convert_value(self.grid_x_var.get(), self.unit.get(), "mm"),
            "grid_y": convert_value(self.grid_y_var.get(), self.unit.get(), "mm"),
            "hole_diam": convert_value(self.hole_var.get(), self.unit.get(), "mm"),
            "spacing": convert_value(self.spacing_var.get(), self.unit.get(), "mm"),
            "feather": convert_value(self.feather_var.get(), self.unit.get(), "mm"),
            "stagger": self.stagger_var.get(),
            "margin": convert_value(self.margin_var.get(), self.unit.get(), "mm"),
        }

        try:
            out = punch_holes(self.src_img, **mm_params)
        except ValueError as exc:
            messagebox.showerror("Cannot save", str(exc))
            return

        w, h = out.size
        w_mm = w / PX_PER_MM
        h_mm = h / PX_PER_MM

        src_name = getattr(self.src_img, "filename", None)
        base = os.path.splitext(os.path.basename(src_name))[0] if src_name else "camera-grid"
        size_tag = f"{w_mm:.1f}X{h_mm:.1f}mm"
        default_name = f"{base}-{size_tag}.png"

        initial_dir = None
        if not getattr(sys, "frozen", False) and src_name:
            initial_dir = os.path.dirname(src_name)

        path = filedialog.asksaveasfilename(
            title="Save for EufyMaker (mm)",
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("All files", "*.*")],
            initialfile=default_name,
            initialdir=initial_dir,
        )
        if not path:
            return

        try:
            out.save(path, dpi=(UV_DPI, UV_DPI))
        except (OSError, ValueError) as exc:
            messagebox.showerror("Save failed", f"{path}\n\n{exc}")
            return

        messagebox.showinfo(
            "Saved for EufyMaker",
            f"{path}\n\n"
            f"Pixel size:    {w} × {h} px\n"
            f"EufyMaker size: {w_mm:.2f} × {h_mm:.2f} mm\n"
            f"               {w_mm / 25.4:.2f} × {h_mm / 25.4:.2f} in\n"
            f"@ {UV_DPI} DPI\n\n"
            f"If EufyMaker still shows mm, use the pixel size above as the "
            f"source of truth.",
        )

    # ── preview rendering ────────────────────────────────────────────────────

    def refresh(self):
        if self._suppress_refresh:
            return
        if self.src_img is None:
            self._show_placeholder("Open an image to preview.")
            return

        try:
            params = self._current_params()
            out = punch_holes(self.src_img, **params)
        except TclError:
            return
        except ValueError as exc:
            self._show_placeholder(str(exc))
            return

        self.display_img = out
        self._render_preview()

    def _render_preview(self):
        if not self.display_img:
            return
        w, h = self.display_img.size
        max_w = max(320, self.root.winfo_screenwidth() // 2)
        max_h = max(240, self.root.winfo_screenheight() // 2)
        scale = min(max_w / max(w, 1), max_h / max(h, 1), 1.0)
        new_w, new_h = max(1, int(w * scale)), max(1, int(h * scale))
        preview = self.display_img.resize((new_w, new_h), Image.LANCZOS)
        self.tk_img = ImageTk.PhotoImage(preview)
        self.canvas.config(image=self.tk_img, text="", compound="center")

    def _show_placeholder(self, message: str) -> None:
        self.canvas.config(image="", text=message, compound="center", fg="#555555",
                           font=("Helvetica", 12))


# ── Entry ────────────────────────────────────────────────────────────────────


def main() -> None:
    root = Tk()
    MaskApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
