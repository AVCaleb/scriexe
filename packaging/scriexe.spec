# PyInstaller one-folder specification for scriexe.
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

root = Path(SPECPATH).parent
core = root / "build" / "core" / "data"
if not core.is_dir():
    raise SystemExit("run packaging/build_core_data.py --output build/core first")

# Ship a CA certificate bundle so that urllib HTTPS works inside the frozen
# app even when the OS trust store is not discoverable (common on macOS).
cacert_src = None
try:
    import certifi
    cacert_src = Path(certifi.where())
except Exception:
    pass

datas = [(str(core), "data")]
if cacert_src and cacert_src.is_file():
    datas.append((str(cacert_src), "."))

a = Analysis(
    [str(root / "src" / "exeg" / "cli.py")],
    pathex=[str(root / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=collect_submodules("exeg") + ["certifi"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="scriexe",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="scriexe",
)
