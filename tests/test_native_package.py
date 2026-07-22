import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_prepare_native_package(tmp_path):
    dist = tmp_path / "dist" / "scriexe"
    dist.mkdir(parents=True)
    (dist / "scriexe").write_text("binary", encoding="utf-8")
    out = tmp_path / "package"
    subprocess.run([
        sys.executable, str(ROOT / "packaging" / "prepare_native_package.py"),
        "--target", "linux-x64", "--dist", str(dist),
        "--output", str(out), "--version", "1.2.3",
    ], check=True)
    package = json.loads((out / "package.json").read_text(encoding="utf-8"))
    assert package["name"] == "scriexe-linux-x64"
    assert package["version"] == "1.2.3"
    assert package["os"] == ["linux"] and package["cpu"] == ["x64"]
    assert package["repository"]["url"] == "https://github.com/AVCaleb/scriexe"
    assert (out / "dist" / "scriexe" / "scriexe").is_file()


def test_windows_native_package_uses_registry_safe_name(tmp_path):
    dist = tmp_path / "dist" / "scriexe"
    dist.mkdir(parents=True)
    (dist / "scriexe.exe").write_text("binary", encoding="utf-8")
    out = tmp_path / "package"
    subprocess.run([
        sys.executable, str(ROOT / "packaging" / "prepare_native_package.py"),
        "--target", "win32-x64", "--dist", str(dist),
        "--output", str(out), "--version", "1.2.3",
    ], check=True)
    package = json.loads((out / "package.json").read_text(encoding="utf-8"))
    assert package["name"] == "scriexe-windows-x64"
