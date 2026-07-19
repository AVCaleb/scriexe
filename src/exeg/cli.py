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
            os.environ.setdefault(key.strip(), val.strip())


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="exeg", description=__doc__)
    p.add_argument("--version", action="store_true", help="print version and exit")
    sub = p.add_subparsers(dest="command")

    from exeg import fetch as _fetch
    f = sub.add_parser("fetch", help="download and normalize all datasets")
    f.add_argument("--only", help="comma list: strongs,sblgnt,wlc,ebible")
    f.set_defaults(func=_fetch.cmd_fetch)

    from exeg import display as _display
    pp = sub.add_parser("passage", help="print a passage in parallel versions")
    pp.add_argument("ref", help="e.g. '1Pet 3:18-22' or '彼前3:18-22'")
    pp.add_argument("--versions", help="comma list, e.g. sblgnt,esv,cuvs")
    pp.set_defaults(func=_display.cmd_passage)
    return p


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.version:
        print(__version__)
        return 0
    if not args.command:
        parser.print_usage(sys.stderr)
        return 2
    try:
        _load_env()
        return args.func(args)
    except SystemExit:
        raise
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
