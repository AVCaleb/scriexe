"""exeg — terminal Bible exegesis workspace. Dispatch only; logic lives in modules."""
import argparse
import os
import sys

from exeg import __version__


def _load_env() -> None:
    """Load KEY=VALUE lines from <root>/.env into os.environ (no override)."""
    from exeg import corpus  # imported lazily; corpus.py arrives in Task 4
    path = corpus.root() / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            v = val.strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                v = v[1:-1]
            os.environ.setdefault(key.strip(), v)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="exeg", description=__doc__)
    p.add_argument("--version", action="store_true", help="print version and exit")
    sub = p.add_subparsers(dest="command")

    from exeg import fetch as _fetch
    f = sub.add_parser("fetch", help="download and normalize all datasets")
    f.add_argument("--only", help="comma list: strongs,sblgnt,wlc,ebible,vulgate")
    f.add_argument("--versions", help="with --only ebible: comma list such as cuvs,asv")
    f.set_defaults(func=_fetch.cmd_fetch)

    from exeg import display as _display
    pp = sub.add_parser("passage", help="print a passage in parallel versions")
    pp.add_argument("ref", help="e.g. '1Pet 3:18-22' or '彼前3:18-22'")
    pp.add_argument("--versions", help="comma list, e.g. sblgnt,esv,cuvs")
    pp.set_defaults(func=_display.cmd_passage)

    from exeg import importer as _importer
    ip = sub.add_parser("import", help="import a user-licensed translation (kept local)")
    ip.add_argument("path", nargs="?", help="a .usfm/.sfm file, a directory of them, or a REF<TAB>text .tsv")
    ip.add_argument("--version", help="corpus version name, e.g. nasb95 (optional if the .tsv has a '# version:' header)")
    ip.add_argument("--format", choices=["usfm", "tsv"], help="override detection")
    ip.add_argument("--example", action="store_true", help="print the required import format with an example")
    ip.set_defaults(func=_importer.cmd_import)

    from exeg import search as _search
    sp = sub.add_parser("search", help="search the corpus (regex)")
    sp.add_argument("pattern")
    sp.add_argument("--versions", help="comma list (default web,kjv,cuvs; with --lemma: sblgnt,wlc)")
    sp.add_argument("--book", help="restrict to one book")
    sp.add_argument("--lemma", action="store_true", help="match lemmas in Greek/Hebrew corpora")
    sp.add_argument("--limit", type=int, default=50)
    sp.set_defaults(func=_search.cmd_search)

    wp = sub.add_parser("word", help="word study: occurrences of a Strong's number or lemma")
    wp.add_argument("query", help="G3958, H1254, or a lemma like πάσχω")
    wp.add_argument("--limit", type=int, default=30)
    wp.set_defaults(func=_search.cmd_word)

    from exeg import scaffold as _scaffold
    sc = sub.add_parser("scaffold", help="generate a bilingual study file")
    sc.add_argument("ref")
    sc.add_argument("--versions", help="comma list (default: originals,esv,nasb95,cuvs)")
    sc.add_argument("--force", action="store_true", help="overwrite an existing study file")
    sc.set_defaults(func=_scaffold.cmd_scaffold)

    from exeg import tui as _tui
    tp = sub.add_parser("tui", help="interactive curses workspace")
    tp.add_argument("--versions", help="comma list (default: local originals + cuvs + web)")
    tp.set_defaults(func=_tui.cmd_tui)

    from exeg import setup as _setup
    sp = sub.add_parser("setup", help="first-run onboarding: language + paste API keys")
    sp.add_argument("--lang", choices=["en", "zh"], help="set interface language non-interactively")
    sp.set_defaults(func=_setup.cmd_setup)
    return p


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.version and not args.command:
        print(__version__)
        return 0
    if not args.command:
        # bare `exeg` launches the interactive TUI; first run shows the curses intro
        from exeg import tui as _tui, setup as _setup
        _load_env()
        intro = sys.stdin.isatty() and not _setup.is_configured()
        return _tui.run(_tui.Controller(intro=intro))
    try:
        _load_env()
        return args.func(args)
    except SystemExit:
        raise
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
