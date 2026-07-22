#!/usr/bin/env python3
"""Stage only redistributable core corpora for frozen scriexe builds."""
import argparse
import shutil
from pathlib import Path

from exeg import canon

CORE = ("cuvs", "asv")


def stage(source_root: Path, output: Path) -> None:
    corpus_root = source_root / "data" / "corpus"
    missing = []
    for version in CORE:
        for book in canon.BOOKS:
            if not (corpus_root / version / f"{book.osis}.tsv").is_file():
                missing.append(f"{version}/{book.osis}.tsv")
    if missing:
        raise SystemExit("incomplete core corpus: " + ", ".join(missing[:10]))
    if output.exists():
        shutil.rmtree(output)
    for version in CORE:
        shutil.copytree(corpus_root / version, output / "data" / "corpus" / version)
    attrs = Path(__file__).parent / "attribution"
    shutil.copytree(attrs, output / "data" / "attribution")
    print(f"staged CUVS + ASV in {output}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    stage(args.source_root.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
