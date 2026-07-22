import io
import sys

from exeg.cli import build_parser, main

def test_no_args_launches_tui_fallback(capsys, monkeypatch):
    # bare `exeg` now launches the curses TUI; without a real terminal it
    # falls back to a helpful message and exits non-zero.
    monkeypatch.setenv("TERM", "dumb")
    rc = main([])
    assert rc == 1
    err = capsys.readouterr().err
    assert "TUI" in err or "exeg passage" in err

def test_version_flag(capsys):
    assert main(["--version"]) == 0
    assert "0.1.0" in capsys.readouterr().out


def test_cli_reconfigures_narrow_windows_stream_for_multilingual_output(monkeypatch):
    raw = io.BytesIO()
    stdout = io.TextIOWrapper(raw, encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", stdout)
    assert main(["passage", "Jude 1:1", "--versions", "cuvs"]) == 0
    stdout.flush()
    assert stdout.encoding.lower().replace("-", "") == "utf8"
    assert raw.getvalue()


def test_parser_fetch_selected_versions():
    args = build_parser().parse_args(["fetch", "--only", "ebible",
                                      "--versions", "cuvs,asv"])
    assert args.versions == "cuvs,asv"
