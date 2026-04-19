# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Hematopoiesis Simulator desktop app.

Build command (run from project root):
    pyinstaller simulator.spec

Output:
    dist/HematopoiesisSim/
    dist/HematopoiesisSim/HematopoiesisSim.exe   ← run this
"""

import os
from PyInstaller.utils.hooks import collect_data_files

# Project root = directory containing this spec file
ROOT = os.path.dirname(os.path.abspath(SPEC))

print(f"[spec] ROOT          = {ROOT}")
print(f"[spec] frontend/public = {os.path.join(ROOT, 'frontend', 'public')}")
print(f"[spec] configs       = {os.path.join(ROOT, 'configs')}")
print(f"[spec] Help_page     = {os.path.join(ROOT, 'Help_page', 'help.html')}")

# ── Data files ────────────────────────────────────────────────────────────────
datas = [
    # Simulation YAML configs (required by simulation_session.py)
    (os.path.join(ROOT, "configs"),              "configs"),
    # Frontend static files — CDN React, no build step needed
    (os.path.join(ROOT, "frontend", "public"),   os.path.join("frontend", "public")),
    # Help page
    (os.path.join(ROOT, "Help_page", "help.html"), "Help_page"),
]

# Matplotlib needs its bundled fonts and style-sheet data
datas += collect_data_files("matplotlib")
# ReportLab needs its Type-1 font data
datas += collect_data_files("reportlab")

# ── Hidden imports ────────────────────────────────────────────────────────────
# uvicorn uses importlib-based plugin discovery; PyInstaller can't see these.
hiddenimports = [
    # uvicorn internals
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.http.httptools_impl",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.protocols.websockets.wsproto_impl",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
    # async runtime
    "anyio",
    "anyio._backends._asyncio",
    # static file serving (FastAPI StaticFiles)
    "aiofiles",
    "aiofiles.os",
    "aiofiles.threadpool",
    # matplotlib Agg backend (used by pdf_exporter.py)
    "matplotlib.backends.backend_agg",
    # pydantic v2 core
    "pydantic",
    "pydantic_core",
    # email helpers used by some starlette internals
    "email.mime.text",
    "email.mime.multipart",
]

# ── Analysis ──────────────────────────────────────────────────────────────────
a = Analysis(
    [os.path.join(ROOT, "launcher.py")],
    pathex=[
        ROOT,                              # project root → cell_diff_sim importable
        os.path.join(ROOT, "backend"),     # backend/ → app, desktop_app, routes…
    ],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # IMPORTANT: do NOT exclude stdlib modules (tkinter/wx/Qt are safe to exclude
    # because they are GUI frameworks, not stdlib).
    # Never put "unittest", "logging", "email", "json" etc. here!
    excludes=[
        "tkinter",
        "PyQt5",  "PyQt6",
        "PySide2", "PySide6",
        "wx",
        "IPython", "jupyter", "notebook",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

# ── Executable ────────────────────────────────────────────────────────────────
exe = EXE(
    pyz,
    a.scripts,
    [],                   # binaries stay in COLLECT (one-dir bundle)
    exclude_binaries=True,
    name="HematopoiesisSim",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,         # keep console visible so errors are readable
    icon=None,            # set to "frontend/public/logo.ico" if you convert logo.png
)

# ── Collect into one directory ────────────────────────────────────────────────
# Result: dist/HematopoiesisSim/ folder — zip this for distribution.
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="HematopoiesisSim",
)
