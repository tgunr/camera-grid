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
    IntVar,
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
    hole_diam: float = 0.5,
    spacing: float = 1.5,
    feather: float = 0.0,
    stagger: bool = False,
    margin: float = 0.0,
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

        self.img_w_var = IntVar(value=0)
        self.img_h_var = IntVar(value=0)
        self.grid_w_var = DoubleVar(value=0.0)
        self.grid_h_var = DoubleVar(value=0.0)
        self.grid_x_var = DoubleVar(value=0.0)
        self.grid_y_var = DoubleVar(value=0.0)
        self.hole_var = DoubleVar(value=0.5)
        self.spacing_var = DoubleVar(value=1.5)
        self.feather_var = DoubleVar(value=0.0)
        self.stagger_var = BooleanVar(value=False)
        self.margin_var = DoubleVar(value=0.0)
        self.step_var = DoubleVar(value=0.01)

        self.prev_unit = self.unit.get()
        self._converting = False
        self._suppress_refresh = False
        self.scales: list[tuple[Scale, bool]] = []

        self.canvas_size = 640
        self._build_ui()
        self._bind_vars()
        self._pick_default_input()

    def _add_scale(self, parent: Frame, label: str, var, frm: float, to: float, res: float, row: int, fixed_res: bool = False) -> None:
        Label(parent, text=label, anchor="w").grid(row=row, column=0, sticky="w", padx=6, pady=3)
        sc = Scale(parent, variable=var, from_=frm, to=to, resolution=res,
                   orient="horizontal", length=220)
        sc.grid(row=row, column=1, sticky="ew", padx=6, pady=3)
        self.scales.append((sc, fixed_res))

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
                val = float(val_str) if isinstance(var, DoubleVar) else int(val_str)
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

        self._add_scale(sliders, "Image Width", self.img_w_var, 0, 9600, 1, 3, fixed_res=True)
        self._add_scale(sliders, "Image Height", self.img_h_var, 0, 9600, 1, 4, fixed_res=True)

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

        sliders.grid_columnconfigure(1, weight=1)

        self._update_slider_resolutions()

        self.canvas = Label(right, text="Open an image to preview.", anchor="center")
        self.canvas.pack(expand=True, fill="both")

    def _bind_vars(self):
        self.unit.trace_add("write", lambda *_: self._on_unit_change())
        self.step_var.trace_add("write", lambda *_: self._on_step_change())

        var_names = [
            "img_w_var", "img_h_var", "grid_w_var", "grid_h_var",
            "grid_x_var", "grid_y_var", "hole_var", "spacing_var", "feather_var",
            "stagger_var", "margin_var",
        ]
        for name in var_names:
            getattr(self, name).trace_add("write", lambda *_: self.refresh())

    def _on_unit_change(self):
        if self._converting:
            return
        new_unit = self.unit.get()
        old_unit = self.prev_unit
        if old_unit == new_unit:
            return

        self._converting = True
        self._suppress_refresh = True
        vars_to_convert = [
            self.hole_var, self.spacing_var, self.feather_var,
            self.grid_w_var, self.grid_h_var,
            self.grid_x_var, self.grid_y_var,
            self.margin_var,
        ]
        for var in vars_to_convert:
            old_val = var.get()
            var.set(convert_value(old_val, old_unit, new_unit))

        self.prev_unit = new_unit
        self._converting = False
        self._suppress_refresh = False
        self._update_slider_resolutions()
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
        for sc, fixed in self.scales:
            if fixed:
                continue
            sc.configure(resolution=res)

    # ── state helpers ────────────────────────────────────────────────────────

    def _pick_default_input(self) -> None:
        project_root = os.path.dirname(SCRIPT_DIR)
        candidates = [
            resource_path(os.path.join("design", "Caution 6X4.png")),
            os.path.join(project_root, "design", "Caution 6X4.png"),
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
        self.img_w_var.set(0)
        self.img_h_var.set(0)
        self.refresh()

    def reset_values(self) -> None:
        self.hole_var.set(0.5)
        self.spacing_var.set(1.5)
        self.feather_var.set(0.0)
        self.grid_w_var.set(0.0)
        self.grid_h_var.set(0.0)
        self.grid_x_var.set(0.0)
        self.grid_y_var.set(0.0)
        self.stagger_var.set(False)
        self.margin_var.set(0.0)
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
        if src_name:
            base = os.path.splitext(os.path.basename(src_name))[0]
            hs = self.hole_var.get()
            sp = self.spacing_var.get()
            stg = "-stagger" if self.stagger_var.get() else ""
            mrg = f"-m{self.margin_var.get():.2f}" if self.margin_var.get() > 0 else ""
            if self.img_w_var.get() or self.img_h_var.get():
                default_name = f"{base}-{self.img_w_var.get()}X{self.img_h_var.get()}-{hs}-{sp}{stg}{mrg}.png"
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
        messagebox.showinfo("Saved", path)

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
