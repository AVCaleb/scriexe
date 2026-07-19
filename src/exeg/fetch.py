"""Download and normalize open datasets into the local corpus (exeg fetch)."""
import json
import re
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

from exeg import canon, corpus
from exeg.corpus import Verse, Word
from exeg.usfm import parse_usfm

RAW = "https://raw.githubusercontent.com"
MORPHGNT_FILES = [  # (repo filename stem, verified 2026-07-19) — canonical NT order
    "61-Mt", "62-Mk", "63-Lk", "64-Jn", "65-Ac", "66-Ro", "67-1Co", "68-2Co",
    "69-Ga", "70-Eph", "71-Php", "72-Col", "73-1Th", "74-2Th", "75-1Ti",
    "76-2Ti", "77-Tit", "78-Phm", "79-Heb", "80-Jas", "81-1Pe", "82-2Pe",
    "83-1Jn", "84-2Jn", "85-3Jn", "86-Jud", "87-Re",
]
STRONGS_URLS = {
    "greek": f"{RAW}/openscriptures/strongs/master/greek/strongs-greek-dictionary.js",
    "hebrew": f"{RAW}/openscriptures/strongs/master/hebrew/strongs-hebrew-dictionary.js",
}
EBIBLE = {"web": "engwebp", "kjv": "eng-kjv", "cuvs": "cmn-cu89s"}
_OSIS_NS = "{http://www.bibletechnologies.net/2003/OSIS/namespace}"


def download(url: str, dest, force: bool = False):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and not force:
        return dest
    req = urllib.request.Request(url, headers={"User-Agent": "exeg/0.1 (personal study tool)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        dest.write_bytes(r.read())
    return dest


def parse_strongs_js(js_text: str) -> dict:
    return json.loads(js_text[js_text.index("{"): js_text.rindex("}") + 1])


def build_greek_lemma_map(greek: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for code in sorted(greek, key=lambda c: int(c[1:])):
        lemma = unicodedata.normalize("NFC", greek[code].get("lemma", "") or "")
        if lemma:
            out.setdefault(lemma, code)
    return out


def normalize_sblgnt(text: str, lemma_map: dict[str, str]) -> list[Word]:
    words: list[Word] = []
    idx, prev = 0, None
    for line in text.splitlines():
        parts = line.split()
        if len(parts) != 7:
            continue
        bcv, pos, parsing, surface, _word, _norm, lemma = parts
        ch, v = int(bcv[2:4]), int(bcv[4:6])
        idx = idx + 1 if prev == (ch, v) else 1
        prev = (ch, v)
        strongs = lemma_map.get(unicodedata.normalize("NFC", lemma), "")
        words.append(Word(ch, v, idx, surface, lemma, strongs, f"{pos}/{parsing}"))
    return words


def normalize_wlc(xml_text: str) -> list[Word]:
    root = ET.fromstring(xml_text)
    words: list[Word] = []
    for velem in root.iter(f"{_OSIS_NS}verse"):
        osis_id = velem.get("osisID", "")
        try:
            _, ch, v = osis_id.rsplit(".", 2)
        except ValueError:
            continue
        idx = 0
        for w in velem:
            if w.tag != f"{_OSIS_NS}w":
                continue
            idx += 1
            lemma = w.get("lemma", "")
            nums = re.findall(r"\d+", lemma)
            strongs = f"H{nums[-1]}" if nums else ""
            surface = "".join(w.itertext()).strip()
            words.append(Word(int(ch), int(v), idx, surface, lemma, strongs, w.get("morph", "")))
    return words


def fetch_strongs(log=print) -> dict[str, str]:
    out_dir = corpus.corpus_dir() / "strongs"
    out_dir.mkdir(parents=True, exist_ok=True)
    lemma_map: dict[str, str] = {}
    for lang, url in STRONGS_URLS.items():
        src = download(url, corpus.sources_dir() / f"strongs-{lang}.js")
        data = parse_strongs_js(src.read_text(encoding="utf-8"))
        (out_dir / f"{lang}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        log(f"strongs/{lang}: {len(data)} entries")
        if lang == "greek":
            lemma_map = build_greek_lemma_map(data)
            (out_dir / "greek-lemma-map.json").write_text(
                json.dumps(lemma_map, ensure_ascii=False), encoding="utf-8")
    return lemma_map


def load_greek_lemma_map() -> dict[str, str]:
    path = corpus.corpus_dir() / "strongs" / "greek-lemma-map.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def fetch_sblgnt(log=print) -> None:
    lemma_map = load_greek_lemma_map()
    for stem, book in zip(MORPHGNT_FILES, canon.NT_BOOKS):
        url = f"{RAW}/morphgnt/sblgnt/master/{stem}-morphgnt.txt"
        src = download(url, corpus.sources_dir() / "sblgnt" / f"{stem}-morphgnt.txt")
        corpus.write_words("sblgnt", book.osis, normalize_sblgnt(src.read_text(encoding="utf-8"), lemma_map))
        log(f"sblgnt/{book.osis} done")


def fetch_wlc(log=print) -> None:
    for book in canon.BOOKS:
        if book.nt:
            continue
        url = f"{RAW}/openscriptures/morphhb/master/wlc/{book.osis}.xml"
        src = download(url, corpus.sources_dir() / "wlc" / f"{book.osis}.xml")
        corpus.write_words("wlc", book.osis, normalize_wlc(src.read_text(encoding="utf-8")))
        log(f"wlc/{book.osis} done")


def fetch_ebible(log=print) -> None:
    for version, tid in EBIBLE.items():
        zpath = download(f"https://ebible.org/Scriptures/{tid}_usfm.zip",
                         corpus.sources_dir() / f"{tid}_usfm.zip")
        out = corpus.sources_dir() / tid
        out.mkdir(exist_ok=True)
        with zipfile.ZipFile(zpath) as z:
            z.extractall(out)
        count = 0
        for f in sorted(out.rglob("*")):
            if f.suffix.lower() not in (".usfm", ".sfm"):
                continue
            try:
                code, verses = parse_usfm(f.read_text(encoding="utf-8-sig"))
            except ValueError:
                continue
            osis = canon.USFM_TO_OSIS.get(code)
            if osis and verses:
                corpus.write_verses(version, osis, verses)
                count += 1
        log(f"{version}: {count} books")


def check_integrity() -> list[str]:
    problems: list[str] = []
    cdir = corpus.corpus_dir()
    if not cdir.is_dir():
        return ["corpus is empty — run `exeg fetch`"]
    for vdir in sorted(cdir.iterdir()):
        version = vdir.name
        if version == "strongs" or not vdir.is_dir():
            continue
        for tsv in sorted(vdir.glob("*.tsv")):
            osis = tsv.stem
            book = canon.BY_OSIS.get(osis)
            if not book:
                problems.append(f"{version}/{osis}: unknown book file")
                continue
            rows = (corpus.read_words(version, osis) if version in corpus.WORD_VERSIONS
                    else corpus.read_verses(version, osis))
            chapters = sorted({r.chapter for r in rows})
            expected = canon.WLC_CHAPTERS.get(osis, book.chapters) if version == "wlc" else book.chapters
            if chapters != list(range(1, expected + 1)):
                problems.append(f"{version}/{osis}: chapters {chapters[:3]}…{chapters[-3:] if len(chapters) > 3 else ''} "
                                f"!= 1..{expected}")
    return problems


def cmd_fetch(args) -> int:
    only = set(args.only.split(",")) if args.only else {"strongs", "sblgnt", "wlc", "ebible"}
    if "strongs" in only:
        fetch_strongs()
    if "sblgnt" in only:
        fetch_sblgnt()
    if "wlc" in only:
        fetch_wlc()
    if "ebible" in only:
        fetch_ebible()
    problems = check_integrity()
    for p in problems:
        print(f"INTEGRITY: {p}")
    print("fetch complete" + (f" — {len(problems)} problems" if problems else ", corpus healthy"))
    return 1 if problems else 0
