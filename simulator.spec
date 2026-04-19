# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Hematopoiesis Simulator desktop app.

Build command (run from project root):
    pyinstaller simulator.spec

Output:
    dist/HematopoiesisSim/          ← folder to distribute
    dist/HematopoiesisSim/HematopoiesisSim.exe   ← the executable
"""

import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Project root = directory that contains this spec file
ROOT = os.path.dirname(os.path.abspath(SPEC))

# ── Data files to bundle ──────────────────────────────────────────────────────
datas = [
    # YAML simulation configs
    (os.path.join(ROOT, "configs"),                   "configs"),
    # Frontend static files (CDN React — no build step needed)
    (os.path.join(ROOT, "frontend", "public"),        os.path.join("frontend", "public")),
    # Help page (only the rendered HTML — skip raw .md/.docx sources)
    (os.path.join(ROOT, "Help_page", "help.html"),    "Help_page"),
]

# Matplotlib needs its data directory (fonts, style sheets, etc.)
datas += collect_data_files("matplotlib")
# ReportLab needs its fonts and resources
datas += collect_data_files("reportlab")

# ── Hidden imports ────────────────────────────────────────────────────────────
# uvicorn uses a plugin-discovery pattern; PyInstaller misses these.
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
    # async backend
    "anyio",
    "anyio._backends._asyncio",
    # static file serving
    "aiofiles",
    "aiofiles.os",
    "aiofiles.threadpool",
    # matplotlib Agg backend (used by pdf_exporter)
    "matplotlib.backends.backend_agg",
    # pydantic v2
    "pydantic",
    "pydantic_core",
    # email (used by some starlette internals)
    "email.mime.text",
    "email.mime.multipart",
]

# ── Analysis ──────────────────────────────────────────────────────────────────
a = Analysis(
    [os.path.join(ROOT, "launcher.py")],
    pathex=[
        ROOT,                              # project root (cell_diff_sim lives here)
        os.path.join(ROOT, "backend"),     # backend package
    ],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # GUI frameworks not needed
        "tkinter", "PyQt5", "PyQt6", "PySide2", "PySide6", "wx",
        # Jupyter / IPython bloat
        "IPython", "jupyter", "notebook",
        # Test frameworks
        "pytest", "unittest",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

# ── Executable (one-directory bundle — fastest startup) ───────────────────────
exe = EXE(
    pyz,
    a.scripts,
    [],                       # binaries go into COLLECT, not inside the exe
    exclude_binaries=True,
    name="HematopoiesisSim",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,             # show console window — useful to see errors
                              # change to False for a "silent" release build
    icon=os.path.join(ROOT, "frontend", "public", "logo.png") if os.path.exists(
          os.path.join(ROOT, "frontend", "public", "logo.png")) else None,
)

# ── Collect into one directory ────────────────────────────────────────────────
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="HematopoiesisSim",   # → dist/HematopoiesisSim/
)
