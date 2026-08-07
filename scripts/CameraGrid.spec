# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec — CameraGrid standalone macOS app.

Bundles the Tkinter hole-grid editor, the perforated_mask punch engine,
Pillow, Tcl/Tk and the Python interpreter into a double-clickable .app.

Build (from the repo root, with a venv that has Pillow + pyinstaller):

    pyinstaller --noconfirm scripts/CameraGrid.spec

The .app lands in dist/CameraGrid.app next to where the spec is built.
"""

import os

ROOT = "/Users/davec/Desktop/Camera Grid"
SCRIPTS = os.path.join(ROOT, "scripts")
DESIGN = os.path.join(ROOT, "design")

a = Analysis(
    [os.path.join(SCRIPTS, "perforated_mask_app.py")],
    pathex=[SCRIPTS],                       # so `perforated_mask` resolves at build time
    binaries=[],
    datas=[
        # Sample artwork so the app has a default image on first launch.
        (os.path.join(DESIGN, "Caution 6X4.png"), "design"),
    ],
    hiddenimports=[],
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
