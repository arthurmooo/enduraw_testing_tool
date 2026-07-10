# -*- mode: python ; coding: utf-8 -*-
"""Bundle Windows onedir autonome pour Enduraw Testing Tool."""
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


ROOT = Path(SPECPATH).resolve().parents[1]
SRC = ROOT / "src"
UI_DIST = ROOT / "local_ui" / "dist"
ICON = ROOT / "icon.ico"

# The application imports top-level packages from src/. Make them visible
# while this spec is evaluated, then collect every project package explicitly.
sys.path.insert(0, str(SRC))

for required_path in (UI_DIST / "index.html", ICON):
    if not required_path.exists():
        raise SystemExit(f"Ressource de packaging absente: {required_path}")

# CustomTkinter lit ses themes depuis ses fichiers de package. PyMongo charge
# les modules DNS SRV dynamiquement pour les URI mongodb+srv.
datas = collect_data_files("customtkinter") + [
    (str(UI_DIST), "local_ui/dist"),
    (str(ICON), "."),
]
hiddenimports = sorted(set(
    ["config", "main_session"]
    + collect_submodules("core")
    + collect_submodules("local_api")
    + collect_submodules("ui")
    + collect_submodules("utils")
    + collect_submodules("dns")
    + collect_submodules("email_validator")
    + collect_submodules("pymongo")
))

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT), str(SRC)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
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
    name="EndurawTestingTool",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=str(ICON),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="EndurawTestingTool",
)
