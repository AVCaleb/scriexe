#!/usr/bin/env python3
"""Create one platform-constrained npm package from a PyInstaller folder."""
import argparse
import json
import shutil
from pathlib import Path

TARGETS = {
    "darwin-arm64": ("darwin", "arm64"),
    "darwin-x64": ("darwin", "x64"),
    "linux-arm64": ("linux", "arm64"),
    "linux-x64": ("linux", "x64"),
    "win32-x64": ("win32", "x64"),
}


def prepare(target: str, dist: Path, output: Path, version: str) -> None:
    if target not in TARGETS:
        raise SystemExit(f"unsupported target: {target}")
    if not dist.is_dir():
        raise SystemExit(f"missing PyInstaller directory: {dist}")
    if output.exists():
        shutil.rmtree(output)
    payload = output / "dist" / "scriexe"
    shutil.copytree(dist, payload)
    os_name, cpu = TARGETS[target]
    package = {
        "name": f"scriexe-{target}",
        "version": version,
        "description": f"Native scriexe binary for {target}",
        "os": [os_name],
        "cpu": [cpu],
        "files": ["dist"],
    }
    (output / "package.json").write_text(
        json.dumps(package, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True, choices=TARGETS)
    parser.add_argument("--dist", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    prepare(args.target, args.dist.resolve(), args.output.resolve(), args.version)


if __name__ == "__main__":
    main()
