# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec — CameraGrid standalone macOS app.

Bundles the Tkinter hole-grid editor, the perforated_mask punch engine,
lens_optics (dual-regime optics calculator), Pillow, Tcl/Tk and the Python
interpreter into a double-clickable .app.

Build (from any location, with a venv that has Pillow + pyinstaller):

    pyinstaller --noconfirm scripts/CameraGrid.spec

The .app lands in dist/CameraGrid.app next to where the spec is built.
No path edits are required after copying the project folder to another Mac.
"""

import os
import sys

try:
    HERE = os.path.abspath(os.path.dirname(__file__))
except NameError:
    HERE = os.path.abspath(os.path.dirname(sys.argv[0]))

ROOT = os.path.abspath(os.path.join(HERE, os.pardir))
SCRIPTS = os.path.join(ROOT, "scripts")

a = Analysis(
    [os.path.join(SCRIPTS, "perforated_mask_app.py")],
    pathex=[SCRIPTS],                       # so `perforated_mask`/`lens_optics` resolve at build time
    binaries=[],
    datas=[
        # Sample artwork so the app has a default image on first launch.
        (os.path.join(ROOT, "danger.png"), "design"),
    ],
    hiddenimports=["lens_optics"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CameraGrid",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,                          # GUI app: no terminal window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="CameraGrid",
)

app = BUNDLE(
    coll,
    name="CameraGrid.app",
    icon=None,
    bundle_identifier="com.cameragrid.maskeditor",
)
