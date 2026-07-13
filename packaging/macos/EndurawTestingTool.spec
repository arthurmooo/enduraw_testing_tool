# -*- mode: python ; coding: utf-8 -*-
"""Bundle macOS autonome pour Enduraw Testing Tool."""
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


ROOT = Path(SPECPATH).resolve().parents[1]
SRC = ROOT / "src"
UI_DIST = ROOT / "local_ui" / "dist"
ICON_ICO = ROOT / "icon.ico"
ICON_ICNS = ROOT / "build" / "macos" / "EndurawTestingTool.icns"

sys.path.insert(0, str(SRC))
from config import APP_VERSION

for required_path in (UI_DIST / "index.html", ICON_ICO, ICON_ICNS):
    if not required_path.exists():
        raise SystemExit(f"Ressource de packaging absente: {required_path}")

datas = collect_data_files("customtkinter") + [
    (str(UI_DIST), "local_ui/dist"),
    (str(ICON_ICO), "."),
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
    argv_emulation=False,
    icon=str(ICON_ICNS),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="EndurawTestingTool",
)

app = BUNDLE(
    coll,
    name="Enduraw Testing Tool V2.app",
    icon=str(ICON_ICNS),
    bundle_identifier="com.enduraw.testingtool.v2",
    info_plist={
        "CFBundleDisplayName": "Enduraw Testing Tool V2",
        "CFBundleShortVersionString": APP_VERSION,
        "CFBundleVersion": APP_VERSION,
        "NSHighResolutionCapable": True,
        "NSRequiresAquaSystemAppearance": False,
    },
)
