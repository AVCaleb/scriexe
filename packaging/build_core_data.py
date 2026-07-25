#!/usr/bin/env python3
"""Stage only redistributable core corpora for frozen scriexe builds.

Bundles CUVS + ASV (translations) and Strong's + SBLGNT + WLC (original-
language study data) so that Hebrew/Greek word study works offline without
the optional download step.
"""
import argparse
import shutil
from pathlib import Path

from exeg import canon

CORE = ("cuvs", "asv")
# Original-language study data bundled for offline word study
BUNDLED_STUDY = ("sblgnt", "wlc")


def stage(source_root: Path, output: Path) -> None:
    corpus_root = source_root / "data" / "corpus"
    missing = []
    for version in CORE:
        for book in canon.BOOKS:
            if not (corpus_root / version / f"{book.osis}.tsv").is_file():
                missing.append(f"{version}/{book.osis}.tsv")
    # Check word-level versions (NT for sblgnt, OT for wlc)
    for version in BUNDLED_STUDY:
        books = canon.NT_BOOKS if version == "sblgnt" else [b for b in canon.BOOKS if not b.nt]
        for book in books:
            if not (corpus_root / version / f"{book.osis}.tsv").is_file():
                missing.append(f"{version}/{book.osis}.tsv")
    # Check Strong's JSON files
    strongs_dir = corpus_root / "strongs"
    for fname in ("greek.json", "hebrew.json", "greek-lemma-map.json"):
        if not (strongs_dir / fname).is_file():
            missing.append(f"strongs/{fname}")
    if missing:
        raise SystemExit("incomplete core corpus: " + ", ".join(missing[:10]))
    if output.exists():
        shutil.rmtree(output)
    for version in CORE:
        shutil.copytree(corpus_root / version, output / "data" / "corpus" / version)
    for version in BUNDLED_STUDY:
        shutil.copytree(corpus_root / version, output / "data" / "corpus" / version)
    # Bundle Strong's dictionary data
    shutil.copytree(strongs_dir, output / "data" / "corpus" / "strongs")
    attrs = Path(__file__).parent / "attribution"
    shutil.copytree(attrs, output / "data" / "attribution")
    print(f"staged CUVS + ASV + Strong's + SBLGNT + WLC in {output}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    stage(args.source_root.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
