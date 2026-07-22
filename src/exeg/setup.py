"""First-run onboarding wizard for exeg (like AI-agent CLI key setup).

Prompts for interface language and pastes API keys with masked input
(getpass), writing them to the gitignored `.env`. Runs automatically on first
launch, and can be re-run via `exeg setup` or the `:setup` TUI command.
"""
import getpass
import os
from pathlib import Path

from exeg import corpus, i18n, notes


def env_path() -> Path:
    return corpus.root() / ".env"


def is_configured() -> bool:
    return bool(notes.read_meta().get("setup_done"))


def _read_env_keys() -> dict[str, str]:
    out = {}
    p = env_path()
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            v = v.strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                v = v[1:-1]
            out[k.strip()] = v
    return out


def key_is_set(env_var: str) -> bool:
    return bool(os.environ.get(env_var) or _read_env_keys().get(env_var))


def write_env_key(key: str, value: str) -> None:
    """Set/replace one KEY=value line in .env (created if absent). Blank deletes."""
    p = env_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = p.read_text(encoding="utf-8").splitlines() if p.exists() else []
    lines = [l for l in lines if not l.strip().startswith(key + "=")]
    value = value.strip()
    if value:
        lines.append(f"{key}={value}")
    p.write_text(("\n".join(lines) + "\n") if lines else "", encoding="utf-8")


def _paste(prompt: str) -> str:
    """Masked paste via getpass (input not echoed)."""
    try:
        return getpass.getpass(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def run_setup(lang: str | None = None, only_keys: bool = False) -> dict:
    """Run the onboarding wizard. Returns what was configured."""
    print()
    print("exeg — setup\n" + "=" * 40)
    configured: dict = {}
    if not only_keys:
        print("Interface language / 界面语言:  en = English,  zh = 中文")
        if lang:
            chosen = lang
        else:
            chosen = (input("  language [en]: ").strip() or "en").lower()
        if chosen not in i18n.LANGS:
            chosen = "en"
        configured["lang"] = chosen
        print(f"  -> {i18n.lang_name(chosen)}\n")

    print("API keys are optional. Without them ESV/NASB95 text is simply shown")
    print("as 'unavailable'; bundled 和合本/ASV reading still works offline.")
    print("You can add keys later any time with `scriexe setup` or")
    print("the `:setup` command in the TUI.\n")
    esv = nasb = ""
    try:
        add = input("  Add API keys now? [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        add = ""
    if add.startswith("y"):
        print("  (Enter or Ctrl-C on a prompt skips that key.)\n")
        esv = _paste("  ESV API key    (free at api.esv.org): ")
        nasb = _paste("  NASB95 API key (api.bible):         ")
    else:
        print("  skipped — no keys set\n")
    if esv:
        write_env_key("ESV_API_KEY", esv)
        os.environ["ESV_API_KEY"] = esv
        configured["esv"] = True
    if nasb:
        write_env_key("API_BIBLE_KEY", nasb)
        os.environ["API_BIBLE_KEY"] = nasb
        configured["nasb"] = True

    m = notes.read_meta()
    if "lang" in configured:
        m["lang"] = configured["lang"]
    m["setup_done"] = True
    notes.write_meta(m)

    print("\n" + "-" * 40)
    if "lang" in configured:
        print(f"language: {i18n.lang_name(configured['lang'])}")
    print(f"ESV key:     {'saved to .env' if configured.get('esv') else 'skipped'}")
    print(f"NASB95 key:  {'saved to .env' if configured.get('nasb') else 'skipped'}")
    if not configured.get("esv") or not configured.get("nasb"):
        print("You can add keys later: `scriexe setup` or `:setup` in the TUI.")
    print(".env is gitignored — keys are never committed.\n")
    return configured


def cmd_setup(args) -> int:
    """Re-run onboarding. Uses the curses intro when interactive, else the plain wizard."""
    import sys
    if sys.stdin.isatty():
        from exeg import tui
        return tui.run(tui.Controller(intro=True))
    run_setup(lang=getattr(args, "lang", None))
    return 0