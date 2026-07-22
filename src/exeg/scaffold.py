"""Generate a bilingual study file for a passage (exeg scaffold)."""
import datetime
import re
from pathlib import Path

from exeg import corpus, display, search
from exeg.corpus import Word
from exeg.refs import Ref

GREEK_STOP = {"εἰμί", "λέγω", "ἔχω", "γίνομαι"}
HEBREW_STOP = {"H1961", "H559", "H6213"}
SBLGNT_NOTICE = "SBLGNT: © 2010 Society of Biblical Literature and Logos Bible Software."
MAX_WORDS = 10
MAX_REFS = 12


def _pos(word: Word, greek: bool) -> str:
    if greek:
        return word.morph[:1]
    lemseg = word.lemma.split("/")
    morph = word.morph[1:] if word.morph[:1] in ("H", "A") else word.morph
    morphseg = morph.split("/")
    i = next((k for k, s in enumerate(lemseg) if re.search(r"\d", s)), len(lemseg) - 1)
    seg = morphseg[i] if i < len(morphseg) else morphseg[-1]
    return seg[:1]


def pick_words(ref: Ref) -> list[Word]:
    version = "sblgnt" if ref.book.nt else "wlc"
    picked, seen = [], set()
    for w in corpus.get_words(ref, version):
        if _pos(w, ref.book.nt) not in ("V", "N", "A"):
            continue
        if ref.book.nt and w.lemma in GREEK_STOP:
            continue
        if not ref.book.nt and w.strongs in HEBREW_STOP:
            continue
        key = w.strongs or w.lemma
        if key in seen:
            continue
        seen.add(key)
        picked.append(w)
        if len(picked) >= MAX_WORDS:
            break
    return picked


def _word_section(ref: Ref) -> list[str]:
    greek, hebrew, _ = search._strongs_dicts()
    version = "sblgnt" if ref.book.nt else "wlc"
    lines: list[str] = []
    for w in pick_words(ref):
        occ = [x for x in corpus.read_words(version, ref.book.osis)
               if (x.strongs == w.strongs if w.strongs else x.lemma == w.lemma)]
        refs_s = ", ".join(f"{o.chapter}:{o.verse}" for o in
                           sorted({(o.chapter, o.verse): o for o in occ}.values(),
                                  key=lambda o: (o.chapter, o.verse))[:MAX_REFS])
        uniq = len({(o.chapter, o.verse) for o in occ})
        if uniq > MAX_REFS:
            refs_s += ", …"
        entry = (greek.get(w.strongs) or hebrew.get(w.strongs) or {})
        heading_lemma = entry.get("lemma") or w.lemma
        gloss = (entry.get("strongs_def", "") or entry.get("kjv_def", "") or "—").strip()
        surface = w.surface.replace("/", "")
        surface = re.sub(r"^[⸀⸁⸂⸃\s]+|[⸀⸁⸂⸃,.;·—\s]+$", "", surface)
        lines.append(f"### {heading_lemma} ({surface}, v. {w.verse}) — {w.strongs or '?'} · "
                     f"{search.greek_morph_label(w.morph)}")
        lines.append(f"gloss: {gloss} · in {ref.book.en}: {uniq}× ({refs_s})")
        lines.append("（your analysis · 你的分析）")
        lines.append("")
    if not lines:
        lines = ["（no original-language text in corpus — run `exeg fetch`）", ""]
    return lines


def build(ref: Ref, versions: list[str] | None = None, today: str | None = None) -> str:
    versions = versions or display.default_versions(ref.book)
    texts, notes = display.gather(ref, versions)
    today = today or datetime.date.today().isoformat()
    labels = " | ".join(display.LABELS.get(v, v.upper()) for v in versions)
    out = [f"# {ref.en_label()} · {ref.zh_label(full=True)}",
           f"> scaffolded {today} · {labels}", "",
           "## Text · 经文对照", ""]
    out += [f"> {n}" for n in notes]
    ids = sorted({vid for tv in texts.values() for vid in tv})
    for ch, v in ids:
        out.append(f"### {ref.book.en} {ch}:{v} · {ref.book.zh_abbr} {ch}:{v}")
        for version in versions:
            if version not in texts:
                continue
            label = display.LABELS.get(version, version.upper())
            t = texts[version].get((ch, v))
            out.append(f"- **{label}** {t if t else f'[not in {label}]'}")
        out.append("")
    out += ["## Word Studies · 字词研究", ""]
    out += _word_section(ref)
    out += ["## Structure & Context · 结构与背景",
            "- Literary structure · 文学结构：",
            "- Historical setting · 历史背景：",
            "- Place in the book's argument · 在全书论证中的位置：", "",
            "## Interpretation · 释经结论", "", "",
            "## Theology & Application · 神学综合与应用",
            "- Cross-references · 串珠：", "", "---"]
    if "esv" in texts and texts["esv"]:
        from exeg import esv
        out.append(esv.NOTICE)
    if "nasb95" in texts and texts["nasb95"] and not corpus.has_book("nasb95", ref.book.osis):
        from exeg import apibible
        out.append(apibible.NOTICE)
    if ("sblgnt" in texts and texts["sblgnt"]):
        out.append(SBLGNT_NOTICE)
    return "\n".join(out).rstrip() + "\n"


def write(ref: Ref, force: bool = False, versions: list[str] | None = None) -> Path:
    path = corpus.studies_dir() / f"{ref.slug()}.md"
    if path.exists() and not force:
        raise SystemExit(f"{path} exists — use --force to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build(ref, versions), encoding="utf-8")
    return path


def cmd_scaffold(args) -> int:
    import sys
    from exeg import canon, refs
    try:
        ref = refs.parse_ref(args.ref)
    except (refs.BadRef, canon.UnknownBook) as e:
        print(str(e), file=sys.stderr)
        return 1
    versions = args.versions.split(",") if args.versions else None
    path = write(ref, force=args.force, versions=versions)
    print(f"wrote {path.resolve()}")
    return 0
